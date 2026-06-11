<div align="center">

<img src="https://readme-typing-svg.demolab.com?font=Orbitron&weight=900&size=24&duration=3000&pause=1000&color=00E5FF&center=true&vCenter=true&width=900&lines=RepoTerrain+%E2%80%94+3D+Codebase+Intelligence;Google+Cloud+Rapid+Agent+Hackathon+%E2%80%94+GitLab+Track" alt="RepoTerrain" />

<br/>

<p>
  <img src="https://img.shields.io/badge/Gemini-2.0%20Flash-4285F4?style=for-the-badge&logo=google&logoColor=white" />
  <img src="https://img.shields.io/badge/Google%20AI-text--embedding--004-4285F4?style=for-the-badge&logo=google&logoColor=white" />
  <img src="https://img.shields.io/badge/GitLab-MCP%20Actions-FC6D26?style=for-the-badge&logo=gitlab&logoColor=white" />
  <img src="https://img.shields.io/badge/Three.js-CSS3D%20Terrain-000000?style=for-the-badge&logo=three.js&logoColor=white" />
  <img src="https://img.shields.io/badge/MediaPipe-Hand%20Tracking-00BCD4?style=for-the-badge&logo=google&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-Backend-009688?style=for-the-badge&logo=fastapi&logoColor=white" />
</p>

<br/>

<p><strong>Google Cloud Rapid Agent Hackathon — GitLab Track — June 2026</strong></p>

> Transform any GitLab repository into a navigable 3D semantic terrain. Files float as cards positioned by AI similarity. A Gemini agent analyzes the codebase and creates real GitLab issues via MCP — all navigable with bare hands.

<p>
  <a href="https://repoterrain-production.up.railway.app/app">
    <img src="https://img.shields.io/badge/%F0%9F%9A%80%20Live%20App-Railway-0B0D0E?style=for-the-badge" />
  </a>
  <a href="https://repoterrain-production.up.railway.app/">
    <img src="https://img.shields.io/badge/%F0%9F%8C%90%20Landing%20Page-docs-00E5FF?style=for-the-badge" />
  </a>
  <a href="https://github.com/ashish-doing/repoterrain/blob/main/ARCHITECTURE.md">
    <img src="https://img.shields.io/badge/%F0%9F%93%90%20Architecture-deep%20dive-6B4FFF?style=for-the-badge" />
  </a>
  <a href="https://github.com/ashish-doing/repoterrain">
    <img src="https://img.shields.io/badge/GitHub-ashish--doing%2Frepoterrain-181717?style=for-the-badge&logo=github" />
  </a>
</p>

<br/>

</div>

---

## Demo Video

<!-- Replace VIDEO_ID with your YouTube video ID after recording -->
[![RepoTerrain Demo](https://img.youtube.com/vi/VIDEO_ID/maxresdefault.jpg)](https://youtu.be/VIDEO_ID)

▶ **[Watch the demo on YouTube](https://youtu.be/VIDEO_ID)**

> 3-minute walkthrough: terrain load → hand-gesture navigation → agent Q&A → live GitLab issue creation

---

## The Problem

Every developer has stared at a repo they've never seen before and had no idea where to start. File trees tell you nothing about relationships, activity, or importance — onboarding to a new codebase means days of reading and grepping, while tech debt hides invisibly in cold corners of the project.

## What It Does

Paste any public GitLab repository URL. In ~15 seconds:

- **Up to 150 files** are fetched, embedded with Google AI, and projected into 3D space via UMAP
- **Semantic clusters** emerge — files grouped by directory and language proximity, not just raw folder structure
- **Activity heat map** scores each file 0–1 from filename role, size, and tree depth — red/hot = core/active, blue/cold = legacy/docs
- **Gemini 2.0 Flash agent** answers questions with real file content and live terrain stats as context
- **GitLab MCP actions** create real issues (via the official GitLab MCP server, REST v4 fallback), list open MRs, and fetch pipeline status — live, on the actual repo
- **MediaPipe hand tracking** lets you fly, orbit, zoom, and select files with gestures — open palm to fly, pinch to zoom, point to select

```
Tested on gitlab-org/gitlab-runner → 149 files · multiple semantic clusters · ~15s end-to-end
```

---

## Screenshots

| | |
|---|---|
| ![Landing page](./screenshots/landing.png) | ![3D terrain with agent](./screenshots/terrain-agent.png) |
| **Landing page** — paste any GitLab repo URL to begin | **3D semantic terrain + Gemini agent** — agent reads the terrain and creates a real GitLab issue live |
| ![Heat map](./screenshots/heatmap.png) | ![Hand tracking](./screenshots/hand-tracking.png) |
| **Activity heat map** — hottest files, cluster map, and cold zones at a glance | **MediaPipe hand tracking** — navigate the terrain with gestures, no mouse needed |

![GitLab issue created](./screenshots/gitlab-issue.png)
**Live GitLab issue** — created by the agent, not simulated, viewable on `ashish-doing/repoterrain-demo`

---

## Agent in Action

| Query | What Happens |
|---|---|
| `"What's the most complex module?"` | Gemini reads terrain stats + real file content → structured analysis citing actual filenames |
| `"Create an issue for cold zones"` | Real GitLab issue created on `ashish-doing/repoterrain-demo` via MCP (REST fallback), with labels + clickable URL returned in chat |
| `"Explain the CI cluster"` | Reads actual files in the selected cluster, explains how they relate |
| `"List open MRs"` | Fetches live merge requests via the GitLab REST API |
| `"Get pipeline status"` | Fetches recent pipeline runs and their status |

The agent's response format is fixed (module name, why it matters, key files, heat level, next action), so every answer stays grounded in the terrain that's actually on screen — no invented file paths.

---

## How It Works

```mermaid
flowchart LR
    A["INPUT\nGitLab Repo URL\nPOST /ingest"] --> B["1 · Fetch\nfetch_repo_files()\nGitLab REST API v4\nup to 150 files"]
    B --> C["2 · Embed\nembed_files()\ntext-embedding-004\n768-dim per file\n(TF-IDF fallback)"]
    C --> D["3 · Project\nproject_to_3d()\nUMAP, cosine,\nn_neighbors=15"]
    D --> E["4 · Render\nThree.js CSS3D\nfloating cards,\nheat colors, clusters"]
    E --> F["5 · Agent\nGemini 2.0 Flash\nQ&A + GitLab MCP\nissues / MRs / pipelines"]
```

See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full system diagram, request/response sequence flows, and component breakdown.

---

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| **AI Embeddings** | Google AI `text-embedding-004` | 768-dim semantic file vectors |
| **AI Agent** | Gemini 2.0 Flash | Codebase Q&A + action reasoning |
| **Fallback LLM** | Groq `llama-3.1-8b-instant` | Agent fallback when Gemini is unavailable or quota exceeded |
| **Fallback Embed** | TF-IDF + sklearn | Embedding fallback when no Gemini key is set |
| **Dim Reduction** | UMAP (cosine, 3 components) | High-dim vectors → 3D coordinates |
| **3D Engine** | Three.js + CSS3DRenderer | Floating file cards in semantic space |
| **Hand Tracking** | MediaPipe Tasks Vision | Gesture-based terrain navigation |
| **GitLab Actions** | GitLab MCP Server (HTTP, 2025-03-26 spec) + REST API v4 fallback | Issue creation, MR listing, pipeline status |
| **Backend** | FastAPI + uvicorn + WebSockets | Ingest pipeline, agent API, real-time updates |
| **Deployment** | Railway (Nixpacks) | Live public URL |

---

## Hackathon Compliance

| Requirement | Status |
|---|---|
| Google Cloud AI (Gemini agent) | Done — Gemini 2.0 Flash for codebase Q&A and action reasoning |
| Google Cloud AI (embeddings) | Done — `text-embedding-004` for semantic file positioning |
| GitLab MCP actions | Done — official GitLab MCP server (HTTP transport, `POST gitlab.com/api/v4/mcp`) attempted first, REST API v4 fallback ensures reliable issue creation. Real issues created live on `ashish-doing/repoterrain-demo` |
| Agent takes real actions | Done — creates artifacts on GitLab, not just chat responses |
| New project | Done — first commit May 23, 2026 (hackathon opened May 5, 2026) |
| Public repo + live demo | Done — MIT license, deployed on Railway |

---

## Local Setup

```bash
git clone https://github.com/ashish-doing/repoterrain
cd repoterrain/backend
pip install -r requirements.txt

# Create a .env file in backend/
GEMINI_API_KEY=your_key_here
GROQ_API_KEY=your_key_here
GITLAB_TOKEN=your_token_here

uvicorn main:app --reload --port 8080
# Landing page: http://localhost:8080/
# App:          http://localhost:8080/app
```

### Environment Variables

| Variable | Purpose | Effect if Missing |
|---|---|---|
| `GEMINI_API_KEY` | Gemini 2.0 Flash agent + `text-embedding-004` embeddings | Falls back to TF-IDF embeddings and Groq agent |
| `GROQ_API_KEY` | `llama-3.1-8b-instant` agent fallback | Agent falls back to demo-mode responses |
| `GITLAB_TOKEN` | Issue creation, MR/pipeline fetch, private repo access | MCP actions disabled; public repos still ingestible |

---

## Project Structure

```
repoterrain/
├── backend/
│   ├── main.py            FastAPI app — /, /app, /ingest, /agent/query, /ws/{session_id}, /terrain/{id}, /health
│   ├── pipeline.py        GitLab fetch -> embed -> UMAP -> cluster/heat -> terrain JSON
│   ├── agent.py           Gemini 2.0 Flash + Groq fallback + GitLab MCP actions
│   ├── index.html         Frontend - Three.js terrain + MediaPipe hand tracking + agent panel
│   ├── landing.html       Product landing page (served at /)
│   └── requirements.txt
├── docs/
│   └── index.html         GitHub Pages mirror of the landing page
├── screenshots/           README screenshots
├── ARCHITECTURE.md
├── deploy.sh               Cloud Run deployment script
├── nixpacks.toml           Railway build/start config
└── README.md
```

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