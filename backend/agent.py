"""
RepoTerrain Agent — Local Mode
Uses Google Gemini API (free tier) via google-generativeai SDK.
No GCP project or Vertex AI needed for this.

Get a free API key at: https://aistudio.google.com/app/apikey
"""

import os
import json
import httpx
import asyncio
from typing import Optional

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GITLAB_TOKEN   = os.environ.get("GITLAB_TOKEN", "")

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

SYSTEM_PROMPT = """You are RepoTerrain's codebase intelligence agent.

You are looking at a 3D terrain visualization of a GitLab repository where:
- Each file is a card positioned by semantic similarity (via UMAP embeddings)
- File heat (color) represents estimated activity level
- Clusters = functionally related modules
- Edges connect semantically similar files

When the user selects a file or cluster, you receive its content preview and position context.

Be concise (your response overlays on a 3D scene), specific (reference actual filenames), and actionable.

If asked to create a GitLab issue, MR, or fetch commits — describe exactly what you would do and
what the result would be (real GitLab actions require a token to be set).
"""

# Session store
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

    session  = _sessions.get(session_id, {"history": []})
    history  = session.get("history", [])

    if GEMINI_API_KEY:
        response = await call_gemini(message, history)
    else:
        response = demo_response(query, selected_file, terrain_data)

    history.append({"role": "user",  "parts": [{"text": message}]})
    history.append({"role": "model", "parts": [{"text": response["text"]}]})
    session["history"] = history[-16:]  # keep last 8 turns
    _sessions[session_id] = session

    return response


def build_context(terrain_data: dict, selected_file: Optional[str], selected_cluster: Optional[list]) -> dict:
    files = terrain_data.get("files", {})
    ctx = {
        "total_files":    len(terrain_data.get("nodes", [])),
        "repo_url":       terrain_data["meta"]["repo_url"],
        "selected_file":  None,
        "file_content":   "",
        "cluster_files":  [],
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
        f"Total files in terrain: {ctx['total_files']}",
    ]
    if ctx["selected_file"]:
        parts.append(f"\nSelected file: {ctx['selected_file']}")
        parts.append(f"Content:\n```\n{ctx['file_content']}\n```")
    if ctx["cluster_files"]:
        parts.append(f"\nSelected cluster ({len(ctx['cluster_files'])} files):")
        for f in ctx["cluster_files"]:
            parts.append(f"--- {f['path']} ---\n{f['preview']}")
    parts.append(f"\nUser: {query}")
    return "\n".join(parts)


async def call_gemini(message: str, history: list) -> dict:
    """Call Gemini 2.0 Flash via free REST API."""
    contents = []

    # Add history
    for h in history[-8:]:
        contents.append(h)

    # Add current message
    contents.append({"role": "user", "parts": [{"text": message}]})

    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": contents,
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 800,
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
            return demo_response("", None, {})

        # Check for GitLab actions in the response and execute if token available
        actions = await maybe_execute_gitlab_action(message, text)

        return {"text": text, "actions": actions, "model": "gemini-2.0-flash"}

    except Exception as e:
        print(f"[agent] Gemini error: {e}")
        return {"text": f"Agent error: {str(e)}", "actions": [], "model": "error"}


async def maybe_execute_gitlab_action(query: str, response_text: str) -> list:
    """If query asks to create issue and token exists, do it for real."""
    if not GITLAB_TOKEN:
        return []

    q = query.lower()
    actions = []

    if "create" in q and "issue" in q:
        # Extract title from response
        lines = response_text.split("\n")
        title = next((l for l in lines if l.strip()), "RepoTerrain: Auto-generated issue")
        title = title.strip("# *").strip()[:80]

        result = await create_gitlab_issue(title, response_text)
        if result:
            actions.append({"tool": "create_gitlab_issue", "result": result})

    return actions


async def create_gitlab_issue(title: str, description: str) -> Optional[str]:
    if not GITLAB_TOKEN:
        return None
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                "https://gitlab.com/api/v4/issues",
                headers={"PRIVATE-TOKEN": GITLAB_TOKEN},
                json={"title": title, "description": description},
            )
            data = r.json()
            return data.get("web_url", "Issue created")
    except Exception as e:
        print(f"[agent] GitLab issue error: {e}")
        return None


def demo_response(query: str, selected_file: Optional[str], terrain_data: dict) -> dict:
    """Fallback responses when no API key is set."""
    total = len(terrain_data.get("nodes", [])) if terrain_data else 0
    q = query.lower() if query else ""

    if selected_file and ("explain" in q or "what" in q or not q):
        text = (
            f"**{selected_file.split('/')[-1]}** is positioned in a semantically rich cluster. "
            f"Based on its location in the terrain, it shares concepts with nearby files. "
            f"Its heat signature indicates moderate recent activity.\n\n"
            f"To get real AI analysis, add your Gemini API key to the `.env` file."
        )
    elif "issue" in q:
        text = "I'd create a GitLab issue titled **'Tech Debt: Cold Zone Review'** for the low-activity files. Add your GITLAB_TOKEN to `.env` to enable real issue creation."
    elif "sprint" in q or "week" in q or "commit" in q:
        text = f"I can see {total} files in this terrain. To query real commit history, connect your GitLab token. The hottest clusters (red/orange) represent your most recently active modules."
    elif "onboard" in q:
        text = f"**Onboarding Guide for this repo:**\n\n1. Start at the **red peaks** — your core modules\n2. Blue zones are legacy/stable code\n3. Cluster labels show module boundaries\n4. Click any card to drill into a file\n\nThis terrain has {total} files across multiple semantic clusters."
    else:
        text = (
            f"I can see **{total} files** in this repository terrain. "
            f"The clusters show semantic groupings — files that do similar things land near each other. "
            f"Red/orange = active code, blue = cold/legacy.\n\n"
            f"Add your `GEMINI_API_KEY` to `.env` for real AI responses."
        )

    return {"text": text, "actions": [], "model": "demo-mode"}
