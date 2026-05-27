"""
RepoTerrain Pipeline
GitLab API → sentence-transformers → UMAP 3D → terrain JSON
No subprocess needed. Works on Windows with SelectorEventLoop.
"""

import os
import re
import uuid
import hashlib
import asyncio
from typing import Optional
from datetime import datetime

import httpx
import numpy as np
import umap

# ── Config ────────────────────────────────────────────────────
USE_VERTEX_AI = os.environ.get("USE_VERTEX_AI", "false").lower() == "true"
GCP_PROJECT   = os.environ.get("GCP_PROJECT", "")
GCP_LOCATION  = os.environ.get("GCP_LOCATION", "us-central1")
LOCAL_MODEL   = "all-MiniLM-L6-v2"
CHUNK_SIZE    = 2000
BATCH_SIZE    = 32
UMAP_DIM      = 3
MAX_FILES     = 150

SKIP_EXTS = {
    '.png','.jpg','.jpeg','.gif','.svg','.ico','.woff','.woff2',
    '.ttf','.eot','.pdf','.zip','.tar','.gz','.lock','.pyc',
    '.exe','.dll','.so','.min.js','.min.css','.map',
}
SKIP_DIRS = {
    'node_modules','__pycache__','.git','.venv','dist','build','vendor','.next',
}

def get_local_model():
    pass  # no longer used


# ── Step 1: Fetch repo tree + file contents via GitLab API ────

def parse_gitlab_url(repo_url: str):
    """Extract host, project_path from GitLab URL."""
    url = repo_url.rstrip('/')
    # Handle https://gitlab.com/group/repo or https://gitlab.com/group/sub/repo
    match = re.match(r'https?://([^/]+)/(.+)', url)
    if not match:
        raise ValueError(f"Cannot parse GitLab URL: {repo_url}")
    host = match.group(1)
    path = match.group(2)
    return host, path


async def fetch_repo_files(repo_url: str, token: Optional[str] = None, max_files: int = MAX_FILES) -> dict:
    """Fetch file tree and contents from GitLab API."""
    host, project_path = parse_gitlab_url(repo_url)
    encoded = project_path.replace('/', '%2F')
    base = f"https://{host}/api/v4/projects/{encoded}"
    headers = {}
    if token:
        headers["PRIVATE-TOKEN"] = token

    files = {}
    summary = f"Repository: {repo_url}"

    async with httpx.AsyncClient(timeout=60, headers=headers) as client:
        # First verify project exists
        print(f"[pipeline] Checking project: {base}")
        r = await client.get(f"{base}")
        if r.status_code == 404:
            raise ValueError(f"Repo not found: {repo_url}. Make sure it's public or provide a token.")
        if r.status_code != 200:
            raise ValueError(f"GitLab API error {r.status_code}: {r.text[:200]}")

        project_info = r.json()
        default_branch = project_info.get("default_branch", "main")
        print(f"[pipeline] Default branch: {default_branch}")

        # Get file tree (recursive)
        print(f"[pipeline] Fetching file tree...")
        all_items = []
        page = 1
        while len(all_items) < 500:
            r = await client.get(f"{base}/repository/tree", params={
                "recursive": "true",
                "per_page": 100,
                "page": page,
                "ref": default_branch,
            })
            if r.status_code != 200:
                print(f"[pipeline] Tree error {r.status_code}: {r.text[:200]}")
                break
            items = r.json()
            if not items:
                break
            all_items.extend(items)
            if len(items) < 100:
                break
            page += 1

        print(f"[pipeline] Total tree items: {len(all_items)}")

        # Filter to files only
        file_paths = []
        for item in all_items:
            if item.get("type") != "blob":
                continue
            path = item["path"]
            if not should_skip(path):
                file_paths.append(path)

        print(f"[pipeline] Filtered to {len(file_paths)} files, fetching content...")
        file_paths = file_paths[:max_files]

        # Fetch file contents in parallel batches
        for i in range(0, len(file_paths), 10):
            batch = file_paths[i:i+10]
            tasks = [fetch_file_content(client, base, fp, default_branch) for fp in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for fp, content in zip(batch, results):
                if isinstance(content, Exception):
                    continue
                if content and len(content.strip()) > 10:
                    files[fp] = content[:CHUNK_SIZE]
            print(f"[pipeline] Fetched {min(i+10, len(file_paths))}/{len(file_paths)} files")

    print(f"[pipeline] Got {len(files)} files")
    print(f"[pipeline] Sample paths: {list(files.keys())[:5]}")
    return files, summary


async def fetch_file_content(client: httpx.AsyncClient, base: str, filepath: str, branch: str = "main") -> str:
    """Fetch single file content via GitLab API."""
    encoded_path = filepath.replace('/', '%2F')
    r = await client.get(f"{base}/repository/files/{encoded_path}/raw", params={"ref": branch})
    if r.status_code == 200:
        return r.text
    return ""


async def fallback_gitingest(repo_url: str, token: Optional[str]) -> dict:
    """Last resort: use gitingest in a separate thread with new event loop."""
    import concurrent.futures
    def run_ingest():
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            from gitingest import ingest_async
            return loop.run_until_complete(ingest_async(repo_url))
        finally:
            loop.close()

    with concurrent.futures.ThreadPoolExecutor() as pool:
        future = pool.submit(run_ingest)
        summary, tree, content = future.result(timeout=120)

    return parse_content_to_files(content, tree, MAX_FILES)


def parse_content_to_files(content: str, tree: str, max_files: int) -> dict:
    """Parse gitingest content format."""
    files = {}
    # Try multiple separator patterns
    for pattern in [
        r"-{48}\nFile:\s*(.+?)\n-{48}\n",
        r"={10,}\nFile:\s*(.+?)\n={10,}\n",
        r"#{3,}\s*File:\s*(.+?)\n",
    ]:
        parts = re.compile(pattern, re.MULTILINE).split(content)
        if len(parts) > 1:
            i = 1
            while i + 1 < len(parts) and len(files) < max_files:
                fp = parts[i].strip()
                body = parts[i+1].strip()
                if fp and not should_skip(fp) and len(body) > 10:
                    files[fp] = body[:CHUNK_SIZE]
                i += 2
            if files:
                break
    return files


def should_skip(filepath: str) -> bool:
    parts = filepath.replace('\\', '/').split('/')
    for part in parts[:-1]:
        if part in SKIP_DIRS:
            return True
    for ext in SKIP_EXTS:
        if filepath.endswith(ext):
            return True
    return False


# ── Step 2: Embed ─────────────────────────────────────────────

async def embed_files(files: dict) -> dict:
    if USE_VERTEX_AI and GCP_PROJECT:
        return await embed_vertex(files)
    return await embed_local(files)


async def embed_local(files: dict) -> dict:
    from sklearn.feature_extraction.text import TfidfVectorizer
    print(f"[pipeline] Embedding {len(files)} files with TF-IDF...")
    fps = list(files.keys())
    texts = [files[fp] for fp in fps]
    vectorizer = TfidfVectorizer(max_features=384, stop_words='english')
    matrix = vectorizer.fit_transform(texts).toarray().astype(np.float32)
    print(f"[pipeline] Embedding done, shape: {matrix.shape}")
    return {fp: matrix[i] for i, fp in enumerate(fps)}


async def embed_vertex(files: dict) -> dict:
    import vertexai
    from vertexai.language_models import TextEmbeddingModel, TextEmbeddingInput
    vertexai.init(project=GCP_PROJECT, location=GCP_LOCATION)
    model = TextEmbeddingModel.from_pretrained("text-embedding-005")
    fps = list(files.keys())
    texts = [files[fp] for fp in fps]
    embeddings = {}
    loop = asyncio.get_event_loop()
    for i in range(0, len(fps), BATCH_SIZE):
        batch_fps = fps[i:i+BATCH_SIZE]
        batch_texts = texts[i:i+BATCH_SIZE]
        inputs = [TextEmbeddingInput(text=t, task_type="RETRIEVAL_DOCUMENT") for t in batch_texts]
        result = await loop.run_in_executor(None, lambda inp=inputs: model.get_embeddings(inp))
        for fp, emb in zip(batch_fps, result):
            embeddings[fp] = np.array(emb.values, dtype=np.float32)
    return embeddings


# ── Step 3: UMAP → 3D ────────────────────────────────────────

def project_to_3d(embeddings: dict) -> dict:
    fps = list(embeddings.keys())
    matrix = np.stack([embeddings[fp] for fp in fps])
    n = len(fps)
    print(f"[pipeline] UMAP {matrix.shape}...")
    reducer = umap.UMAP(
        n_components=UMAP_DIM,
        n_neighbors=min(15, max(2, n-1)),
        min_dist=0.15,
        metric="cosine",
        random_state=42,
    )
    coords = reducer.fit_transform(matrix)
    for dim in range(UMAP_DIM):
        col = coords[:, dim]
        mn, mx = col.min(), col.max()
        coords[:, dim] = 2*(col-mn)/(mx-mn+1e-8) - 1
    return {fp: coords[i].tolist() for i, fp in enumerate(fps)}


# ── Step 4: Metadata + edges ──────────────────────────────────

def compute_metadata(files: dict, coords_3d: dict) -> tuple:
    nodes, file_meta = [], {}
    for fp, coord in coords_3d.items():
        content = files.get(fp, "")
        size = len(content)
        node = {
            "id":       hashlib.md5(fp.encode()).hexdigest()[:8],
            "path":     fp,
            "name":     fp.split("/")[-1],
            "x": coord[0], "y": coord[1], "z": coord[2],
            "heat":     estimate_heat(fp, size),
            "size":     min(size/5000, 1.0),
            "language": detect_language(fp),
            "worldX": 0, "worldY": 0, "worldZ": 0,
        }
        nodes.append(node)
        file_meta[fp] = node
    edges = compute_edges(nodes)
    return nodes, edges, file_meta


def estimate_heat(fp: str, size: int) -> float:
    hot = ['main','index','app','server','api','router','config','auth',
           'core','base','utils','helpers','routes','handler','controller']
    name = fp.lower()
    heat = 0.25
    for p in hot:
        if p in name:
            heat += 0.12
    heat += min(size/10000, 0.3)
    return min(heat, 1.0)


def detect_language(fp: str) -> str:
    ext_map = {
        '.py':'python','.js':'javascript','.ts':'typescript',
        '.jsx':'react','.tsx':'react','.go':'go','.rs':'rust',
        '.java':'java','.rb':'ruby','.php':'php',
        '.md':'markdown','.yml':'yaml','.yaml':'yaml',
        '.json':'json','.sh':'shell','.sql':'sql',
        '.html':'html','.css':'css','.scss':'scss',
        '.toml':'yaml','.tf':'other','.kt':'java','.vue':'javascript',
    }
    for ext, lang in ext_map.items():
        if fp.endswith(ext):
            return lang
    return 'other'


def compute_edges(nodes: list, max_dist: float = 0.35, max_per_node: int = 3) -> list:
    if not nodes:
        return []
    positions = np.array([[n['x'],n['y'],n['z']] for n in nodes])
    edges = []
    for i, node in enumerate(nodes):
        dists = np.linalg.norm(positions - positions[i], axis=1)
        dists[i] = 999
        for j in np.argsort(dists)[:max_per_node]:
            if dists[j] < max_dist:
                edges.append({"source": node["id"], "target": nodes[j]["id"], "distance": float(dists[j])})
    return edges


# ── Main pipeline ─────────────────────────────────────────────

async def run_pipeline(repo_url: str, gitlab_token: Optional[str] = None, max_files: int = MAX_FILES) -> dict:
    session_id = str(uuid.uuid4())[:8]
    start = datetime.utcnow()

    files, summary = await fetch_repo_files(repo_url, gitlab_token, max_files)
    if not files:
        raise ValueError("No files found. Check the repo URL.")

    embeddings = await embed_files(files)
    coords_3d  = project_to_3d(embeddings)
    nodes, edges, file_meta = compute_metadata(files, coords_3d)

    elapsed = (datetime.utcnow() - start).seconds
    mode = "vertex-ai" if (USE_VERTEX_AI and GCP_PROJECT) else "local"
    print(f"[pipeline] Done in {elapsed}s — {len(nodes)} nodes")

    return {
        "session_id": session_id,
        "nodes": nodes, "edges": edges, "file_meta": file_meta,
        "files": files,
        "meta": {
            "repo_url": repo_url, "file_count": len(nodes),
            "session_id": session_id, "elapsed_seconds": elapsed,
            "mode": mode, "summary": summary,
        },
    }