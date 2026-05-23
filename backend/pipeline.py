"""
RepoTerrain Pipeline — Local Mode
gitingest → sentence-transformers (local) → UMAP 3D → terrain JSON
"""

import os
import sys
import re
import uuid
import hashlib
import asyncio
from typing import Optional
from datetime import datetime

import numpy as np
import umap

# ── Windows ProactorEventLoop fix for gitingest subprocess ────
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# ── Config ────────────────────────────────────────────────────
USE_VERTEX_AI = os.environ.get("USE_VERTEX_AI", "false").lower() == "true"
GCP_PROJECT   = os.environ.get("GCP_PROJECT", "")
GCP_LOCATION  = os.environ.get("GCP_LOCATION", "us-central1")
EMBED_MODEL   = "text-embedding-005"
LOCAL_MODEL   = "all-MiniLM-L6-v2"

CHUNK_SIZE  = 2000
BATCH_SIZE  = 32
UMAP_DIM    = 3

# ── Lazy model cache ──────────────────────────────────────────
_local_model = None

def get_local_model():
    global _local_model
    if _local_model is None:
        from sentence_transformers import SentenceTransformer
        print(f"[pipeline] Loading local model: {LOCAL_MODEL}")
        _local_model = SentenceTransformer(LOCAL_MODEL)
    return _local_model


# ── Step 1: Ingest repo ───────────────────────────────────────

async def ingest_repo(repo_url: str, gitlab_token: Optional[str] = None, max_files: int = 200) -> dict:
    print(f"[pipeline] Ingesting: {repo_url}")

    if gitlab_token:
        os.environ["GITLAB_TOKEN"] = gitlab_token

    # Use ingest_async directly — works with FastAPI's event loop on Windows
    from gitingest import ingest_async
    summary, tree, content = await ingest_async(repo_url)

    print(f"[pipeline] Raw content length: {len(content)}")
    print(f"[pipeline] Content preview: {repr(content[:300])}")

    files = parse_content_to_files(content, tree, max_files)
    print(f"[pipeline] Parsed {len(files)} files")
    print(f"[pipeline] Sample paths: {list(files.keys())[:5]}")

    return {"summary": summary, "tree": tree, "files": files, "repo_url": repo_url}


def parse_content_to_files(content: str, tree: str, max_files: int) -> dict:
    files = {}

    # gitingest 0.3.1 uses this separator format:
    # ================================================
    # File: path/to/file.py
    # ================================================
    separator = re.compile(
        r"-{48}\nFile:\s*(.+?)\n-{48}",
        re.MULTILINE
    )
    parts = separator.split(content)

    if len(parts) > 1:
        i = 1
        while i + 1 < len(parts) and len(files) < max_files:
            filepath = parts[i].strip()
            file_content = parts[i + 1].strip()
            if not should_skip(filepath, file_content):
                files[filepath] = file_content[:CHUNK_SIZE]
            i += 2

    # Fallback: try = signs separator
    if not files:
        separator2 = re.compile(r"={10,}\nFile:\s*(.+?)\n={10,}\n", re.MULTILINE)
        parts = separator2.split(content)
        i = 1
        while i + 1 < len(parts) and len(files) < max_files:
            filepath = parts[i].strip()
            file_content = parts[i + 1].strip()
            if not should_skip(filepath, file_content):
                files[filepath] = file_content[:CHUNK_SIZE]
            i += 2

    # Fallback: parse tree to get real filenames, use content chunks
    if not files and tree:
        print("[pipeline] Using tree fallback parser")
        # Extract filenames from tree
        tree_files = []
        for line in tree.splitlines():
            line = line.strip().lstrip('├─└│ ')
            if '.' in line and not line.startswith('#'):
                tree_files.append(line)

        # Split content into chunks mapped to tree files
        chunks = [c.strip() for c in re.split(r'\n{3,}', content) if len(c.strip()) > 50]
        for i, filepath in enumerate(tree_files[:max_files]):
            if i < len(chunks):
                body = chunks[i]
                if not should_skip(filepath, body):
                    files[filepath] = body[:CHUNK_SIZE]

    # Last resort: line-by-line scan
    if not files and content:
        print("[pipeline] Using line-by-line fallback parser")
        lines = content.splitlines()
        current_file = None
        current_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("File: ") or stripped.startswith("## File: "):
                if current_file and current_lines:
                    body = "\n".join(current_lines).strip()
                    if not should_skip(current_file, body):
                        files[current_file] = body[:CHUNK_SIZE]
                current_file = stripped.replace("File: ", "").replace("## File: ", "").strip()
                current_lines = []
            elif current_file:
                current_lines.append(line)
        if current_file and current_lines:
            body = "\n".join(current_lines).strip()
            if not should_skip(current_file, body):
                files[current_file] = body[:CHUNK_SIZE]

    print(f"[pipeline] Sample filenames: {list(files.keys())[:5]}")
    return files


def should_skip(filepath: str, content: str) -> bool:
    skip_exts = {
        '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico',
        '.woff', '.woff2', '.ttf', '.eot', '.pdf',
        '.zip', '.tar', '.gz', '.lock', '.min.js', '.min.css',
        '.exe', '.dll', '.so', '.pyc',
    }
    skip_dirs = {
        'node_modules/', '.git/', '__pycache__/', '.venv/',
        'dist/', 'build/', 'vendor/', '.next/',
    }
    for d in skip_dirs:
        if d in filepath:
            return True
    for ext in skip_exts:
        if filepath.endswith(ext):
            return True
    if len(content.strip()) < 10:
        return True
    return False


# ── Step 2: Embed files ───────────────────────────────────────

async def embed_files(files: dict) -> dict:
    if USE_VERTEX_AI and GCP_PROJECT:
        return await embed_vertex(files)
    return await embed_local(files)


async def embed_local(files: dict) -> dict:
    print(f"[pipeline] Embedding {len(files)} files locally (sentence-transformers)...")
    model = get_local_model()
    filepaths = list(files.keys())
    contents  = [files[fp] for fp in filepaths]

    loop = asyncio.get_event_loop()
    matrix = await loop.run_in_executor(
        None,
        lambda: model.encode(contents, batch_size=BATCH_SIZE, show_progress_bar=True, convert_to_numpy=True)
    )
    return {fp: matrix[i] for i, fp in enumerate(filepaths)}


async def embed_vertex(files: dict) -> dict:
    import vertexai
    from vertexai.language_models import TextEmbeddingModel, TextEmbeddingInput

    vertexai.init(project=GCP_PROJECT, location=GCP_LOCATION)
    model = TextEmbeddingModel.from_pretrained(EMBED_MODEL)
    filepaths = list(files.keys())
    contents  = [files[fp] for fp in filepaths]
    embeddings = {}
    loop = asyncio.get_event_loop()

    print(f"[pipeline] Embedding {len(filepaths)} files via Vertex AI...")
    for i in range(0, len(filepaths), BATCH_SIZE):
        batch_paths    = filepaths[i:i + BATCH_SIZE]
        batch_contents = contents[i:i + BATCH_SIZE]
        inputs = [TextEmbeddingInput(text=c, task_type="RETRIEVAL_DOCUMENT") for c in batch_contents]
        result = await loop.run_in_executor(None, lambda inp=inputs: model.get_embeddings(inp))
        for fp, emb in zip(batch_paths, result):
            embeddings[fp] = np.array(emb.values, dtype=np.float32)
        print(f"[pipeline] Vertex batch {i // BATCH_SIZE + 1} done")

    return embeddings


# ── Step 3: UMAP → 3D ────────────────────────────────────────

def project_to_3d(embeddings: dict) -> dict:
    filepaths = list(embeddings.keys())
    matrix    = np.stack([embeddings[fp] for fp in filepaths])
    n = len(filepaths)
    print(f"[pipeline] UMAP on {matrix.shape}...")

    reducer = umap.UMAP(
        n_components=UMAP_DIM,
        n_neighbors=min(15, max(2, n - 1)),
        min_dist=0.15,
        metric="cosine",
        random_state=42,
    )
    coords = reducer.fit_transform(matrix)

    for dim in range(UMAP_DIM):
        col = coords[:, dim]
        mn, mx = col.min(), col.max()
        coords[:, dim] = 2 * (col - mn) / (mx - mn + 1e-8) - 1

    return {fp: coords[i].tolist() for i, fp in enumerate(filepaths)}


# ── Step 4: Metadata + edges ──────────────────────────────────

def compute_metadata(files: dict, coords_3d: dict) -> tuple:
    nodes, file_meta = [], {}

    for filepath, coord in coords_3d.items():
        content = files.get(filepath, "")
        size    = len(content)
        heat    = estimate_heat(filepath, size)
        node = {
            "id":       hashlib.md5(filepath.encode()).hexdigest()[:8],
            "path":     filepath,
            "name":     filepath.split("/")[-1],
            "x": coord[0], "y": coord[1], "z": coord[2],
            "heat":     heat,
            "size":     min(size / 5000, 1.0),
            "language": detect_language(filepath),
            "worldX": 0, "worldY": 0, "worldZ": 0,
        }
        nodes.append(node)
        file_meta[filepath] = node

    edges = compute_edges(nodes)
    return nodes, edges, file_meta


def estimate_heat(filepath: str, size: int) -> float:
    hot_patterns = [
        'main', 'index', 'app', 'server', 'api', 'router', 'config',
        'auth', 'core', 'base', 'utils', 'helpers', 'routes',
        'handler', 'controller', 'middleware',
    ]
    name = filepath.lower()
    heat = 0.25
    for p in hot_patterns:
        if p in name:
            heat += 0.12
    heat += min(size / 10000, 0.3)
    return min(heat, 1.0)


def detect_language(filepath: str) -> str:
    ext_map = {
        '.py': 'python', '.js': 'javascript', '.ts': 'typescript',
        '.jsx': 'react', '.tsx': 'react', '.go': 'go', '.rs': 'rust',
        '.java': 'java', '.rb': 'ruby', '.php': 'php',
        '.md': 'markdown', '.yml': 'yaml', '.yaml': 'yaml',
        '.json': 'json', '.sh': 'shell', '.sql': 'sql',
        '.html': 'html', '.css': 'css', '.scss': 'scss',
        '.toml': 'yaml', '.tf': 'other', '.kt': 'java',
    }
    for ext, lang in ext_map.items():
        if filepath.endswith(ext):
            return lang
    return 'other'


def compute_edges(nodes: list, max_dist: float = 0.35, max_per_node: int = 3) -> list:
    if not nodes:
        return []
    positions = np.array([[n['x'], n['y'], n['z']] for n in nodes])
    edges = []
    for i, node in enumerate(nodes):
        dists = np.linalg.norm(positions - positions[i], axis=1)
        dists[i] = 999
        closest = np.argsort(dists)[:max_per_node]
        for j in closest:
            if dists[j] < max_dist:
                edges.append({"source": node["id"], "target": nodes[j]["id"], "distance": float(dists[j])})
    return edges


# ── Main pipeline ─────────────────────────────────────────────

async def run_pipeline(repo_url: str, gitlab_token: Optional[str] = None, max_files: int = 200) -> dict:
    session_id = str(uuid.uuid4())[:8]
    start      = datetime.utcnow()

    repo_data  = await ingest_repo(repo_url, gitlab_token, max_files)
    if not repo_data["files"]:
        raise ValueError("No files found. Check the repo URL or token.")

    embeddings = await embed_files(repo_data["files"])
    coords_3d  = project_to_3d(embeddings)
    nodes, edges, file_meta = compute_metadata(repo_data["files"], coords_3d)

    elapsed = (datetime.utcnow() - start).seconds
    mode    = "vertex-ai" if (USE_VERTEX_AI and GCP_PROJECT) else "local"
    print(f"[pipeline] Done in {elapsed}s — {len(nodes)} nodes, mode={mode}")

    return {
        "session_id": session_id,
        "nodes":      nodes,
        "edges":      edges,
        "file_meta":  file_meta,
        "files":      repo_data["files"],
        "meta": {
            "repo_url":        repo_url,
            "file_count":      len(nodes),
            "session_id":      session_id,
            "elapsed_seconds": elapsed,
            "mode":            mode,
            "summary":         repo_data.get("summary", ""),
        },
    }