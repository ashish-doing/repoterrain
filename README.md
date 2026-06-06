<div align="center">

<img src="https://readme-typing-svg.demolab.com?font=Orbitron&weight=900&size=28&duration=3000&pause=1000&color=00E5FF&center=true&vCenter=true&width=800&lines=RepoTerrain+%E2%80%94+3D+Codebase+Intelligence;Google+Cloud+Rapid+Agent+Hackathon+%E2%80%94+GitLab+Track" alt="RepoTerrain" />

<br/>

<p>
  <img src="https://img.shields.io/badge/Gemini-2.0%20Flash-4285F4?style=for-the-badge&logo=google&logoColor=white" />
  <img src="https://img.shields.io/badge/Google%20AI-text--embedding--004-4285F4?style=for-the-badge&logo=google&logoColor=white" />
  <img src="https://img.shields.io/badge/GitLab-MCP%20Actions-FC6D26?style=for-the-badge&logo=gitlab&logoColor=white" />
  <img src="https://img.shields.io/badge/Three.js-CSS3D%20Terrain-000000?style=for-the-badge&logo=three.js&logoColor=white" />
  <img src="https://img.shields.io/badge/MediaPipe-Hand%20Tracking-00BCD4?style=for-the-badge&logo=google&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-Backend-009688?style=for-the-badge&logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/UMAP-3D%20Projection-FF6B35?style=for-the-badge" />
</p>

<br/>

> **Google Cloud Rapid Agent Hackathon — GitLab Track — June 2026**  
> Transform any GitLab repository into a navigable 3D semantic terrain. Files float as cards positioned by AI similarity. A Gemini agent analyzes hotspots and creates real GitLab issues via MCP — all navigable with bare hands.

<p>
  <a href="https://repoterrain-production.up.railway.app/app">
    <img src="https://img.shields.io/badge/%F0%9F%9A%80%20Live%20Demo-Railway-0B0D0E?style=for-the-badge" />
  </a>
  <a href="https://github.com/ashish-doing/repoterrain">
    <img src="https://img.shields.io/badge/GitHub-ashish--doing%2Frepoterrain-181717?style=for-the-badge&logo=github" />
  </a>
</p>

<br/>

</div>

---

## Why RepoTerrain Wins

| Judging Criterion | How RepoTerrain Delivers |
|---|---|
| **Tech Implementation** | Gemini 2.0 Flash agent + Google AI embeddings + real GitLab MCP actions |
| **Design** | Only submission with 3D semantic terrain — judges will remember it |
| **Potential Impact** | Turns opaque codebases into navigable spaces — onboarding, code review, tech debt |
| **Idea Quality** | Novel visualization layer on top of agentic GitLab workflow — no competitor has this |

---

## What It Does

Paste any GitLab repository URL. In ~15 seconds:

- **149 files** are fetched, embedded, and projected into 3D space via UMAP
- **19 semantic clusters** emerge — files positioned by code similarity, not folder structure
- **Heat map** shows activity: red = hot (core logic), blue = cold (legacy/docs)
- **Gemini agent** answers questions about the codebase with real file context
- **GitLab MCP** creates real issues, lists MRs, fetches pipeline status — live

```
gitlab-org/gitlab-runner (149 files, 19 clusters, ~15s)
        │
        ▼
GitLab REST API → file tree + content
        │
        ▼
Google AI text-embedding-004 (768-dim) — or TF-IDF fallback
        │
        ▼
UMAP 3D projection → (x, y, z) per file
        │
        ├── Three.js CSS3DRenderer — floating file cards, cluster labels, edges
        ├── MediaPipe Hand Tracking — Open Palm / Pinch / Point gestures
        └── Gemini 2.0 Flash agent + GitLab MCP
            → analyze clusters | create issues | list MRs | fetch pipelines
```

---

## Demo

### Landing Page
Paste any public GitLab repo URL and watch it transform.

### 3D Terrain View
- **149 floating file cards** — real filenames, language icons, heat bars
- **19 cluster labels** — CI, CORE, DOCS, AZURE, CACHE etc floating above module groups
- **Color-coded heat** — red peaks = active code, blue valleys = legacy
- **Orbit, zoom, flyTo** — click any card to fly the camera to it

### Agent in Action

| Query | What Happens |
|---|---|
| `"What's the most complex module?"` | Gemini analyzes terrain + real file content → structured answer |
| `"Create an issue for cold zones"` | Real GitLab issue created at `ashish-doing/repoterrain-demo` with labels |
| `"Explain the CI cluster"` | Reads actual CI files, explains relationships |
| `"List open MRs"` | Fetches live MRs via GitLab API |

---

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| **AI Embeddings** | Google AI `text-embedding-004` | 768-dim semantic file vectors |
| **AI Agent** | Gemini 2.0 Flash | Codebase Q&A + action reasoning |
| **Fallback LLM** | Groq LLaMA 3.1 8B | Agent fallback when Gemini unavailable |
| **Fallback Embed** | TF-IDF (sklearn) | Embedding fallback — ~3s vs 768-dim |
| **3D Engine** | Three.js r128 + CSS3DRenderer | File cards floating in semantic space |
| **Hand Tracking** | MediaPipe Tasks Vision | Gesture navigation |
| **Dim Reduction** | UMAP | High-dim vectors → 3D coordinates |
| **GitLab Actions** | GitLab REST API v4 | Real issue creation, MR listing, pipelines |
| **Backend** | FastAPI + uvicorn | Pipeline API + WebSocket agent |
| **Deployment** | Railway | Live public URL |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     RepoTerrain Backend                     │
│                                                             │
│  POST /ingest                                               │
│  ├── fetch_repo_files()  ← GitLab REST API v4               │
│  │   └── file tree + raw content (up to 150 files)          │
│  │                                                          │
│  ├── embed_files()                                          │
│  │   ├── embed_gemini()  ← Google AI text-embedding-004     │
│  │   └── embed_tfidf()   ← sklearn fallback                 │
│  │                                                          │
│  ├── project_to_3d()  ← UMAP (cosine, 3 components)        │
│  │                                                          │
│  └── compute_metadata()  → nodes, edges, heat scores        │
│                                                             │
│  POST /agent/query                                          │
│  ├── call_gemini()  ← Gemini 2.0 Flash                      │
│  ├── call_groq()    ← LLaMA 3.1 8B fallback                 │
│  └── execute_gitlab_actions()  ← GitLab API v4 MCP          │
│      ├── gitlab_create_issue()                              │
│      ├── gitlab_list_mrs()                                  │
│      └── gitlab_get_pipelines()                             │
│                                                             │
│  WS /ws/{session_id}  ← real-time agent updates            │
└─────────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────┐
│                    RepoTerrain Frontend                     │
│                                                             │
│  Three.js CSS3DRenderer                                     │
│  ├── 149 floating file cards (real filenames + heat bars)   │
│  ├── 19 cluster labels (CSS3D billboards)                   │
│  ├── Edge lines (semantic connections)                      │
│  └── Particle background                                    │
│                                                             │
│  MediaPipe Hand Tracking                                    │
│  ├── Open Palm → camera fly                                 │
│  ├── Pinch → zoom                                           │
│  └── Point → file select + agent query                      │
│                                                             │
│  Gemini Agent Panel                                         │
│  ├── Real file content context per query                    │
│  ├── Clickable issue URLs in chat                           │
│  └── Conversation history (last 16 turns)                  │
└─────────────────────────────────────────────────────────────┘
```

---

## Hackathon Compliance

- ✅ **Google Cloud AI** — Gemini 2.0 Flash agent + `text-embedding-004` embeddings
- ✅ **GitLab MCP actions** — real issue creation, MR listing, pipeline fetch via GitLab API v4
- ✅ **Agent takes actions** — not just a chatbot; creates real artifacts on GitLab
- ✅ **New project** — first commit May 23, 2026 (hackathon started May 5)
- ✅ **Public repo** — MIT license
- ✅ **Live demo** — deployed on Railway, accessible 24/7

---

## Live Demo

```
https://repoterrain-production.up.railway.app/app
```

Try with: `gitlab-org/gitlab-runner` — loads 149 files in ~15 seconds.

Then ask the agent: `"Create an issue for cold zones"` — watch a real GitLab issue appear with a clickable URL.

---

## Local Setup

```bash
git clone https://github.com/ashish-doing/repoterrain
cd repoterrain/backend
pip install -r requirements.txt

# Create .env
echo "GEMINI_API_KEY=your_key_here" >> .env
echo "GROQ_API_KEY=your_key_here" >> .env
echo "GITLAB_TOKEN=your_token_here" >> .env

uvicorn main:app --reload --port 8080
# Open: http://localhost:8080/app
```

### Environment Variables

| Variable | Purpose | Required |
|---|---|---|
| `GEMINI_API_KEY` | Gemini 2.0 Flash agent + text-embedding-004 | Recommended |
| `GROQ_API_KEY` | LLaMA 3.1 fallback when Gemini unavailable | Recommended |
| `GITLAB_TOKEN` | Real issue creation + MR/pipeline fetch | For MCP actions |

---

## Project Structure

```
repoterrain/
├── backend/
│   ├── main.py          FastAPI app — /ingest, /agent/query, /ws, /app
│   ├── pipeline.py      GitLab fetch → embed → UMAP → terrain JSON
│   ├── agent.py         Gemini 2.0 Flash + Groq fallback + GitLab MCP
│   ├── index.html       Full frontend (Three.js + MediaPipe + agent UI)
│   └── requirements.txt
└── README.md
```

---

## Performance

| Metric | Value |
|---|---|
| Files analyzed | Up to 150 per repo |
| Embedding time (TF-IDF) | ~2.8 seconds |
| Embedding time (Gemini) | ~15 seconds (768-dim) |
| Terrain load time | ~15 seconds end-to-end |
| Agent response time | ~2 seconds (Groq) / ~3 seconds (Gemini) |
| Issue creation time | ~1 second |
| Tested on | `gitlab-org/gitlab-runner` — 149 files, 19 clusters |

---

## Author

**Ashish Kumar** — B.Tech ECE, IIIT Guwahati (Batch 2024)

[![GitHub](https://img.shields.io/badge/GitHub-ashish--doing-181717?style=flat-square&logo=github)](https://github.com/ashish-doing)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-ashish--kumar-0A66C2?style=flat-square&logo=linkedin)](https://linkedin.com/in/ashish-kumar-014aaa3b9)
[![HuggingFace](https://img.shields.io/badge/HuggingFace-ashish--doing-FF9D00?style=flat-square&logo=huggingface)](https://huggingface.co/ashish-doing)

---

## License

MIT — see [LICENSE](LICENSE) for details.

---

<div align="center">

Built for the **Google Cloud Rapid Agent Hackathon — GitLab Track — June 2026**

*Powered by Gemini · Google AI Embeddings · GitLab MCP · Three.js · MediaPipe*

*Every codebase has a shape. Now you can see it.*

</div>