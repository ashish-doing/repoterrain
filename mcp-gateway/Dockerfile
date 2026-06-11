# RepoTerrain — GitLab MCP Gateway
# Wraps zereight/gitlab-mcp (community GitLab MCP server) for Streamable HTTP
# with Remote Authorization, so RepoTerrain's agent can call real MCP tools
# (create_issue, list_merge_requests, list_pipelines, ...) on free-tier GitLab.

FROM zereight050/gitlab-mcp:latest

ENV HOST=0.0.0.0
ENV PORT=3002
ENV STREAMABLE_HTTP=true
ENV REMOTE_AUTHORIZATION=true
ENV GITLAB_API_URL=https://gitlab.com/api/v4
ENV USE_PIPELINE=true
ENV USE_MILESTONE=true

EXPOSE 3002