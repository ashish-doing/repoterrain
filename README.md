# ⛰ RepoTerrain
**Gestural 3D Codebase Intelligence** — Google Cloud Rapid Agent Hackathon

> Every codebase has a shape. RepoTerrain makes you feel it.

Navigate any GitLab repository as a 3D semantic terrain using bare hands. A Gemini agent watches where you look and answers questions, creates issues, and writes docs — all through GitLab MCP.

---

## Architecture

```
GitLab Repo URL
    │
    ▼
gitingest → Vertex AI Text Embeddings (768-dim)
    │
    ▼
UMAP 3D projection → (x, y, z) per file
    │
    ├── Three.js terrain (browser)
    │   Files = peaks  |  Heat = color  |  Edges = dependency rivers
    │
    ├── MediaPipe Hand Tracking (browser)
    │   Open palm = fly  |  Pinch = zoom  |  Point = select
    │
    └── Gemini 2.0 Flash (Vertex AI) + GitLab MCP
        Explain clusters | Create issues | Write docs | Query commits
```

## Setup

### 1. Google Cloud

```bash
# Create project + enable APIs
gcloud projects create repoterrain-hackathon
gcloud config set project repoterrain-hackathon

gcloud services enable \
  aiplatform.googleapis.com \
  run.googleapis.com \
  cloudbuild.googleapis.com

# Auth
gcloud auth application-default login
```

### 2. GitLab Token

Create a GitLab Personal Access Token with: `api`, `read_repository`, `write_repository`

```bash
# Store as Cloud Run secret
echo -n "glpat-xxxx" | gcloud secrets create gitlab-token --data-file=-
```

### 3. Local Development

```bash
cd backend
pip install -r requirements.txt

# Copy and fill .env
cp .env.example .env
# Edit: GCP_PROJECT, GITLAB_TOKEN

# Start backend
uvicorn main:app --reload --port 8000

# Open frontend
open ../frontend/index.html
# Or serve it:
python -m http.server 3000 --directory ../frontend
```

### 4. Deploy to Cloud Run

```bash
chmod +x deploy.sh
GCP_PROJECT=your-project-id ./deploy.sh
```

## Tech Stack

| Tool | Purpose | License |
|------|---------|---------|
| `gitingest` | Repo → LLM text | MIT |
| Vertex AI `text-embedding-005` | File → 768-dim vector | Google (compliant) |
| `umap-learn` | Vectors → 3D coords | BSD |
| Three.js | 3D terrain rendering | MIT |
| MediaPipe Tasks Vision | Hand tracking | Apache 2.0 |
| FastAPI | Backend API + WebSocket | MIT |
| Gemini 2.0 Flash | Agent reasoning | Google |
| GitLab MCP Server | Repo actions | GitLab |
| Cloud Run | Deployment | Google |

## Hackathon Compliance

- ✅ Built with Gemini + Google Cloud (Vertex AI)
- ✅ Integrates GitLab MCP Server
- ✅ Agent performs real actions (create issues, MRs, fetch commits)
- ✅ Only Google Cloud AI (Vertex AI embeddings — NOT sentence-transformers)
- ✅ OSS license (MIT)
- ✅ New project built during contest period

## Agent Capabilities

Point at any file in 3D space and ask:

- `"Explain this cluster"` → reads files, reasons, explains
- `"Create an issue for this cold zone"` → creates real GitLab issue
- `"Onboard me to this codebase"` → writes onboarding doc
- `"What changed last sprint?"` → queries commits, highlights changes
- `"What's the most complex module?"` → analyzes terrain topology
