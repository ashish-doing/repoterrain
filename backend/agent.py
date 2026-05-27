"""
RepoTerrain Agent — Gemini 2.0 Flash + GitLab MCP Actions
Google Cloud Rapid Agent Hackathon — GitLab Track
"""
from dotenv import load_dotenv
load_dotenv()

import os
import httpx
import asyncio
from typing import Optional

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GROQ_API_KEY   = os.environ.get("GROQ_API_KEY", "")   # fallback
GITLAB_TOKEN   = os.environ.get("GITLAB_TOKEN", "")

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
GROQ_URL   = "https://api.groq.com/openai/v1/chat/completions"

SYSTEM_PROMPT = """You are RepoTerrain's codebase intelligence agent — powered by Google Gemini.
You analyze GitLab repositories visualized as a live 3D semantic terrain.

Each file is a floating card. Position = semantic similarity (UMAP). Color = activity heat.
Clusters = functionally related modules. Edges = semantic connections.

RESPONSE FORMAT (always use this):
🎯 **[Module or File Name]**
• Why: [one line — specific reason]
• Key files: [2-3 real filenames from the terrain]
• Heat: [🔴 Hot / 🟡 Warm / 🔵 Cold]
• Action: [one concrete next step]

RULES:
- Under 120 words
- Only reference files that actually exist in the terrain data provided
- Never invent file paths or line numbers
- Be specific, technical, and actionable

GITLAB ACTIONS:
If asked to create an issue, MR, or label:
✅ **GitLab Issue Created**
• Title: [title]
• Labels: [label1, label2]
• URL: [will be shown if token available]

If asked about commits, pipelines, or MRs — describe what you would fetch and why it matters.
"""

_sessions: dict = {}


async def agent_query(
    session_id: str,
    query: str,
    terrain_data: dict,
    selected_file: Optional[str] = None,
    selected_cluster: Optional[list] = None,
) -> dict:
    context = build_context(terrain_data, selected_file, selected_cluster)
    message = build_message(query, context)

    session = _sessions.get(session_id, {"history": []})
    history = session.get("history", [])

    # Try Gemini first, fall back to Groq
    if GEMINI_API_KEY:
        response = await call_gemini(message, history)
    elif GROQ_API_KEY:
        response = await call_groq(message, history)
    else:
        response = demo_response(query, selected_file, terrain_data)

    history.append({"role": "user",  "parts": [{"text": message}]})
    history.append({"role": "model", "parts": [{"text": response["text"]}]})
    session["history"] = history[-16:]
    _sessions[session_id] = session

    return response


def build_context(terrain_data: dict, selected_file: Optional[str], selected_cluster: Optional[list]) -> dict:
    files = terrain_data.get("files", {})
    nodes = terrain_data.get("nodes", [])

    # Build cluster map from nodes
    cluster_map = {}
    for node in nodes:
        lang = node.get("language", "other")
        cluster_map.setdefault(lang, []).append(node["path"])

    ctx = {
        "total_files":   len(nodes),
        "repo_url":      terrain_data["meta"]["repo_url"],
        "clusters":      {k: v[:5] for k, v in list(cluster_map.items())[:6]},
        "selected_file": None,
        "file_content":  "",
        "cluster_files": [],
        "hot_files":     [n["path"] for n in sorted(nodes, key=lambda x: x.get("heat", 0), reverse=True)[:5]],
        "cold_files":    [n["path"] for n in sorted(nodes, key=lambda x: x.get("heat", 0))[:5]],
    }

    if selected_file and selected_file in files:
        ctx["selected_file"] = selected_file
        ctx["file_content"]  = files[selected_file][:3000]

    if selected_cluster:
        for fp in selected_cluster[:4]:
            if fp in files:
                ctx["cluster_files"].append({"path": fp, "preview": files[fp][:600]})

    return ctx


def build_message(query: str, ctx: dict) -> str:
    parts = [
        f"Repository: {ctx['repo_url']}",
        f"Total files: {ctx['total_files']}",
        f"Hottest files: {', '.join(ctx['hot_files'])}",
        f"Coldest files: {', '.join(ctx['cold_files'])}",
    ]

    if ctx["clusters"]:
        parts.append(f"Language clusters: {ctx['clusters']}")

    if ctx["selected_file"]:
        parts.append(f"\nSelected file: {ctx['selected_file']}")
        parts.append(f"Content preview:\n```\n{ctx['file_content']}\n```")

    if ctx["cluster_files"]:
        parts.append(f"\nSelected cluster ({len(ctx['cluster_files'])} files):")
        for f in ctx["cluster_files"]:
            parts.append(f"--- {f['path']} ---\n{f['preview']}")

    parts.append(f"\nUser query: {query}")
    return "\n".join(parts)


# ── Gemini 2.0 Flash ─────────────────────────────────────────

async def call_gemini(message: str, history: list) -> dict:
    contents = []
    for h in history[-8:]:
        contents.append(h)
    contents.append({"role": "user", "parts": [{"text": message}]})

    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": contents,
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 600,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{GEMINI_URL}?key={GEMINI_API_KEY}",
                json=payload,
            )
            data = r.json()

        text = (
            data.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
        )

        if not text:
            error_msg = data.get("error", {}).get("message", "Unknown Gemini error")
            print(f"[agent] Gemini error: {error_msg}")
            # Fall back to Groq if available
            if GROQ_API_KEY:
                return await call_groq(message, history)
            return {"text": f"⚠️ AI unavailable: {error_msg}", "actions": [], "model": "error"}

        actions = await execute_gitlab_actions(message, text)
        return {"text": text, "actions": actions, "model": "gemini-2.0-flash"}

    except Exception as e:
        print(f"[agent] Gemini exception: {e}")
        if GROQ_API_KEY:
            return await call_groq(message, history)
        return {"text": f"Agent error: {str(e)}", "actions": [], "model": "error"}


# ── Groq fallback ─────────────────────────────────────────────

async def call_groq(message: str, history: list) -> dict:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for h in history[-8:]:
        role = "assistant" if h["role"] == "model" else "user"
        messages.append({"role": role, "content": h["parts"][0]["text"]})
    messages.append({"role": "user", "content": message})

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                GROQ_URL,
                headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                json={
                    "model": "llama-3.1-8b-instant",
                    "messages": messages,
                    "temperature": 0.3,
                    "max_tokens": 600,
                },
            )
            data = r.json()

        if "choices" not in data:
            print(f"[agent] Groq error: {data}")
            return {"text": f"⚠️ {data.get('error', {}).get('message', str(data))}", "actions": [], "model": "error"}

        text = data["choices"][0]["message"]["content"]
        actions = await execute_gitlab_actions(message, text)
        return {"text": text, "actions": actions, "model": "groq-llama3"}

    except Exception as e:
        print(f"[agent] Groq exception: {e}")
        return {"text": f"Agent error: {str(e)}", "actions": [], "model": "error"}


# ── GitLab MCP Actions ────────────────────────────────────────

async def execute_gitlab_actions(query: str, response_text: str) -> list:
    if not GITLAB_TOKEN:
        return []

    q = query.lower()
    actions = []

    if "create" in q and "issue" in q:
        lines = [l.strip() for l in response_text.split("\n") if l.strip()]
        title = next((l for l in lines if l and not l.startswith("•") and not l.startswith("-")), "RepoTerrain: Codebase Issue")
        title = title.strip("🎯#* ").strip()[:80]
        if not title:
            title = "RepoTerrain: Auto-generated issue"

        labels = []
        if "cold" in q or "legacy" in q:
            labels = ["tech-debt", "low-priority"]
        elif "hot" in q or "complex" in q:
            labels = ["needs-review", "high-priority"]
        else:
            labels = ["repoterrain"]

        result = await gitlab_create_issue(title, response_text, labels)
        if result:
            actions.append({"tool": "create_issue", "result": result, "title": title})

    elif "list" in q and ("mr" in q or "merge request" in q):
        result = await gitlab_list_mrs()
        if result:
            actions.append({"tool": "list_mrs", "result": result})

    elif "pipeline" in q or "ci" in q:
        result = await gitlab_get_pipelines()
        if result:
            actions.append({"tool": "get_pipelines", "result": result})

    return actions


async def gitlab_create_issue(title: str, description: str, labels: list) -> Optional[dict]:
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                "https://gitlab.com/api/v4/issues",
                headers={"PRIVATE-TOKEN": GITLAB_TOKEN},
                json={
                    "title": title,
                    "description": f"Created by RepoTerrain AI Agent\n\n{description}",
                    "labels": ",".join(labels),
                },
            )
            data = r.json()
            return {
                "url": data.get("web_url", ""),
                "id": data.get("iid", ""),
                "title": data.get("title", title),
            }
    except Exception as e:
        print(f"[agent] GitLab create issue error: {e}")
        return None


async def gitlab_list_mrs() -> Optional[list]:
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                "https://gitlab.com/api/v4/merge_requests",
                headers={"PRIVATE-TOKEN": GITLAB_TOKEN},
                params={"state": "opened", "per_page": 5},
            )
            data = r.json()
            return [{"title": mr.get("title"), "url": mr.get("web_url"), "state": mr.get("state")} for mr in data[:5]]
    except Exception as e:
        print(f"[agent] GitLab list MRs error: {e}")
        return None


async def gitlab_get_pipelines() -> Optional[list]:
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                "https://gitlab.com/api/v4/projects",
                headers={"PRIVATE-TOKEN": GITLAB_TOKEN},
                params={"membership": True, "per_page": 1},
            )
            projects = r.json()
            if not projects:
                return None
            project_id = projects[0]["id"]
            r2 = await client.get(
                f"https://gitlab.com/api/v4/projects/{project_id}/pipelines",
                headers={"PRIVATE-TOKEN": GITLAB_TOKEN},
                params={"per_page": 5},
            )
            data = r2.json()
            return [{"id": p.get("id"), "status": p.get("status"), "ref": p.get("ref")} for p in data[:5]]
    except Exception as e:
        print(f"[agent] GitLab pipelines error: {e}")
        return None


# ── Demo fallback ─────────────────────────────────────────────

def demo_response(query: str, selected_file: Optional[str], terrain_data: dict) -> dict:
    total = len(terrain_data.get("nodes", [])) if terrain_data else 0
    nodes = terrain_data.get("nodes", []) if terrain_data else []
    hot = [n["path"] for n in sorted(nodes, key=lambda x: x.get("heat", 0), reverse=True)[:3]]
    q = query.lower() if query else ""

    if selected_file:
        name = selected_file.split("/")[-1]
        text = (
            f"🎯 **{name}**\n"
            f"• Why: Central file in its semantic cluster\n"
            f"• Key files: {selected_file}\n"
            f"• Heat: 🟡 Warm\n"
            f"• Action: Add GEMINI_API_KEY for real AI analysis"
        )
    elif "complex" in q or "hot" in q:
        top = hot[0] if hot else "main file"
        text = (
            f"🎯 **{top.split('/')[-1]}**\n"
            f"• Why: Highest activity heat in terrain\n"
            f"• Key files: {', '.join(hot[:2])}\n"
            f"• Heat: 🔴 Hot\n"
            f"• Action: Add GEMINI_API_KEY for deep analysis"
        )
    else:
        text = (
            f"🎯 **{total} files** mapped across semantic clusters\n"
            f"• Why: Files positioned by code similarity via UMAP\n"
            f"• Key files: {', '.join(hot[:2]) if hot else 'loading...'}\n"
            f"• Heat: Mixed zones detected\n"
            f"• Action: Add GEMINI_API_KEY to enable real AI"
        )

    return {"text": text, "actions": [], "model": "demo-mode"}