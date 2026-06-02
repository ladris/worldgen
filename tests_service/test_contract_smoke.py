"""Run the contract smoke harness against an in-process service."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from terrain_service.config import ProjectConfig
from terrain_service.cache import TileCache
from terrain_service.service import create_app
from terrain_service.providers import get_provider
from tools.contract_smoke import run


def test_contract_smoke_passes(tmp_path):
    cfg = ProjectConfig(
        project_id="smoke", origin_lat=39.7392, origin_lon=-104.9903,
        tile_size_m=256.0, meters_per_pixel=4.0, provider="synthetic",
    )
    cache = TileCache(cfg, cache_root=str(tmp_path / "cache"),
                      provider=get_provider("synthetic"), write_png=False)
    client = TestClient(create_app(cache))
    summary = run(client, base="")
    assert summary["status"] == "PASS"
    assert summary["seam_check"] == "ok"
    assert summary["edit_check"] == "ok"
    assert summary["undo_check"] == "ok"
