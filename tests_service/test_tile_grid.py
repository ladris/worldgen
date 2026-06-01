"""Tests for the WorldGrid — especially the seamless-edge guarantee."""

import math
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from terrain_service.config import ProjectConfig
from terrain_service.tile_grid import WorldGrid, TileIndex, utm_epsg_for_lonlat


@pytest.fixture
def cfg():
    return ProjectConfig(
        project_id="test",
        origin_lat=39.7392,
        origin_lon=-104.9903,  # Denver → UTM 13N
        tile_size_m=1008.0,
        meters_per_pixel=1.0,
    )


@pytest.fixture
def grid(cfg):
    return WorldGrid(cfg)


def test_auto_utm_zone_selection():
    assert utm_epsg_for_lonlat(39.7392, -104.9903) == "EPSG:32613"  # Denver
    assert utm_epsg_for_lonlat(48.8566, 2.3522) == "EPSG:32631"     # Paris
    assert utm_epsg_for_lonlat(-33.8688, 151.2093) == "EPSG:32756"  # Sydney


def test_crs_must_be_projected(cfg):
    bad = ProjectConfig(project_id="t", origin_lat=0, origin_lon=0, crs="EPSG:4326")
    with pytest.raises(ValueError, match="not projected"):
        WorldGrid(bad)


def test_tile_size_is_exact(grid, cfg):
    b = grid.tile_bounds_projected(TileIndex(0, 0))
    assert b.max_x - b.min_x == pytest.approx(cfg.tile_size_m)
    assert b.max_y - b.min_y == pytest.approx(cfg.tile_size_m)


def test_adjacent_tiles_share_edge_exactly(grid):
    """East edge of (x,y) must equal west edge of (x+1,y) to the metre."""
    a = grid.tile_bounds_projected(TileIndex(5, 5))
    east = grid.tile_bounds_projected(TileIndex(6, 5))
    north = grid.tile_bounds_projected(TileIndex(5, 6))
    assert a.max_x == pytest.approx(east.min_x)
    assert a.max_y == pytest.approx(north.min_y)


def test_shared_edge_samples_are_identical(grid):
    """The actual sample coordinates on a shared edge must coincide — this is
    what guarantees weldable vertices and zero seams."""
    xs_a, ys_a = grid.sample_coords_projected(TileIndex(2, 0))
    xs_b, ys_b = grid.sample_coords_projected(TileIndex(3, 0))
    # East column of A == west column of B.
    np.testing.assert_allclose(xs_a[:, -1], xs_b[:, 0])
    np.testing.assert_allclose(ys_a[:, -1], ys_b[:, 0])

    xs_c, ys_c = grid.sample_coords_projected(TileIndex(2, 1))
    # North row of A (row 0) == south row of the tile above (row -1).
    np.testing.assert_allclose(xs_a[0, :], xs_c[-1, :])
    np.testing.assert_allclose(ys_a[0, :], ys_c[-1, :])


def test_sample_grid_shape_and_orientation(grid, cfg):
    xs, ys = grid.sample_coords_projected(TileIndex(0, 0))
    n = cfg.samples_per_edge
    assert xs.shape == (n, n)
    # Row 0 is north (max y), last row is south.
    assert ys[0, 0] > ys[-1, 0]
    # Column 0 is west (min x), last column is east.
    assert xs[0, 0] < xs[0, -1]


def test_inverse_mapping_roundtrip(grid):
    for tile in [TileIndex(0, 0), TileIndex(7, -3), TileIndex(-4, 9)]:
        b = grid.tile_bounds_projected(tile)
        cx = (b.min_x + b.max_x) / 2
        cy = (b.min_y + b.max_y) / 2
        got = grid.tile_for_projected(cx, cy)
        assert (got.x, got.y) == (tile.x, tile.y)


def test_origin_is_in_tile_0_0(grid, cfg):
    t = grid.tile_for_lonlat(cfg.origin_lat, cfg.origin_lon)
    assert (t.x, t.y) == (0, 0)


def test_unreal_location_matches_grid(grid, cfg):
    loc = grid.unreal_location_cm(TileIndex(3, -2))
    assert loc[0] == pytest.approx(3 * cfg.tile_size_m * 100.0)
    assert loc[1] == pytest.approx(-2 * cfg.tile_size_m * 100.0)
    assert loc[2] == 0.0


def test_neighbors(grid):
    n = grid.neighbors(TileIndex(4, 4))
    assert (n["east"].x, n["east"].y) == (5, 4)
    assert (n["west"].x, n["west"].y) == (3, 4)
    assert (n["north"].x, n["north"].y) == (4, 5)
    assert (n["south"].x, n["south"].y) == (4, 3)


def test_tiles_in_radius_count(grid):
    tiles = grid.tiles_in_radius(TileIndex(0, 0), radius=2)
    assert len(tiles) == 25  # (2*2+1)^2
