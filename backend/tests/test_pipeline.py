"""
RepoTerrain — Pipeline unit tests
Pure-function coverage for pipeline.py: URL parsing, file filtering,
heat scoring, language detection, and edge computation.

Run with: pytest backend/tests/ -v
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from pipeline import (
    parse_gitlab_url,
    should_skip,
    estimate_heat,
    detect_language,
    compute_edges,
    compute_clusters,
)


# ── parse_gitlab_url ──────────────────────────────────────────

def test_parse_gitlab_url_basic():
    host, path = parse_gitlab_url("https://gitlab.com/gitlab-org/gitlab-runner")
    assert host == "gitlab.com"
    assert path == "gitlab-org/gitlab-runner"


def test_parse_gitlab_url_trailing_slash():
    host, path = parse_gitlab_url("https://gitlab.com/gitlab-org/gitlab-runner/")
    assert host == "gitlab.com"
    assert path == "gitlab-org/gitlab-runner"


def test_parse_gitlab_url_nested_group():
    host, path = parse_gitlab_url("https://gitlab.com/group/subgroup/project")
    assert host == "gitlab.com"
    assert path == "group/subgroup/project"


def test_parse_gitlab_url_invalid_raises():
    with pytest.raises(ValueError):
        parse_gitlab_url("not-a-url")


# ── should_skip ───────────────────────────────────────────────

def test_should_skip_binary_extension():
    assert should_skip("assets/logo.png") is True
    assert should_skip("dist/bundle.min.js") is True


def test_should_skip_skip_dir():
    assert should_skip("node_modules/lodash/index.js") is True
    assert should_skip(".git/config") is True
    assert should_skip("vendor/lib/foo.go") is True


def test_should_skip_normal_source_file():
    assert should_skip("backend/main.py") is False
    assert should_skip("src/components/App.tsx") is False


# ── estimate_heat ─────────────────────────────────────────────

def test_estimate_heat_core_file_runs_hot():
    hot = estimate_heat("src/main.go", size=5000)
    cold = estimate_heat("docs/CHANGELOG.md", size=5000)
    assert hot > cold


def test_estimate_heat_bounds():
    for fp, size in [("a.py", 0), ("b.py", 10**8), ("very/deep/nested/path/test.py", 1)]:
        h = estimate_heat(fp, size)
        assert 0.05 <= h <= 1.0


def test_estimate_heat_shallow_files_hotter_than_deep():
    shallow = estimate_heat("main.py", size=1000)
    deep = estimate_heat("a/b/c/d/e/main.py", size=1000)
    assert shallow >= deep


# ── detect_language ───────────────────────────────────────────

@pytest.mark.parametrize("filename,expected", [
    ("main.py", "python"),
    ("index.ts", "typescript"),
    ("App.tsx", "react"),
    ("server.go", "go"),
    ("README.md", "markdown"),
    ("config.yaml", "yaml"),
    ("unknown.xyz", "other"),
])
def test_detect_language(filename, expected):
    assert detect_language(filename) == expected


# ── compute_edges ──────────────────────────────────────────────

def test_compute_edges_empty():
    assert compute_edges([]) == []


def test_compute_edges_connects_nearby_nodes():
    nodes = [
        {"id": "a", "x": 0.0, "y": 0.0, "z": 0.0},
        {"id": "b", "x": 0.05, "y": 0.0, "z": 0.0},
        {"id": "c", "x": 5.0, "y": 5.0, "z": 5.0},
    ]
    edges = compute_edges(nodes, max_dist=0.35, max_per_node=3)
    pairs = {(e["source"], e["target"]) for e in edges}
    assert ("a", "b") in pairs or ("b", "a") in pairs
    # c is far away, should not connect to a or b
    assert ("a", "c") not in pairs and ("c", "a") not in pairs


# ── compute_clusters ───────────────────────────────────────────

def test_compute_clusters_groups_by_directory():
    nodes = [
        {"id": "1", "path": "backend/main.py", "language": "python"},
        {"id": "2", "path": "backend/agent.py", "language": "python"},
        {"id": "3", "path": "README.md", "language": "markdown"},
    ]
    clusters = compute_clusters(nodes)
    assert "backend" in clusters
    assert set(clusters["backend"]) == {"1", "2"}


def test_compute_clusters_drops_singletons():
    nodes = [
        {"id": "1", "path": "backend/main.py", "language": "python"},
        {"id": "2", "path": "README.md", "language": "markdown"},
    ]
    clusters = compute_clusters(nodes)
    # both are singleton clusters -> filtered out
    assert clusters == {}