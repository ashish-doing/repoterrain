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
</p>

<br/>

> **Google Cloud Rapid Agent Hackathon — GitLab Track — June 2026**
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

> 3-minute walkthrough: terrain load → agent Q&A → live GitLab issue creation

---

## What It Does

Paste any public GitLab repository URL. In ~15 seconds:

- **Up to 150 files** are fetched, embedded with Google AI, and projected into 3D space via UMAP
- **Semantic clusters** emerge — files grouped by code similarity, not folder structure
- **Activity heat map** shows which code is active (red) vs legacy (blue)
- **Gemini 2.0 Flash agent** answers questions with real file content as context
- **GitLab MCP actions** create real issues, list MRs, and fetch pipeline status — live

```
Tested on gitlab-org/gitlab-runner → 149 files · 24 clusters · ~15s end-to-end
```

---

## Agent in Action

| Query | What Happens |
|---|---|
| `"What's the most complex module?"` | Gemini reads file content → structured analysis with cluster context |
| `"Create an issue for cold zones"` | Real GitLab issue created at `ashish-doing/repoterrain-demo` with labels + clickable URL in chat |
| `"Explain the CI cluster"` | Reads actual CI files, explains module relationships |
| `"List open MRs"` | Fetches live merge requests via GitLab API |

---

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| **AI Embeddings** | Google AI `text-embedding-004` | 768-dim semantic file vectors |
| **AI Agent** | Gemini 2.0 Flash | Codebase Q&A + action reasoning |
| **Fallback LLM** | Groq LLaMA 3.1 8B | Agent fallback when Gemini quota exceeded |
| **Fallback Embed** | TF-IDF (sklearn) | Embedding fallback (~2.8s vs ~15s Gemini) |
| **3D Engine** | Three.js r128 + CSS3DRenderer | Floating file cards in semantic space |
| **Hand Tracking** | MediaPipe Tasks Vision | Gesture-based terrain navigation |
| **Dim Reduction** | UMAP | High-dim vectors → 3D coordinates |
| **GitLab Actions** | GitLab REST API v4 | Issue creation, MR listing, pipelines |
| **Backend** | FastAPI + uvicorn | Ingest pipeline + agent API + WebSocket |
| **Deployment** | Railway | Live public URL |

---

## Architecture

See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full system diagram with data flow, state schema, and component breakdown.

**Short version:**

```
GitLab REST API → Google AI Embeddings → UMAP 3D → Three.js terrain
                                                  ↓
                              Gemini 2.0 Flash agent + GitLab MCP actions
```

---

## Hackathon Compliance

| Requirement | Status |
|---|---|
| Google Cloud AI (Gemini) | ✅ Gemini 2.0 Flash — agent reasoning |
| Google Cloud AI (Embeddings) | ✅ `text-embedding-004` — semantic file positioning |
| GitLab MCP actions | ✅ Real issue creation, MR listing, pipeline fetch |
| Agent takes real actions | ✅ Creates artifacts on GitLab, not just chat responses |
| New project | ✅ First commit May 23, 2026 (hackathon opened May 5) |
| Public repo + live demo | ✅ MIT license, deployed on Railway |

---

## Performance

| Metric | Value |
|---|---|
| Files analyzed | Up to 150 per repo |
| Embedding (TF-IDF fallback) | ~2.8 seconds |
| Embedding (Google AI) | ~15 seconds (768-dim vectors) |
| End-to-end terrain load | ~15 seconds |
| Agent response | ~2s (Groq) / ~3s (Gemini) |
| Issue creation | ~1 second |

---

## Local Setup

```bash
git clone https://github.com/ashish-doing/repoterrain
cd repoterrain/backend
pip install -r requirements.txt

# Create .env
GEMINI_API_KEY=your_key_here
GROQ_API_KEY=your_key_here
GITLAB_TOKEN=your_token_here

uvicorn main:app --reload --port 8080
# Open: http://localhost:8080/app
```

### Environment Variables

| Variable | Purpose | Required |
|---|---|---|
| `GEMINI_API_KEY` | Gemini 2.0 Flash + text-embedding-004 | Recommended |
| `GROQ_API_KEY` | LLaMA 3.1 fallback | Recommended |
| `GITLAB_TOKEN` | Issue creation + MR/pipeline fetch | For MCP actions |

---

## Project Structure

```
repoterrain/
├── backend/
│   ├── main.py          FastAPI — /ingest, /agent/query, /ws, /app, /
│   ├── pipeline.py      GitLab fetch → embed → UMAP → terrain JSON
│   ├── agent.py         Gemini 2.0 Flash + Groq fallback + GitLab MCP
│   ├── index.html       Frontend (Three.js + MediaPipe + agent panel)
│   ├── landing.html     Product landing page
│   └── requirements.txt
├── ARCHITECTURE.md
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