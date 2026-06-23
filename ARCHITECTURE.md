# RepoTerrain — Architecture

## Overview

RepoTerrain has two phases: an **ingest pipeline** that turns a GitLab repository into a 3D semantic terrain, and an **agent loop** that lets Gemini 2.0 Flash answer questions about that terrain and take real actions on GitLab via MCP-style REST calls.

---

## System Diagram

```mermaid
flowchart TD
    subgraph CLIENT["🖥️ FRONTEND — index.html"]
        UI["Three.js + CSS3DRenderer\n━━━━━━━━━━━━━━━\n• floating file cards\n• heat-colored terrain\n• edge lines between similar files"]
        HAND["MediaPipe Hand Tracking\n━━━━━━━━━━━━━━━\n• open palm → fly/orbit\n• pinch → zoom\n• point → select file"]
        PANEL["Agent Panel\n━━━━━━━━━━━━━━━\n• chat with Gemini\n• selected file / cluster context\n• action results (issue links, MRs)"]
        HAND -->|controls| UI
        UI -->|select node| PANEL
    end

    subgraph API["⚙️ BACKEND — main.py (FastAPI)"]
        ING["POST /ingest\n━━━━━━━━━━━━━━━\nrepo_url, gitlab_token,\nmax_files"]
        AGT["POST /agent/query\n━━━━━━━━━━━━━━━\nsession_id, query,\nselected_file, selected_cluster"]
        WS["WS /ws/{session_id}\n━━━━━━━━━━━━━━━\nreal-time agent responses"]
        CACHE["terrain_cache\n━━━━━━━━━━━━━━━\nin-memory session store"]
        ING --> CACHE
        AGT --> CACHE
        WS --> CACHE
    end

    subgraph PIPE["🛰️ pipeline.py"]
        FETCH["fetch_repo_files()\n━━━━━━━━━━━━━━━\nGitLab REST API v4\nfile tree + raw content\nup to 150 files"]
        EMBED["embed_files()\n━━━━━━━━━━━━━━━\nGemini text-embedding-004\nor TF-IDF fallback"]
        UMAPB["project_to_3d()\n━━━━━━━━━━━━━━━\nUMAP, 3 components,\ncosine metric"]
        META["compute_metadata()\n━━━━━━━━━━━━━━━\nheat score, language,\nclusters, edges"]
        FETCH --> EMBED --> UMAPB --> META
    end

    subgraph AGENT["🤖 agent.py"]
        CTX["build_context()\n━━━━━━━━━━━━━━━\nterrain stats + file content\n+ selected cluster"]
        GEM["call_gemini()\n━━━━━━━━━━━━━━━\nGemini 2.0 Flash\nsystem prompt + history"]
        GROQ["call_groq()\n━━━━━━━━━━━━━━━\nllama-3.1-8b-instant\nfallback model"]
        ACT["execute_gitlab_actions()\n━━━━━━━━━━━━━━━\ncreate_issue · list_mrs\nget_pipelines"]
        CTX --> GEM
        GEM -->|quota / error| GROQ
        GEM --> ACT
        GROQ --> ACT
    end

    subgraph GITLAB["🦊 GITLAB PLATFORM"]
        REPO["Target Repo\n━━━━━━━━━━━━━━━\nrepository/tree\nrepository/files/*/raw"]
        DEMO["ashish-doing/repoterrain-demo\n━━━━━━━━━━━━━━━\nissues created here"]
        MRAPI["merge_requests\npipelines API"]
    end

    UI -->|paste repo URL| ING
    PANEL -->|ask question| AGT
    PANEL -->|gesture select| WS

    ING --> FETCH
    META -->|nodes, edges, meta| ING
    ING -->|terrain JSON| UI

    AGT --> CTX
    ACT -->|create issue| DEMO
    ACT -->|list MRs / pipelines| MRAPI
    FETCH -->|tree + files| REPO

    GEM -->|response + actions| AGT
    AGT -->|text, actions, model| PANEL
```

---

## Request Flow — Ingest

```mermaid
sequenceDiagram
    participant User
    participant UI as Frontend (index.html)
    participant API as FastAPI (main.py)
    participant PL as pipeline.py
    participant GL as GitLab API v4
    participant G as Gemini Embeddings

    User->>UI: Paste GitLab repo URL
    UI->>API: POST /ingest {repo_url, max_files}
    API->>PL: run_pipeline()
    PL->>GL: GET /projects/:id (default branch)
    PL->>GL: GET /repository/tree (paginated, recursive)
    PL->>GL: GET /repository/files/*/raw (batches of 10)
    GL-->>PL: file contents (up to 150 files)
    PL->>G: embedContent (text-embedding-004) per file
    G-->>PL: 768-dim vectors (or TF-IDF fallback if no key)
    PL->>PL: UMAP -> 3D coords (cosine, n_components=3)
    PL->>PL: compute heat, language, clusters, edges
    PL-->>API: {session_id, nodes, edges, meta, files}
    API-->>UI: {session_id, nodes, edges, meta}
    UI->>UI: render CSS3D terrain
```

---

## Request Flow — Agent Query

```mermaid
sequenceDiagram
    participant User
    participant UI as Frontend (index.html)
    participant API as FastAPI (main.py)
    participant AG as agent.py
    participant Gemini as Gemini 2.0 Flash
    participant Groq as Groq Llama 3.1
    participant GL as GitLab API v4

    User->>UI: "Create an issue for cold zones"
    UI->>API: POST /agent/query {session_id, query}
    API->>AG: agent_query(query, terrain_data)
    AG->>AG: classify_intent() -> "create_issue"
    AG->>AG: build_context() + build_message()
    AG->>Gemini: generateContent (system prompt + history)
    alt Gemini unavailable / quota error
        AG->>Groq: chat/completions (llama-3.1-8b-instant)
        Groq-->>AG: response text
    else Gemini OK
        Gemini-->>AG: response text
    end
    AG->>GL: POST /projects/:id/issues (title, description, labels)
    GL-->>AG: {web_url, iid, title}
    AG-->>API: {text, actions, model, reasoning}
    API-->>UI: agent response
    UI->>UI: render reply + clickable issue link
```

---

## Component Map

| File | Responsibility |
|---|---|
| `backend/main.py` | FastAPI app — `/`, `/app`, `/health`, `/ingest`, `/agent/query`, `/ws/{session_id}`, `/terrain/{session_id}` |
| `backend/pipeline.py` | GitLab fetch -> embed -> UMAP -> heat/language/cluster/edge computation -> terrain JSON |
| `backend/agent.py` | Intent classification, context building, Gemini/Groq calls, GitLab MCP action execution |
| `backend/index.html` | Single-file frontend — Three.js terrain, MediaPipe hand tracking, agent chat panel |
| `backend/landing.html` | Product landing page served at `/` |
| `docs/index.html` | GitHub Pages mirror of the landing page |

---

## Embedding Strategy

```mermaid
flowchart LR
    A["files dict\n{path: content[:2000]}"] --> B{"GEMINI_API_KEY set?"}
    B -->|yes| C["embed_gemini()\n━━━━━━━━━━━━━━━\ntext-embedding-004\n768-dim per file\nbatched, 0.5s pause / 10 files"]
    B -->|no| D["embed_tfidf()\n━━━━━━━━━━━━━━━\nTfidfVectorizer\nmax_features=384\nstop_words=english"]
    C --> E["UMAP(n_components=3,\nmetric=cosine,\nn_neighbors=min(15,n-1))"]
    D --> E
    E --> F["normalized x,y,z in [-1, 1]"]
```

If a Gemini embed call fails for a single file, `pipeline.py` substitutes a random 768-dim vector for that file rather than failing the whole batch — so one bad file never blocks terrain generation.

---

## Heat & Cluster Computation

`compute_metadata()` derives, per file:

- **`heat`** (0.05–1.0) — base 0.2, boosted for filenames matching core/entry patterns (`main`, `index`, `app`, `server`, `router`, `config`, `auth`, `core`, `client`, `engine`, ...), reduced for `test`, `spec`, `mock`, `readme`, `changelog`, etc., plus a contribution from file size and tree depth (shallower files run hotter). Heat is a proxy for activity — the GitLab API does not expose commit frequency without authentication, so filename role and size are used as signals instead.
- **`language`** — derived from file extension via a fixed extension map.
- **`size`** — `min(content_length / 5000, 1.0)`.

`compute_clusters()` groups files by parent directory name (falling back to language when a file is at the root), discarding clusters with fewer than 2 members.

`compute_edges()` connects each node to its 3 nearest neighbours in 3D space, capped at `max_dist = 0.35`, giving the terrain its semantic-connection lines.

---

## GitLab MCP Gateway

The official `gitlab.com/api/v4/mcp` server requires GitLab Premium/Ultimate with Duo enabled — not available on the free-tier `ashish-doing/repoterrain-demo` project this app targets. RepoTerrain instead self-hosts the open-source community server [`zereight/gitlab-mcp`](https://github.com/zereight/gitlab-mcp) (154 tools, MIT license) as a second Railway service, in **Streamable HTTP + Remote Authorization** mode — this is genuine MCP (JSON-RPC 2.0 over Streamable HTTP, `MCP-Protocol-Version: 2025-03-26`), not a REST shim, and works on any GitLab tier.

```mermaid
flowchart LR
    AG["agent.py\nclassify_intent()"] -->|"JSON-RPC 2.0\ntools/call\nPrivate-Token: <PAT>"| GW["mcp-gateway\n(Railway service)\nzereight/gitlab-mcp\nStreamable HTTP"]
    GW -->|"create_issue\nlist_merge_requests\nlist_pipelines"| GL["gitlab.com/api/v4\nashish-doing/repoterrain-demo"]
    AG -->|"if gateway unreachable\nor unconfigured"| REST["REST API v4\n(direct fallback)"]
    REST --> GL
```

| Intent (from `classify_intent`) | MCP Tool | REST Fallback |
|---|---|---|
| `create_issue` | `create_issue` | `POST /projects/ashish-doing%2Frepoterrain-demo/issues` |
| `list_mrs` | `list_merge_requests` | `GET /merge_requests?state=opened&per_page=5` |
| `get_pipelines` | `list_pipelines` | `GET /projects/:id/pipelines?per_page=5` |

```python
# MCP tools/call (simplified) — sent to GITLAB_MCP_GATEWAY_URL
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "create_issue",
    "arguments": {
      "project_id": "ashish-doing/repoterrain-demo",
      "title": "...",
      "description": "🤖 Created by RepoTerrain AI Agent (via GitLab MCP)\n\n...",
      "labels": ["repoterrain"]  # or tech-debt/low-priority, needs-review/high-priority
    }
  }
}
# Headers: Private-Token: <GITLAB_TOKEN>, MCP-Protocol-Version: 2025-03-26
```

If `GITLAB_MCP_GATEWAY_URL` is unset, or the gateway returns a non-2xx / errors / is unreachable, `agent.py` falls back to direct REST API v4 calls — every action still completes, but `via` in the response will read `gitlab-rest-api` instead of `gitlab-mcp-gateway`, so the response is fully transparent about which path served the request.

Issue titles are extracted from the agent's first non-bullet response line; labels are chosen from query keywords (`cold`/`legacy` → `tech-debt, low-priority`, `hot`/`complex` → `needs-review, high-priority`, otherwise `repoterrain`).

See [`mcp-gateway/`](./mcp-gateway/) for the gateway's Dockerfile and Railway deployment config.

---

## Agent Fallback Chain

```mermaid
flowchart TD
    Q["User query"] --> I["classify_intent()"]
    I --> K{"GEMINI_API_KEY set?"}
    K -->|yes| GM["call_gemini()\ngemini-2.0-flash"]
    K -->|no, GROQ_API_KEY set| GR["call_groq()\nllama-3.1-8b-instant"]
    K -->|no keys| DM["demo_response()\nrule-based, terrain stats only"]
    GM -->|empty response / API error| GR2{"GROQ_API_KEY set?"}
    GR2 -->|yes| GR
    GR2 -->|no| ERR["return error message"]
    GM --> OUT["execute_gitlab_actions()"]
    GR --> OUT
    DM --> OUT2["actions = []"]
    OUT --> RESP["{text, actions, model, reasoning}"]
    OUT2 --> RESP
```

Each session keeps its last 16 conversation turns (`history[-16:]`) so follow-up questions retain context across both Gemini and Groq calls.

---

## Environment Variables

| Variable | Used In | Effect if Missing |
|---|---|---|
| `GEMINI_API_KEY` | `pipeline.py` (embeddings), `agent.py` (chat) | Falls back to TF-IDF embeddings and Groq/demo agent |
| `GROQ_API_KEY` | `agent.py` | Agent falls back to rule-based `demo_response()` |
| `GITLAB_TOKEN` | `agent.py`, `pipeline.py` | GitLab actions disabled; private repos inaccessible; public repos still ingestible |
| `GITLAB_MCP_GATEWAY_URL` | `agent.py` | Falls back to direct REST API v4 calls (still functional, `via: gitlab-rest-api`) |

---

## Deployment

Two Railway services:

**1. Main backend** (`backend/`) — built via Railway's Railpack builder, which reads `backend/.python-version` (3.12.3) and `backend/requirements.txt`:

```
uvicorn main:app --host 0.0.0.0 --port $PORT
```

`landing.html` and `index.html` are served directly by FastAPI (`/` and `/app`) — no separate frontend build step. `deploy.sh` provides an alternative Cloud Run deployment path using Docker + `gcloud run deploy`.

**2. MCP gateway** (`mcp-gateway/`) — Dockerfile-based service running `zereight/gitlab-mcp` in Streamable HTTP + Remote Authorization mode. The main backend's `GITLAB_MCP_GATEWAY_URL` env var points at this service's `/mcp` endpoint. See [`mcp-gateway/README.md`](./mcp-gateway/README.md).

Live URL: <https://repoterrain.onrender.com>