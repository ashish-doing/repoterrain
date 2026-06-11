# RepoTerrain — GitLab MCP Gateway

A small Railway service that runs the community `zereight/gitlab-mcp` server in
Streamable HTTP + Remote Authorization mode, giving RepoTerrain a real MCP
endpoint that works on GitLab free tier (the official `gitlab.com/api/v4/mcp`
requires GitLab Premium/Ultimate + Duo).

## Deploy on Railway

1. New Railway service → Deploy from GitHub repo → select this repo, set **Root Directory** to `mcp-gateway/`
2. Railway builds the Dockerfile (pulls `zereight050/gitlab-mcp:latest`, sets `STREAMABLE_HTTP=true` + `REMOTE_AUTHORIZATION=true`)
3. No environment variables needed — GitLab tokens are passed per-request from `agent.py` via the `Private-Token` header
4. Note the generated public URL, e.g. `https://terrific-healing-production.up.railway.app`
5. Set `GITLAB_MCP_GATEWAY_URL=https://<that-url>/mcp` in the main backend service's environment variables

## How RepoTerrain Uses This

`backend/agent.py` calls `POST {GITLAB_MCP_GATEWAY_URL}` with:
- `Private-Token: <GITLAB_TOKEN>` header (Remote Authorization — per-request, isolated)
- JSON-RPC 2.0 `tools/call` body: `create_issue`, `list_merge_requests`, `list_pipelines`

This is real MCP — JSON-RPC over Streamable HTTP, `MCP-Protocol-Version: 2025-03-26`. Not a REST shim.

## Why a Separate Service?

The official `gitlab.com/api/v4/mcp` requires GitLab Premium/Ultimate with Duo enabled.
RepoTerrain's demo project runs on GitLab free tier, so we self-host the open-source
community server instead — same MCP protocol, works on any GitLab tier.