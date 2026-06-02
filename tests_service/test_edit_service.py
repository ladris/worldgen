"""HTTP tests for the editable-terrain endpoints."""

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
        project_id="esvc", origin_lat=39.7392, origin_lon=-104.9903,
        tile_size_m=256.0, meters_per_pixel=4.0, provider="synthetic",
    )
    cache = TileCache(cfg, cache_root=str(tmp_path / "cache"),
                      provider=get_provider("synthetic"), write_png=False)
    return TestClient(create_app(cache)), cfg


def _read_tile(c, cfg, x, y):
    n = cfg.samples_per_edge
    raw = c.get(f"/tile/0/{x}/{y}/heightmap.r16").content
    return np.frombuffer(raw, dtype="<u2").reshape(n, n)


def test_edit_changes_served_tile(client):
    c, cfg = client
    before = _read_tile(c, cfg, 0, 0)
    # Tile (0,0) centre in Unreal cm: tile spans [0, tile_size_cm].
    half = cfg.tile_size_m * 100.0 / 2.0
    r = c.post("/edit", json={
        "type": "raise_lower", "center_x_cm": half, "center_y_cm": half,
        "radius_m": 100.0, "strength_m": 40.0,
    })
    assert r.status_code == 200
    body = r.json()
    assert "op_id" in body and len(body["affected"]) >= 1
    after = _read_tile(c, cfg, 0, 0)
    # The brushed centre sample rose; compare there rather than the global max
    # (the tile's peak may sit far from the brush and be unchanged).
    n = cfg.samples_per_edge
    assert int(after[n // 2, n // 2]) > int(before[n // 2, n // 2])


def test_edit_then_undo_roundtrip(client):
    c, cfg = client
    before = _read_tile(c, cfg, 3, 3)
    half = cfg.tile_size_m * 100.0 / 2.0
    cx = 3 * cfg.tile_size_m * 100.0 + half
    cy = 3 * cfg.tile_size_m * 100.0 + half
    c.post("/edit", json={"type": "raise_lower", "center_x_cm": cx,
                          "center_y_cm": cy, "radius_m": 100.0, "strength_m": 50.0})
    assert not np.array_equal(_read_tile(c, cfg, 3, 3), before)
    u = c.post("/edit/undo")
    assert u.status_code == 200
    np.testing.assert_allclose(_read_tile(c, cfg, 3, 3), before, atol=2)


def test_tile_edits_listing(client):
    c, cfg = client
    half = cfg.tile_size_m * 100.0 / 2.0
    c.post("/edit", json={"type": "flatten", "center_x_cm": half,
                          "center_y_cm": half, "radius_m": 80.0,
                          "target_height_m": 1200.0})
    r = c.get("/tile/0/0/0/edits")
    assert r.status_code == 200
    assert len(r.json()["ops"]) == 1
    assert r.json()["ops"][0]["type"] == "flatten"


def test_invalid_op_type_rejected(client):
    c, _ = client
    r = c.post("/edit", json={"type": "explode", "center_x_cm": 0.0,
                              "center_y_cm": 0.0, "radius_m": 10.0})
    assert r.status_code >= 400
