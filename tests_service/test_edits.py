"""Tests for the editable terrain layer: brushes, persistence, seamlessness."""

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from terrain_service.config import ProjectConfig
from terrain_service.cache import TileCache
from terrain_service.edit_store import EditStore
from terrain_service.edits import EditOp, OP_RAISE_LOWER, OP_FLATTEN, OP_SMOOTH
from terrain_service.tile_grid import TileIndex
from terrain_service.providers import get_provider


@pytest.fixture
def store(tmp_path):
    cfg = ProjectConfig(
        project_id="edittest", origin_lat=39.7392, origin_lon=-104.9903,
        tile_size_m=256.0, meters_per_pixel=4.0, provider="synthetic",
    )
    cache = TileCache(cfg, cache_root=str(tmp_path / "cache"),
                      provider=get_provider("synthetic"), write_png=False)
    return EditStore(cache), cache, cfg


def _center_cm_of_tile(cache, tile):
    """Unreal cm at the centre of a tile (brush coordinates are Unreal cm)."""
    loc = cache.pipeline.grid.unreal_location_cm(tile)
    half = cache.config.tile_size_m * 100.0 / 2.0
    return loc[0] + half, loc[1] + half


def test_raise_changes_height(store):
    es, cache, cfg = store
    t = TileIndex(0, 0)
    before = cache.decode_heights(t).copy()
    cx, cy = _center_cm_of_tile(cache, t)
    es.apply_edit(EditOp(type=OP_RAISE_LOWER, center_x_cm=cx, center_y_cm=cy,
                         radius_m=80.0, strength_m=50.0))
    after = cache.decode_heights(t)
    # Centre rose ~50 m (within encoding precision).
    n = cfg.samples_per_edge
    assert after[n // 2, n // 2] - before[n // 2, n // 2] == pytest.approx(50.0, abs=0.5)
    # Far corner essentially unchanged.
    assert abs(after[0, 0] - before[0, 0]) < 1.0


def test_edit_persists_via_fetch(store, tmp_path):
    es, cache, cfg = store
    t = TileIndex(1, 1)
    cx, cy = _center_cm_of_tile(cache, t)
    es.apply_edit(EditOp(type=OP_RAISE_LOWER, center_x_cm=cx, center_y_cm=cy,
                         radius_m=120.0, strength_m=30.0))
    edited = cache.decode_heights(t).copy()

    # A brand-new EditStore + cache over the same dir must reproduce the edit
    # (persistence): the cached tile already carries it.
    cache2 = TileCache(cfg, cache_root=cache.cache_root,
                       provider=get_provider("synthetic"), write_png=False)
    reloaded = cache2.decode_heights(t)
    np.testing.assert_allclose(edited, reloaded, atol=0.2)


def test_edit_across_boundary_stays_seamless(store):
    es, cache, cfg = store
    # Brush centred on the shared edge between tiles (0,0) and (1,0).
    loc = cache.pipeline.grid.unreal_location_cm(TileIndex(1, 0))
    half_h = cache.config.tile_size_m * 100.0 / 2.0
    edge_x_cm = loc[0]                 # west edge of tile (1,0) == east edge of (0,0)
    edge_y_cm = loc[1] + half_h
    es.apply_edit(EditOp(type=OP_RAISE_LOWER, center_x_cm=edge_x_cm,
                         center_y_cm=edge_y_cm, radius_m=150.0, strength_m=40.0))

    left = cache.decode_heights(TileIndex(0, 0))
    right = cache.decode_heights(TileIndex(1, 0))
    # Shared column still identical after the cross-boundary edit.
    np.testing.assert_allclose(left[:, -1], right[:, 0], atol=1e-6)


def test_flatten_moves_toward_target(store):
    es, cache, cfg = store
    t = TileIndex(2, 0)
    cx, cy = _center_cm_of_tile(cache, t)
    target = 1500.0
    es.apply_edit(EditOp(type=OP_FLATTEN, center_x_cm=cx, center_y_cm=cy,
                         radius_m=200.0, target_height_m=target, falloff="constant"))
    after = cache.decode_heights(t)
    n = cfg.samples_per_edge
    assert after[n // 2, n // 2] == pytest.approx(target, abs=1.0)


def test_undo_restores_base(store):
    es, cache, cfg = store
    t = TileIndex(0, 0)
    base = cache.decode_heights(t).copy()
    cx, cy = _center_cm_of_tile(cache, t)
    es.apply_edit(EditOp(type=OP_RAISE_LOWER, center_x_cm=cx, center_y_cm=cy,
                         radius_m=100.0, strength_m=60.0))
    assert not np.allclose(cache.decode_heights(t), base, atol=1.0)
    es.undo_last()
    np.testing.assert_allclose(cache.decode_heights(t), base, atol=0.3)


def test_multiple_edits_accumulate(store):
    es, cache, cfg = store
    t = TileIndex(0, 0)
    cx, cy = _center_cm_of_tile(cache, t)
    base = cache.decode_heights(t).copy()
    for _ in range(3):
        es.apply_edit(EditOp(type=OP_RAISE_LOWER, center_x_cm=cx, center_y_cm=cy,
                             radius_m=100.0, strength_m=10.0))
    n = cfg.samples_per_edge
    after = cache.decode_heights(t)
    assert after[n // 2, n // 2] - base[n // 2, n // 2] == pytest.approx(30.0, abs=0.6)


def test_smooth_runs_and_reduces_variance(store):
    es, cache, cfg = store
    t = TileIndex(5, 5)
    cx, cy = _center_cm_of_tile(cache, t)
    before = cache.decode_heights(t)
    n = cfg.samples_per_edge
    region = (slice(n // 4, 3 * n // 4), slice(n // 4, 3 * n // 4))
    var_before = np.var(before[region])
    es.apply_edit(EditOp(type=OP_SMOOTH, center_x_cm=cx, center_y_cm=cy,
                         radius_m=400.0, falloff="constant", iterations=8))
    after = cache.decode_heights(t)
    assert np.var(after[region]) <= var_before
