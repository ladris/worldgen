"""Security regression tests: resource bounds, input validation, auth.

These lock in the fixes for the audit findings (negative/huge level OOM, edit
radius/iterations DoS, prestage flooding, optional auth). If any of these starts
returning 200 for an abusive request, a guardrail has regressed.
"""

import importlib
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from terrain_service.config import ProjectConfig
from terrain_service.cache import TileCache
from terrain_service.service import create_app
from terrain_service.providers import get_provider
from terrain_service import limits


def _make(tmp_path):
    cfg = ProjectConfig(
        project_id="sec", origin_lat=39.7392, origin_lon=-104.9903,
        tile_size_m=256.0, meters_per_pixel=4.0, provider="synthetic",
    )
    cache = TileCache(cfg, cache_root=str(tmp_path / "cache"),
                      provider=get_provider("synthetic"), write_png=False)
    return cache, cfg


@pytest.fixture
def client(tmp_path):
    cache, cfg = _make(tmp_path)
    return TestClient(create_app(cache)), cfg


# ---- C1: negative / huge level must be rejected, never allocate -------------

def test_negative_level_rejected(client):
    c, _ = client
    r = c.get("/tile/-10/0/0/manifest")
    assert r.status_code == 422  # rejected at the boundary, no allocation


def test_huge_level_rejected(client):
    c, _ = client
    r = c.get(f"/tile/{limits.MAX_TILE_LEVEL + 5}/0/0/manifest")
    assert r.status_code == 422


def test_huge_tile_index_rejected(client):
    c, _ = client
    r = c.get(f"/tile/0/{limits.MAX_ABS_TILE_INDEX + 1}/0/manifest")
    assert r.status_code == 422


# ---- C2: edit radius / iterations bounds -----------------------------------

def test_edit_radius_over_hard_cap_rejected(client):
    c, _ = client
    r = c.post("/edit", json={
        "type": "raise_lower", "center_x_cm": 0, "center_y_cm": 0,
        "radius_m": limits.MAX_EDIT_RADIUS_M + 1, "strength_m": 1,
    })
    assert r.status_code in (400, 422)


def test_edit_radius_within_cap_but_too_many_tiles_rejected(client):
    c, _ = client
    # Large-but-allowed radius that still spans more than the affected-tile cap.
    # tile_size_m=256 → radius of ~20 km spans hundreds of tiles → rejected.
    r = c.post("/edit", json={
        "type": "raise_lower", "center_x_cm": 0, "center_y_cm": 0,
        "radius_m": 20000.0, "strength_m": 1,
    })
    assert r.status_code == 400
    assert "tiles" in r.json()["detail"].lower() or "mosaic" in r.json()["detail"].lower()


def test_edit_excessive_iterations_rejected(client):
    c, _ = client
    r = c.post("/edit", json={
        "type": "smooth", "center_x_cm": 0, "center_y_cm": 0,
        "radius_m": 50.0, "iterations": 10_000_000,
    })
    assert r.status_code in (400, 422)


def test_reasonable_edit_still_works(client):
    c, cfg = client
    half = cfg.tile_size_m * 100.0 / 2.0
    r = c.post("/edit", json={
        "type": "raise_lower", "center_x_cm": half, "center_y_cm": half,
        "radius_m": 80.0, "strength_m": 10.0,
    })
    assert r.status_code == 200


# ---- H1: prestage list bound -----------------------------------------------

def test_prestage_oversized_list_rejected(client):
    c, _ = client
    tiles = [{"x": i, "y": 0} for i in range(limits.MAX_PRESTAGE_TILES + 5)]
    r = c.post("/prestage", json={"tiles": tiles})
    assert r.status_code == 422


def test_prestage_within_limit_ok(client):
    c, _ = client
    r = c.post("/prestage", json={"tiles": [{"x": 1, "y": 1}, {"x": 2, "y": 1}]})
    assert r.status_code == 200


# ---- H2: optional bearer auth ----------------------------------------------

def test_auth_enforced_when_token_set(tmp_path, monkeypatch):
    monkeypatch.setenv("WORLDGEN_API_TOKEN", "s3cret")
    cache, cfg = _make(tmp_path)
    client = TestClient(create_app(cache))
    # health is open; data endpoints require the token.
    assert client.get("/health").status_code == 200
    assert client.get("/project").status_code == 401
    assert client.get("/project",
                      headers={"Authorization": "Bearer s3cret"}).status_code == 200
    assert client.get("/project",
                      headers={"Authorization": "Bearer wrong"}).status_code == 401
