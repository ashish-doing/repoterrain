"""
RepoTerrain — Backend API
Google Cloud Rapid Agent Hackathon — GitLab Track
"""

import sys
import asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import os
import time
from typing import Optional
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from pipeline import run_pipeline
from agent import agent_query

app = FastAPI(title="RepoTerrain API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

terrain_cache: dict = {}
start_time = time.time()

# ── Simple in-memory rate limiting ───────────────────────────
# Protects shared Gemini/GitLab API quotas during public demos.
# Keyed by client IP; sliding 60s window.
_rate_buckets: dict = {}
RATE_LIMITS = {
    "/ingest":      (5, 60),    # 5 ingests per 60s per IP
    "/agent/query": (15, 60),   # 15 agent queries per 60s per IP
}


def check_rate_limit(path: str, client_ip: str):
    limit, window = RATE_LIMITS.get(path, (None, None))
    if limit is None:
        return
    now = time.time()
    key = (path, client_ip)
    bucket = _rate_buckets.setdefault(key, [])
    bucket[:] = [t for t in bucket if now - t < window]
    if len(bucket) >= limit:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded: max {limit} requests per {window}s on {path}. Please wait and try again.",
        )
    bucket.append(now)


# ── Pages ─────────────────────────────────────────────────────

@app.get("/")
async def serve_landing():
    path = os.path.join(os.path.dirname(__file__), "landing.html")
    with open(path) as f:
        return HTMLResponse(f.read())


@app.get("/app")
async def serve_frontend():
    path = os.path.join(os.path.dirname(__file__), "index.html")
    with open(path) as f:
        return HTMLResponse(f.read())


# ── Health ────────────────────────────────────────────────────

@app.get("/health")
async def health():
    gemini_key = bool(os.environ.get("GEMINI_API_KEY"))
    return {
        "status": "ok",
        "version": "2.0.0",
        "uptime_seconds": round(time.time() - start_time),
        "active_sessions": len(terrain_cache),
        # AI stack
        "agent_model_primary": "gemini-2.0-flash",
        "agent_model_quota_fallback": "groq-llama3.1",   # transparent — used only when Gemini quota exceeded
        "embedding_model": "text-embedding-004" if gemini_key else "tfidf-fallback",
        "gemini_configured": gemini_key,
        "groq_fallback_configured": bool(os.environ.get("GROQ_API_KEY")),
        # GitLab integration
        "gitlab_mcp_gateway": os.environ.get("GITLAB_MCP_GATEWAY_URL", "not configured"),
        "gitlab_mcp_gateway_configured": bool(os.environ.get("GITLAB_MCP_GATEWAY_URL")),
        "gitlab_token_configured": bool(os.environ.get("GITLAB_TOKEN")),
    }


# ── Models ────────────────────────────────────────────────────

class IngestRequest(BaseModel):
    repo_url: str
    gitlab_token: Optional[str] = None
    max_files: int = 150


class AgentQueryRequest(BaseModel):
    session_id: str
    query: str
    selected_file: Optional[str] = None
    selected_cluster: Optional[list] = None


# ── Ingest ────────────────────────────────────────────────────

@app.post("/ingest")
async def ingest_repo(req: IngestRequest, request: Request):
    check_rate_limit("/ingest", request.client.host if request.client else "unknown")
    try:
        data = await run_pipeline(
            repo_url=req.repo_url,
            gitlab_token=req.gitlab_token,
            max_files=req.max_files,
        )
        terrain_cache[data["session_id"]] = data
        return {
            "session_id": data["session_id"],
            "nodes":      data["nodes"],
            "edges":      data["edges"],
            "meta":       data["meta"],
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ── Agent ─────────────────────────────────────────────────────

@app.post("/agent/query")
async def query_agent(req: AgentQueryRequest, request: Request):
    check_rate_limit("/agent/query", request.client.host if request.client else "unknown")
    terrain = terrain_cache.get(req.session_id)
    if not terrain:
        raise HTTPException(status_code=404, detail="Session not found. Re-ingest the repo.")
    try:
        return await agent_query(
            session_id=req.session_id,
            query=req.query,
            terrain_data=terrain,
            selected_file=req.selected_file,
            selected_cluster=req.selected_cluster,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── WebSocket ─────────────────────────────────────────────────

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "agent_query":
                terrain = terrain_cache.get(session_id)
                if terrain:
                    response = await agent_query(
                        session_id=session_id,
                        query=data.get("query", "Explain this codebase"),
                        terrain_data=terrain,
                        selected_file=data.get("file"),
                        selected_cluster=data.get("cluster"),
                    )
                    await websocket.send_json({"type": "agent_response", **response})
    except WebSocketDisconnect:
        pass


# ── Terrain fetch ─────────────────────────────────────────────

@app.get("/terrain/{session_id}")
async def get_terrain(session_id: str):
    terrain = terrain_cache.get(session_id)
    if not terrain:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "nodes": terrain["nodes"],
        "edges": terrain["edges"],
        "meta":  terrain["meta"],
    }