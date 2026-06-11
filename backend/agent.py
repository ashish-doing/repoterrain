"""
RepoTerrain Agent — Gemini 2.0 Flash + GitLab MCP Actions
Google Cloud Rapid Agent Hackathon — GitLab Track
"""
from dotenv import load_dotenv
load_dotenv()

import os
import re
import json
import httpx
import asyncio
from typing import Optional

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GROQ_API_KEY   = os.environ.get("GROQ_API_KEY", "")   # quota fallback — transparent
GITLAB_TOKEN   = os.environ.get("GITLAB_TOKEN", "")

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
GROQ_URL   = "https://api.groq.com/openai/v1/chat/completions"

# GitLab MCP — self-hosted community gateway (zereight/gitlab-mcp)
# The official gitlab.com/api/v4/mcp server requires GitLab Premium/Ultimate
# + Duo, so we run the open-source community MCP server (Streamable HTTP +
# Remote Authorization) as a second Railway service. Same MCP protocol
# (JSON-RPC 2.0, MCP-Protocol-Version 2025-03-26), works on free-tier GitLab.
GITLAB_MCP_GATEWAY_URL = os.environ.get("GITLAB_MCP_GATEWAY_URL", "")

SYSTEM_PROMPT = """You are RepoTerrain's codebase intelligence agent — powered by Google Gemini.
You analyze GitLab repositories visualized as a live 3D semantic terrain.

Each file is a floating card. Position = semantic similarity (UMAP). Color = activity heat.
Clusters = functionally related modules. Edges = semantic connections.

RESPONSE FORMAT (always follow this exactly):
🎯 **[Module or File Name]**
• Why: [one specific reason — reference actual filenames]
• Key files: [2-3 real filenames from the terrain data]
• Heat: [🔴 Hot / 🟡 Warm / 🔵 Cold] — [heat percentage if known]
• Action: [one concrete, specific next step]

RULES:
- Under 120 words total
- Only reference files that actually exist in the terrain data provided
- Never invent file paths or line numbers
- Be specific and technical — no generic advice
- When multiple files are relevant, name the most important one first

GITLAB ACTIONS:
When asked to create an issue, respond with the format below AND the action will be executed:
✅ **GitLab Issue Created**
• Title: [descriptive title]
• Labels: [label1, label2]
• URL: [shown automatically when token is available]

When asked about pipelines or MRs — describe what you fetched and why it matters for the terrain.

PROACTIVE INSIGHT FORMAT (for auto-triggered terrain summaries):
🗺 **Terrain Overview**
• Hottest: [filename] — [why it's hot]
• Coldest: [filename] — [legacy/docs/rarely touched]
• Start here: [specific file or cluster for a new developer]
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
    repo_url = terrain_data.get("meta", {}).get("repo_url", "")

    session = _sessions.get(session_id, {"history": []})
    history = session.get("history", [])

    # multi-step agentic reasoning
    reasoning_steps = []

    # step 1: classify intent
    intent = classify_intent(query)
    reasoning_steps.append(f"intent: {intent}")

    # step 2: decide model — Gemini primary, Groq quota fallback
    if GEMINI_API_KEY:
        response = await call_gemini(message, history, repo_url)
        reasoning_steps.append("model: gemini-2.0-flash")
    elif GROQ_API_KEY:
        response = await call_groq(message, history, repo_url)
        reasoning_steps.append("model: groq-llama3.1 (quota-fallback)")
    else:
        response = demo_response(query, selected_file, terrain_data)
        reasoning_steps.append("model: demo-fallback")

    # step 3: execute gitlab actions if needed
    if intent in ("create_issue", "list_mrs", "get_pipelines"):
        reasoning_steps.append(f"action: executing {intent} via GitLab MCP")

    history.append({"role": "user",  "parts": [{"text": message}]})
    history.append({"role": "model", "parts": [{"text": response["text"]}]})
    session["history"] = history[-16:]
    _sessions[session_id] = session

    if len(_sessions) > 50:
        _sessions.pop(next(iter(_sessions)))
        
    response["reasoning"] = reasoning_steps
    return response


def classify_intent(query: str) -> str:
    q = query.lower()
    if "create" in q and "issue" in q:
        return "create_issue"
    if "list" in q and ("mr" in q or "merge" in q):
        return "list_mrs"
    if "pipeline" in q or ("ci" in q and "status" in q):
        return "get_pipelines"
    if any(w in q for w in ["explain", "what is", "what does", "how does"]):
        return "explain"
    if any(w in q for w in ["complex", "hot", "active", "important"]):
        return "analyze_heat"
    if any(w in q for w in ["cold", "legacy", "unused", "debt"]):
        return "analyze_cold"
    if any(w in q for w in ["onboard", "start", "begin", "new developer"]):
        return "onboard"
    return "general"


def build_context(terrain_data: dict, selected_file: Optional[str], selected_cluster: Optional[list]) -> dict:
    files = terrain_data.get("files", {})
    nodes = terrain_data.get("nodes", [])
    meta  = terrain_data.get("meta", {})

    cluster_map = {}
    for node in nodes:
        lang = node.get("language", "other")
        cluster_map.setdefault(lang, []).append(node["path"])

    ctx = {
        "total_files":    len(nodes),
        "cluster_count":  meta.get("cluster_count", len(cluster_map)),
        "repo_url":       meta.get("repo_url", ""),
        "clusters":       {k: v[:5] for k, v in list(cluster_map.items())[:6]},
        "selected_file":  None,
        "file_content":   "",
        "cluster_files":  [],
        "hot_files":      meta.get("hot_files") or [n["path"] for n in sorted(nodes, key=lambda x: x.get("heat", 0), reverse=True)[:5]],
        "cold_files":     meta.get("cold_files") or [n["path"] for n in sorted(nodes, key=lambda x: x.get("heat", 0))[:5]],
        "lang_breakdown": meta.get("lang_breakdown", {}),
        "embedding_mode": meta.get("mode", "tfidf"),
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
        f"Total files: {ctx['total_files']} across {ctx['cluster_count']} semantic clusters",
        f"Hottest files: {', '.join(ctx['hot_files'])}",
        f"Coldest files: {', '.join(ctx['cold_files'])}",
        f"Language breakdown: {ctx['lang_breakdown']}",
        f"Embedding mode: {ctx['embedding_mode']}",
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


# ── Gemini 2.0 Flash (primary) ────────────────────────────────

async def call_gemini(message: str, history: list, repo_url: str = "") -> dict:
    contents = list(history[-8:])
    contents.append({"role": "user", "parts": [{"text": message}]})

    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": contents,
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 600},
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(f"{GEMINI_URL}?key={GEMINI_API_KEY}", json=payload)
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
            # quota hit — try Groq fallback
            if GROQ_API_KEY:
                return await call_groq(message, history, repo_url)
            return {"text": f"⚠️ AI unavailable: {error_msg}", "actions": [], "model": "error"}

        actions = await execute_gitlab_actions(message, text, repo_url)
        return {"text": text, "actions": actions, "model": "gemini-2.0-flash"}

    except Exception as e:
        print(f"[agent] Gemini exception: {e}")
        if GROQ_API_KEY:
            return await call_groq(message, history, repo_url)
        return {"text": f"Agent error: {str(e)}", "actions": [], "model": "error"}


# ── Groq fallback (quota recovery only) ──────────────────────

async def call_groq(message: str, history: list, repo_url: str = "") -> dict:
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
        actions = await execute_gitlab_actions(message, text, repo_url)
        return {"text": text, "actions": actions, "model": "groq-llama3.1 (quota-fallback)"}

    except Exception as e:
        print(f"[agent] Groq exception: {e}")
        return {"text": f"Agent error: {str(e)}", "actions": [], "model": "error"}


# ── GitLab MCP + REST Actions ─────────────────────────────────
# Issue creation: tries official GitLab MCP server first, REST v4 as fallback
# MR listing + pipeline fetch: GitLab REST API v4

async def execute_gitlab_actions(query: str, response_text: str, repo_url: str = "") -> list:
    if not GITLAB_TOKEN:
        return []

    q = query.lower()
    actions = []

    if "create" in q and "issue" in q:
        project_path = "ashish-doing%2Frepoterrain-demo"

        lines = [l.strip() for l in response_text.split("\n") if l.strip()]
        title = next(
            (l for l in lines if l and not l.startswith("•") and not l.startswith("-")),
            "RepoTerrain: Codebase Issue"
        )
        title = title.strip("🎯#* ").replace("**", "").strip()[:80]
        if not title:
            title = "RepoTerrain: Auto-generated issue"

        if "cold" in q or "legacy" in q:
            labels = ["tech-debt", "low-priority"]
        elif "hot" in q or "complex" in q:
            labels = ["needs-review", "high-priority"]
        else:
            labels = ["repoterrain"]

        # try MCP first, REST fallback
        result = await gitlab_create_issue_mcp(title, response_text, labels, project_path)
        if not result:
            result = await gitlab_create_issue_rest(title, response_text, labels, project_path)

        if result:
            actions.append({
                "tool": "create_issue",
                "via": result.get("via", "gitlab-api"),
                "result": result,
                "title": title,
            })

    elif "list" in q and ("mr" in q or "merge request" in q):
        result = await gitlab_list_mrs(repo_url)
        if result:
            actions.append({"tool": "list_mrs", "result": result})

    elif "pipeline" in q or ("ci" in q and "status" in q):
        result = await gitlab_get_pipelines(repo_url)
        if result:
            actions.append({"tool": "get_pipelines", "result": result})

    return actions


async def gitlab_create_issue_mcp(title: str, description: str, labels: list, project_path: str) -> Optional[dict]:
    """
    Create a GitLab issue via the self-hosted GitLab MCP gateway
    (zereight/gitlab-mcp, Streamable HTTP + Remote Authorization,
    MCP-Protocol-Version 2025-03-26, JSON-RPC 2.0 tools/call -> create_issue).

    Falls back to REST v4 if the gateway is unreachable or unconfigured.
    """
    if not GITLAB_TOKEN or not GITLAB_MCP_GATEWAY_URL:
        return None

    mcp_payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "create_issue",
            "arguments": {
                "project_id": project_path.replace("%2F", "/"),
                "title": title,
                "description": f"🤖 Created by RepoTerrain AI Agent (via GitLab MCP)\n\n{description}",
                "labels": labels,
            }
        }
    }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(
                GITLAB_MCP_GATEWAY_URL,
                headers={
                    "Private-Token": GITLAB_TOKEN,
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                    "MCP-Protocol-Version": "2025-03-26",
                },
                json=mcp_payload,
            )

            if r.status_code not in (200, 201, 202):
                print(f"[agent] GitLab MCP gateway HTTP {r.status_code} — falling back to REST")
                return None

            # Streamable HTTP can return SSE-framed JSON ("data: {...}") or plain JSON
            raw = r.text.strip()
            if raw.startswith("data:"):
                raw = raw.split("data:", 1)[1].strip().splitlines()[0]
            data = json.loads(raw)

            if "error" in data:
                print(f"[agent] GitLab MCP tool error: {data['error']}")
                return None

            result = data.get("result", {})
            content = result.get("content", [{}])
            text_block = next((c for c in content if c.get("type") == "text"), {})
            issue_data = {}
            try:
                issue_data = json.loads(text_block.get("text", "{}"))
            except Exception:
                pass

            return {
                "url":   issue_data.get("web_url", ""),
                "id":    issue_data.get("iid", ""),
                "title": issue_data.get("title", title),
                "via":   "gitlab-mcp-gateway",
            }

    except Exception as e:
        print(f"[agent] GitLab MCP gateway exception: {e} — falling back to REST")
        return None


async def gitlab_create_issue_rest(title: str, description: str, labels: list, project_path: str) -> Optional[dict]:
    """REST API v4 fallback for issue creation."""
    try:
        url = f"https://gitlab.com/api/v4/projects/{project_path}/issues"
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                url,
                headers={"PRIVATE-TOKEN": GITLAB_TOKEN},
                json={
                    "title": title,
                    "description": f"🤖 Created by RepoTerrain AI Agent\n\n{description}",
                    "labels": ",".join(labels),
                },
            )
            data = r.json()
            return {
                "url":   data.get("web_url", ""),
                "id":    data.get("iid", ""),
                "title": data.get("title", title),
                "via":   "gitlab-rest-api",
            }
    except Exception as e:
        print(f"[agent] GitLab REST issue error: {e}")
        return None


async def call_mcp_tool(tool_name: str, arguments: dict) -> Optional[dict]:
    """Generic MCP gateway call — JSON-RPC 2.0 tools/call over Streamable HTTP."""
    if not GITLAB_TOKEN or not GITLAB_MCP_GATEWAY_URL:
        return None
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
    }
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(
                GITLAB_MCP_GATEWAY_URL,
                headers={
                    "Private-Token": GITLAB_TOKEN,
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                    "MCP-Protocol-Version": "2025-03-26",
                },
                json=payload,
            )
            if r.status_code not in (200, 201, 202):
                return None
            raw = r.text.strip()
            if raw.startswith("data:"):
                raw = raw.split("data:", 1)[1].strip().splitlines()[0]
            data = json.loads(raw)
            if "error" in data:
                print(f"[agent] MCP tool {tool_name} error: {data['error']}")
                return None
            content = data.get("result", {}).get("content", [{}])
            text_block = next((c for c in content if c.get("type") == "text"), {})
            return json.loads(text_block.get("text", "null"))
    except Exception as e:
        print(f"[agent] MCP tool {tool_name} exception: {e}")
        return None


async def gitlab_list_mrs(repo_url: str = "") -> Optional[list]:
    # Extract project path from repo_url e.g. https://gitlab.com/org/repo → org/repo
    project_id = ""
    if repo_url:
        m = re.match(r'https?://[^/]+/(.+)', repo_url.rstrip('/'))
        if m:
            project_id = m.group(1).replace("/", "%2F")

    mcp_args = {"state": "opened", "per_page": 5}
    if project_id:
        mcp_args["project_id"] = project_id.replace("%2F", "/")
    mcp_result = await call_mcp_tool("list_merge_requests", mcp_args)
    if mcp_result:
        items = mcp_result if isinstance(mcp_result, list) else mcp_result.get("items", [])
        if items:
            return [{"title": mr.get("title"), "url": mr.get("web_url"), "state": mr.get("state")} for mr in items[:5]]

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            url = f"https://gitlab.com/api/v4/projects/{project_id}/merge_requests" if project_id else "https://gitlab.com/api/v4/merge_requests"
            r = await client.get(
                url,
                headers={"PRIVATE-TOKEN": GITLAB_TOKEN},
                params={"state": "opened", "per_page": 5},
            )
            data = r.json()
            return [{"title": mr.get("title"), "url": mr.get("web_url"), "state": mr.get("state")} for mr in data[:5]]
    except Exception as e:
        print(f"[agent] GitLab list MRs error: {e}")
        return None


async def gitlab_get_pipelines(repo_url: str = "") -> Optional[list]:
    # Use the analyzed repo's pipeline, fall back to repoterrain-demo
    project_path = "ashish-doing/repoterrain-demo"
    if repo_url:
        m = re.match(r'https?://[^/]+/(.+)', repo_url.rstrip('/'))
        if m:
            project_path = m.group(1)
    mcp_result = await call_mcp_tool("list_pipelines", {"project_id": project_path, "per_page": 5})
    if mcp_result:
        items = mcp_result if isinstance(mcp_result, list) else mcp_result.get("items", [])
        if items:
            return [{"id": p.get("id"), "status": p.get("status"), "ref": p.get("ref")} for p in items[:5]]

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
            pid = projects[0]["id"]
            r2 = await client.get(
                f"https://gitlab.com/api/v4/projects/{pid}/pipelines",
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
    nodes = terrain_data.get("nodes", [])
    meta  = terrain_data.get("meta", {})
    total = len(nodes)
    hot   = meta.get("hot_files") or [n["path"] for n in sorted(nodes, key=lambda x: x.get("heat", 0), reverse=True)[:3]]
    q     = query.lower() if query else ""

    if selected_file:
        name = selected_file.split("/")[-1]
        text = (
            f"🎯 **{name}**\n"
            f"• Why: Central file in its semantic cluster\n"
            f"• Key files: {selected_file}\n"
            f"• Heat: 🟡 Warm\n"
            f"• Action: Add GEMINI_API_KEY for deep AI analysis"
        )
    elif "complex" in q or "hot" in q:
        top = hot[0].split("/")[-1] if hot else "main file"
        text = (
            f"🎯 **{top}**\n"
            f"• Why: Highest activity heat in terrain\n"
            f"• Key files: {', '.join(p.split('/')[-1] for p in hot[:2])}\n"
            f"• Heat: 🔴 Hot\n"
            f"• Action: Review recently changed files in this cluster"
        )
    elif "terrain" in q or "overview" in q or "loaded" in q:
        top = hot[0].split("/")[-1] if hot else "core module"
        text = (
            f"🗺 **Terrain Overview**\n"
            f"• Hottest: {top} — highest activity score\n"
            f"• Coldest: legacy files in outer clusters — low heat, rarely touched\n"
            f"• Start here: navigate to the red cluster first — that's where the core logic lives"
        )
    else:
        text = (
            f"🎯 **{total} files** across {meta.get('cluster_count', '?')} semantic clusters\n"
            f"• Why: Files positioned by code similarity via UMAP\n"
            f"• Key files: {', '.join(p.split('/')[-1] for p in hot[:2]) if hot else 'loading...'}\n"
            f"• Heat: Mixed zones detected\n"
            f"• Action: Click any file card for specific analysis"
        )

    return {"text": text, "actions": [], "model": "demo-mode"}