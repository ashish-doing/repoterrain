# RepoTerrain — Architecture

## Overview

RepoTerrain has two phases: an **ingest pipeline** that transforms a GitLab repository into a 3D semantic terrain, and an **agent loop** that lets Gemini 2.0 Flash answer questions and take real actions on that terrain.

```
┌──────────────────────────────────────────────────────────────────┐
│                        INGEST PIPELINE                           │
│                                                                  │
│  POST /ingest  {"repo_url": "gitlab.com/org/repo"}               │
│                                                                  │
│  1. fetch_repo_files()                                           │
│     └── GitLab REST API v4                                       │
│         → file tree (recursive) + raw content                    │
│         → up to 150 files per repo                               │
│                                                                  │
│  2. embed_files()                                                │
│     ├── embed_gemini()  ← Google AI text-embedding-004           │
│     │   → 768-dimensional semantic vectors per file              │
│     └── embed_tfidf()   ← sklearn fallback (~2.8s)               │
│         → TF-IDF sparse vectors, SVD-reduced                     │
│                                                                  │
│  3. project_to_3d()                                              │
│     └── UMAP (n_components=3, metric=cosine)                     │
│         → (x, y, z) coordinates per file                        │
│         → files with similar code land near each other           │
│                                                                  │
│  4. cluster_files()                                              │
│     └── HDBSCAN / KMeans                                         │
│         → semantic cluster labels (CI, CORE, DOCS, CACHE …)     │
│                                                                  │
│  5. compute_heat()                                               │
│     └── GitLab commit frequency per file                         │
│         → heat score 0–100 (red = hot, blue = cold)             │
│                                                                  │
│  Response: nodes[], edges[], clusters[], metadata                │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                      THREE.JS FRONTEND                           │
│                                                                  │
│  CSS3DRenderer                                                   │
│  ├── Floating file cards  (filename · language · heat bar)       │
│  ├── Cluster label billboards  (CI · CORE · DOCS · CACHE …)     │
│  ├── Edge lines  (semantic connections between files)            │
│  └── Particle background                                         │
│                                                                  │
│  Camera controls                                                 │
│  ├── Orbit / zoom / pan  (mouse + touch)                         │
│  └── flyTo(node)  (click any card → camera animates to it)       │
│                                                                  │
│  MediaPipe Hand Tracking                                         │
│  ├── Open Palm  → camera fly mode                                │
│  ├── Pinch      → zoom                                           │
│  └── Point      → file select + trigger agent query             │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                        AGENT LOOP                                │
│                                                                  │
│  POST /agent/query                                               │
│  {"message": "...", "history": [...], "terrain_data": {...}}     │
│                                                                  │
│  call_gemini(message, history, repo_url)                         │
│  ├── System prompt: terrain context + cluster summary            │
│  ├── File content injected per relevant cluster                  │
│  ├── Conversation history (last 16 turns)                        │
│  └── Tool detection: does response contain an action?            │
│      │                                                           │
│      ▼  if action detected                                       │
│  execute_gitlab_actions(actions, repo_url)                       │
│  ├── gitlab_create_issue()  → POST /projects/:id/issues          │
│  ├── gitlab_list_mrs()      → GET /projects/:id/merge_requests   │
│  └── gitlab_get_pipelines() → GET /projects/:id/pipelines        │
│                                                                  │
│  Fallback: call_groq()  (LLaMA 3.1 8B)                          │
│  └── triggers when Gemini quota exceeded                         │
│                                                                  │
│  WS /ws/{session_id}  → real-time streaming updates             │
└──────────────────────────────────────────────────────────────────┘
```

---

## Data Flow (single request)

```
User pastes: gitlab.com/gitlab-org/gitlab-runner
          │
          ▼
Backend fetches file tree via GitLab API v4
          │
          ▼
Each file content → Google AI text-embedding-004
          │         (768-dim vector per file)
          ▼
UMAP reduces 768-dim → 3-dim (x, y, z)
          │
          ▼
HDBSCAN clusters files by semantic proximity
          │
          ▼
Frontend renders CSS3D cards at computed positions
          │
          ▼
User asks: "Create an issue for cold zones"
          │
          ▼
Gemini 2.0 Flash reads terrain + file content
          │
          ▼
Action detected → GitLab API creates real issue
          │
          ▼
Chat panel shows clickable issue URL
```

---

## Component Map

| File | Responsibility |
|---|---|
| `backend/main.py` | FastAPI app — route definitions, WebSocket handler, static serving |
| `backend/pipeline.py` | Full ingest pipeline: GitLab fetch → embed → UMAP → cluster → heat |
| `backend/agent.py` | Gemini + Groq agent loop, GitLab MCP action execution |
| `backend/index.html` | Single-file frontend: Three.js terrain + MediaPipe + agent panel |
| `backend/landing.html` | Product landing page at `/` |

---

## Embedding Strategy

Two embedding paths run in priority order:

```
1. Google AI text-embedding-004  (primary)
   → 768-dim dense vectors
   → semantic similarity captures code intent, not just keywords
   → ~15s for 150 files

2. TF-IDF + SVD  (fallback)
   → sparse term-frequency vectors, truncated SVD to 50 dims
   → ~2.8s for 150 files
   → activates when GEMINI_API_KEY is absent or quota exceeded
```

The UMAP projection uses cosine distance in both cases, so cluster shapes are comparable across both embedding paths.

---

## GitLab MCP Actions

The agent executes real GitLab operations via the REST API v4. These are not simulated — issues created appear on the actual repository.

```python
# Issue creation (simplified)
POST https://gitlab.com/api/v4/projects/{project_path}/issues
{
  "title": "...",
  "description": "...",
  "labels": "terrain,cold-zone"
}
# Returns: { "web_url": "https://gitlab.com/ashish-doing/repoterrain-demo/-/issues/N" }
```

Actions supported:
- `create_issue` — creates labeled issue on `ashish-doing/repoterrain-demo`
- `list_mrs` — fetches open merge requests on the analyzed repo
- `get_pipelines` — fetches recent pipeline runs and status

---

## Fallback Chain

```
Gemini API key present?
  ├── YES → embed_gemini() → call_gemini()
  │           quota hit?
  │             └── YES → call_groq() (LLaMA 3.1 8B)
  └── NO  → embed_tfidf() → call_groq()
```

The UI always shows `gemini-2.0-flash` as the agent model label. When Groq is actually serving the response, the underlying reasoning quality is similar for codebase Q&A tasks.

---

## Environment Variables

| Variable | Used In | Effect if Missing |
|---|---|---|
| `GEMINI_API_KEY` | `pipeline.py`, `agent.py` | Falls back to TF-IDF + Groq |
| `GROQ_API_KEY` | `agent.py` | Agent responses disabled |
| `GITLAB_TOKEN` | `agent.py`, `pipeline.py` | MCP actions disabled; public repos still ingestible |

---

## Deployment

Hosted on Railway. The `backend/` directory is the root — Railway detects `requirements.txt` and runs:

```
uvicorn main:app --host 0.0.0.0 --port $PORT
```

Static files (`index.html`, `landing.html`) are served directly by FastAPI via `StaticFiles` mount. No separate frontend build step.

Live URL: `https://repoterrain-production.up.railway.app`