"""HTTP service tests via FastAPI TestClient (synthetic provider, no network)."""

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from terrain_service.config import ProjectConfig
from terrain_service.cache import TileCache
from terrain_service.service import create_app
from terrain_service.providers import get_provider


@pytest.fixture
def client(tmp_path):
    cfg = ProjectConfig(
        project_id="svc", origin_lat=39.7392, origin_lon=-104.9903,
        tile_size_m=256.0, meters_per_pixel=4.0, provider="synthetic",
    )
    cache = TileCache(cfg, cache_root=str(tmp_path / "cache"),
                      provider=get_provider("synthetic"), write_png=False)
    return TestClient(create_app(cache)), cfg


def test_health(client):
    c, cfg = client
    r = c.get("/health")
    assert r.status_code == 200
    assert r.json()["project_id"] == cfg.project_id


def test_project_endpoint(client):
    c, cfg = client
    r = c.get("/project")
    body = r.json()
    assert body["config"]["project_id"] == cfg.project_id
    assert body["derived"]["samples_per_edge"] == cfg.samples_per_edge


def test_manifest_endpoint(client):
    c, cfg = client
    r = c.get("/tile/0/2/-1/manifest")
    assert r.status_code == 200
    m = r.json()
    assert m["tile"] == {"level": 0, "x": 2, "y": -1}
    assert m["heightmap_url"] == "/tile/0/2/-1/heightmap.r16"


def test_heightmap_endpoint_size_and_type(client):
    c, cfg = client
    r = c.get("/tile/0/0/0/heightmap.r16")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/octet-stream"
    arr = np.frombuffer(r.content, dtype="<u2")
    assert arr.size == cfg.samples_per_edge ** 2


def test_heightmap_matches_manifest_hash(client):
    import hashlib
    c, _ = client
    raw = c.get("/tile/0/1/1/heightmap.r16").content
    m = c.get("/tile/0/1/1/manifest").json()
    assert m["content_hash"] == "sha256:" + hashlib.sha256(raw).hexdigest()


def test_service_tiles_are_seamless(client):
    """Fetch two adjacent tiles over HTTP and confirm the shared edge matches."""
    c, cfg = client
    n = cfg.samples_per_edge
    left = np.frombuffer(c.get("/tile/0/0/0/heightmap.r16").content,
                         dtype="<u2").reshape(n, n)
    right = np.frombuffer(c.get("/tile/0/1/0/heightmap.r16").content,
                          dtype="<u2").reshape(n, n)
    np.testing.assert_array_equal(left[:, -1], right[:, 0])


def test_prestage_schedules(client):
    c, _ = client
    r = c.post("/prestage", json={"tiles": [{"x": 5, "y": 5}, {"x": 6, "y": 5}]})
    assert r.status_code == 200
    assert r.json()["count"] == 2
