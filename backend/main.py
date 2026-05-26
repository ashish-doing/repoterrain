"""
RepoTerrain — Backend API
"""

import sys
import asyncio

# ── Windows fix: ProactorEventLoop needed for gitingest subprocesses ──
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import os
from typing import Optional
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from pipeline import run_pipeline
from agent import agent_query

app = FastAPI(title="RepoTerrain API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve frontend
from fastapi.responses import HTMLResponse

@app.get("/app")
async def serve_frontend():
    path = os.path.join(os.path.dirname(__file__), "index.html")
    with open(path) as f:
        return HTMLResponse(f.read())

terrain_cache: dict = {}

class IngestRequest(BaseModel):
    repo_url: str
    gitlab_token: Optional[str] = None
    max_files: int = 150

class AgentQueryRequest(BaseModel):
    session_id: str
    query: str
    selected_file: Optional[str] = None
    selected_cluster: Optional[list] = None

@app.get("/")
async def root():
    return {"status": "RepoTerrain API running", "version": "1.0.0"}

@app.post("/ingest")
async def ingest_repo(req: IngestRequest):
    try:
        data = await run_pipeline(
            repo_url=req.repo_url,
            gitlab_token=req.gitlab_token,
            max_files=req.max_files,
        )
        terrain_cache[data["session_id"]] = data
        return {
            "session_id": data["session_id"],
            "nodes": data["nodes"],
            "edges": data["edges"],
            "meta": data["meta"],
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/agent/query")
async def query_agent(req: AgentQueryRequest):
    terrain = terrain_cache.get(req.session_id)
    if not terrain:
        raise HTTPException(status_code=404, detail="Session not found.")
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
                        query=data.get("query", "Explain this"),
                        terrain_data=terrain,
                        selected_file=data.get("file"),
                        selected_cluster=data.get("cluster"),
                    )
                    await websocket.send_json({"type": "agent_response", **response})
    except WebSocketDisconnect:
        pass

@app.get("/terrain/{session_id}")
async def get_terrain(session_id: str):
    terrain = terrain_cache.get(session_id)
    if not terrain:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"nodes": terrain["nodes"], "edges": terrain["edges"], "meta": terrain["meta"]}