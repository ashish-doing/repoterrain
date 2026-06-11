# Contributing to RepoTerrain

Thanks for your interest! This project was built for the 
Google Cloud Rapid Agent Hackathon — GitLab Track — June 2026.

## Running Locally

```bash
git clone https://github.com/ashish-doing/repoterrain
cd repoterrain/backend
pip install -r requirements.txt
cp .env.example .env
# Add your keys to .env
uvicorn main:app --reload --port 8080
```

## Environment Variables

| Variable | Required | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | Yes | Gemini 2.0 Flash agent + embeddings |
| `GITLAB_TOKEN` | Yes | Issue creation, MR listing |
| `GROQ_API_KEY` | No | Quota fallback only |

## Architecture

See [ARCHITECTURE.md](./ARCHITECTURE.md) for full system diagrams.

## Issues

Use the issue tracker for bugs. 
For live demo issues created by the AI agent, 
see [repoterrain-demo](https://gitlab.com/ashish-doing/repoterrain-demo/-/issues).