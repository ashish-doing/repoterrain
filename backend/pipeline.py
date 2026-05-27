"""
RepoTerrain Pipeline
GitLab API → Gemini Embeddings → UMAP 3D → Terrain JSON
Google Cloud Rapid Agent Hackathon
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
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
CHUNK_SIZE     = 2000
BATCH_SIZE     = 32
UMAP_DIM       = 3
MAX_FILES      = 150

SKIP_EXTS = {
    '.png','.jpg','.jpeg','.gif','.svg','.ico','.woff','.woff2',
    '.ttf','.eot','.pdf','.zip','.tar','.gz','.lock','.pyc',
    '.exe','.dll','.so','.min.js','.min.css','.map',
}
SKIP_DIRS = {
    'node_modules','__pycache__','.git','.venv','dist','build','vendor','.next',
}

# ── Step 1: Fetch repo tree + file contents via GitLab API ────

def parse_gitlab_url(repo_url: str):
    url = repo_url.rstrip('/')
    match = re.match(r'https?://([^/]+)/(.+)', url)
    if not match:
        raise ValueError(f"Cannot parse GitLab URL: {repo_url}")
    return match.group(1), match.group(2)


async def fetch_repo_files(repo_url: str, token: Optional[str] = None, max_files: int = MAX_FILES):
    host, project_path = parse_gitlab_url(repo_url)
    encoded = project_path.replace('/', '%2F')
    base = f"https://{host}/api/v4/projects/{encoded}"
    headers = {"PRIVATE-TOKEN": token} if token else {}

    files = {}
    summary = f"Repository: {repo_url}"

    async with httpx.AsyncClient(timeout=60, headers=headers) as client:
        print(f"[pipeline] Checking project: {base}")
        r = await client.get(base)
        if r.status_code == 404:
            raise ValueError(f"Repo not found: {repo_url}")
        if r.status_code != 200:
            raise ValueError(f"GitLab API error {r.status_code}: {r.text[:200]}")

        project_info = r.json()
        default_branch = project_info.get("default_branch", "main")
        summary = f"Repository: {repo_url} | Branch: {default_branch} | Description: {project_info.get('description', '')}"
        print(f"[pipeline] Default branch: {default_branch}")

        # Get file tree
        print(f"[pipeline] Fetching file tree...")
        all_items = []
        page = 1
        while len(all_items) < 500:
            r = await client.get(f"{base}/repository/tree", params={
                "recursive": "true", "per_page": 100,
                "page": page, "ref": default_branch,
            })
            if r.status_code != 200:
                break
            items = r.json()
            if not items:
                break
            all_items.extend(items)
            if len(items) < 100:
                break
            page += 1

        print(f"[pipeline] Total tree items: {len(all_items)}")

        file_paths = [
            item["path"] for item in all_items
            if item.get("type") == "blob" and not should_skip(item["path"])
        ][:max_files]

        print(f"[pipeline] Fetching {len(file_paths)} files...")
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
    return files, summary


async def fetch_file_content(client, base, filepath, branch="main"):
    encoded_path = filepath.replace('/', '%2F')
    r = await client.get(f"{base}/repository/files/{encoded_path}/raw", params={"ref": branch})
    return r.text if r.status_code == 200 else ""


def should_skip(filepath: str) -> bool:
    parts = filepath.replace('\\', '/').split('/')
    for part in parts[:-1]:
        if part in SKIP_DIRS:
            return True
    return any(filepath.endswith(ext) for ext in SKIP_EXTS)


# ── Step 2: Embed with Gemini text-embedding-004 ─────────────

async def embed_files(files: dict) -> dict:
    if GEMINI_API_KEY:
        print(f"[pipeline] Using Gemini text-embedding-004 (Google Cloud AI)...")
        return await embed_gemini(files)
    print(f"[pipeline] No Gemini key — using TF-IDF fallback...")
    return await embed_tfidf(files)


async def embed_gemini(files: dict) -> dict:
    """Embed using Google's text-embedding-004 model via Gemini API."""
    fps = list(files.keys())
    embeddings = {}
    url = f"https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent?key={GEMINI_API_KEY}"

    # Process in batches to avoid rate limits
    async with httpx.AsyncClient(timeout=60) as client:
        for i, fp in enumerate(fps):
            text = files[fp][:2000]
            try:
                r = await client.post(url, json={
                    "model": "models/text-embedding-004",
                    "content": {"parts": [{"text": text}]},
                    "taskType": "RETRIEVAL_DOCUMENT",
                })
                data = r.json()
                vec = data.get("embedding", {}).get("values", [])
                if vec:
                    embeddings[fp] = np.array(vec, dtype=np.float32)
                else:
                    print(f"[pipeline] Gemini embed error for {fp}: {data.get('error', {}).get('message', 'unknown')}")
                    embeddings[fp] = np.random.randn(768).astype(np.float32)
            except Exception as e:
                print(f"[pipeline] Embed exception {fp}: {e}")
                embeddings[fp] = np.random.randn(768).astype(np.float32)

            if (i + 1) % 10 == 0:
                print(f"[pipeline] Embedded {i+1}/{len(fps)} files")
                await asyncio.sleep(0.5)  # gentle rate limiting

    print(f"[pipeline] Gemini embedding done: {len(embeddings)} files, dim=768")
    return embeddings


async def embed_tfidf(files: dict) -> dict:
    """Fast TF-IDF fallback when no Gemini key."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    print(f"[pipeline] TF-IDF embedding {len(files)} files...")
    fps = list(files.keys())
    texts = [files[fp] for fp in fps]
    vectorizer = TfidfVectorizer(max_features=384, stop_words='english')
    matrix = vectorizer.fit_transform(texts).toarray().astype(np.float32)
    print(f"[pipeline] TF-IDF done, shape: {matrix.shape}")
    return {fp: matrix[i] for i, fp in enumerate(fps)}


# ── Step 3: UMAP → 3D ────────────────────────────────────────

def project_to_3d(embeddings: dict) -> dict:
    fps = list(embeddings.keys())
    matrix = np.stack([embeddings[fp] for fp in fps])
    n = len(fps)
    print(f"[pipeline] UMAP projecting {matrix.shape} → 3D...")
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


# ── Step 4: Metadata + clustering ────────────────────────────

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
           'core','base','utils','helpers','routes','handler','controller',
           'manager','executor','runner','builder','factory']
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
        '.c':'c','.cpp':'cpp','.h':'c','.cs':'csharp',
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
                edges.append({
                    "source": node["id"],
                    "target": nodes[j]["id"],
                    "distance": float(dists[j])
                })
    return edges


# ── Main pipeline ─────────────────────────────────────────────

async def run_pipeline(repo_url: str, gitlab_token: Optional[str] = None, max_files: int = MAX_FILES) -> dict:
    session_id = str(uuid.uuid4())[:8]
    start = datetime.utcnow()

    files, summary = await fetch_repo_files(repo_url, gitlab_token, max_files)
    if not files:
        raise ValueError("No files found. Check the repo URL and make sure it's public.")

    embeddings = await embed_files(files)
    coords_3d  = project_to_3d(embeddings)
    nodes, edges, file_meta = compute_metadata(files, coords_3d)

    elapsed = (datetime.utcnow() - start).seconds
    mode = "gemini-embedding" if GEMINI_API_KEY else "tfidf"
    print(f"[pipeline] Done in {elapsed}s — {len(nodes)} nodes, mode={mode}")

    return {
        "session_id": session_id,
        "nodes": nodes, "edges": edges, "file_meta": file_meta,
        "files": files,
        "meta": {
            "repo_url": repo_url, "file_count": len(nodes),
            "session_id": session_id, "elapsed_seconds": elapsed,
            "mode": mode, "summary": summary,
            "embedding_model": "text-embedding-004" if GEMINI_API_KEY else "tfidf",
        },
    }