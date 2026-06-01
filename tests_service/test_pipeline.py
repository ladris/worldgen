"""End-to-end pipeline tests using the synthetic provider (no network)."""

import json
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from terrain_service.config import ProjectConfig
from terrain_service.pipeline import TilePipeline
from terrain_service.tile_grid import TileIndex
from terrain_service.providers import get_provider
from terrain_service.elevation import decode_absolute


@pytest.fixture
def pipeline(tmp_path):
    cfg = ProjectConfig(
        project_id="synthtest",
        origin_lat=39.7392, origin_lon=-104.9903,
        tile_size_m=256.0, meters_per_pixel=4.0,  # 64 cells, 65 samples — fast
        provider="synthetic",
        elevation_min_m=-500.0, elevation_max_m=9000.0,
    )
    return TilePipeline(cfg, provider=get_provider("synthetic"),
                        work_dir=str(tmp_path / "work"))


def test_generate_writes_all_artifacts(pipeline, tmp_path):
    art = pipeline.generate(TileIndex(0, 0), str(tmp_path / "out"))
    assert os.path.exists(art.r16_path)
    assert os.path.exists(art.json_path)
    n = pipeline.config.samples_per_edge
    # .r16 is uint16 little-endian, n*n samples.
    raw = np.fromfile(art.r16_path, dtype="<u2")
    assert raw.size == n * n


def test_manifest_matches_contract(pipeline, tmp_path):
    art = pipeline.generate(TileIndex(3, -2), str(tmp_path / "out"))
    m = art.manifest
    assert m["schema_version"] == "1.0"
    assert m["tile"] == {"level": 0, "x": 3, "y": -2}
    assert m["grid"]["samples_per_edge"] == pipeline.config.samples_per_edge
    assert m["heightmap"]["format"] == "r16"
    # Constant world Z-scale present and correct.
    assert m["unreal"]["scale"]["z"] == pytest.approx(pipeline.config.ue_scale_z)
    # Unreal location matches grid placement.
    assert m["unreal"]["tile_location_cm"]["x"] == pytest.approx(
        3 * pipeline.config.tile_size_m * 100.0)


def test_adjacent_tiles_have_identical_shared_edge_heights(pipeline, tmp_path):
    """The payoff test: decode two horizontally-adjacent tiles and confirm the
    shared column is bit-identical — proving zero seams end to end."""
    out = str(tmp_path / "out")
    left = pipeline.generate(TileIndex(0, 0), out)
    right = pipeline.generate(TileIndex(1, 0), out)

    lo, hi = pipeline.config.elevation_min_m, pipeline.config.elevation_max_m
    left_h = decode_absolute(left.heightmap, lo, hi)
    right_h = decode_absolute(right.heightmap, lo, hi)

    # East column of left tile == west column of right tile, exactly.
    np.testing.assert_array_equal(left.heightmap[:, -1], right.heightmap[:, 0])
    np.testing.assert_allclose(left_h[:, -1], right_h[:, 0])


def test_vertical_adjacent_tiles_share_edge(pipeline, tmp_path):
    out = str(tmp_path / "out")
    lower = pipeline.generate(TileIndex(0, 0), out)
    upper = pipeline.generate(TileIndex(0, 1), out)
    # North row of lower tile (row 0) == south row of upper tile (last row).
    np.testing.assert_array_equal(lower.heightmap[0, :], upper.heightmap[-1, :])


def test_determinism(pipeline, tmp_path):
    a = pipeline.generate(TileIndex(2, 2), str(tmp_path / "a"))
    b = pipeline.generate(TileIndex(2, 2), str(tmp_path / "b"))
    np.testing.assert_array_equal(a.heightmap, b.heightmap)
    assert a.manifest["content_hash"] == b.manifest["content_hash"]
