"""Manifest construction — the JSON contract emitted with every tile.

Centralises CONTRACT.md §3.2 / §4 so the exact serialized shape lives in one
place and both the HTTP service and the CLI produce identical manifests.
"""

from __future__ import annotations

from typing import Any

from .config import ProjectConfig, CM_PER_M
from .tile_grid import WorldGrid, TileIndex

SCHEMA_VERSION = "1.0"


def build_manifest(config: ProjectConfig, grid: WorldGrid, tile: TileIndex,
                   tile_min_m: float, tile_max_m: float,
                   content_hash: str | None = None) -> dict[str, Any]:
    b_proj = grid.tile_bounds_projected(tile)
    b_wgs = grid.tile_bounds_wgs84(tile)
    loc = grid.unreal_location_cm(tile)
    n = config.samples_per_edge

    return {
        "schema_version": SCHEMA_VERSION,
        "project_id": config.project_id,
        "tile": tile.as_dict(),
        "grid": {
            "crs": grid.crs_string,
            "origin_easting_m": grid.origin_easting,
            "origin_northing_m": grid.origin_northing,
            "tile_size_m": config.tile_size_m,
            "meters_per_pixel": config.meters_per_pixel,
            "cells_per_tile": config.cells_per_tile,
            "samples_per_edge": n,
        },
        "bounds_projected_m": b_proj.as_dict(),
        "bounds_wgs84": {
            "west": b_wgs.min_x, "south": b_wgs.min_y,
            "east": b_wgs.max_x, "north": b_wgs.max_y,
        },
        "elevation": {
            "project_min_m": config.elevation_min_m,
            "project_max_m": config.elevation_max_m,
            "tile_min_m": tile_min_m,
            "tile_max_m": tile_max_m,
            "encoding": "uint16_linear_absolute",
        },
        "heightmap": {
            "format": "r16",
            "width": n, "height": n,
            "bbp": 16, "byte_order": "little",
            "row_order": "north_to_south",
        },
        "unreal": {
            "vertex_spacing_cm": config.vertex_spacing_cm,
            "tile_location_cm": {"x": loc[0], "y": loc[1], "z": loc[2]},
            "scale": {"x": 100.0, "y": 100.0, "z": config.ue_scale_z},
        },
        "neighbors": {
            name: idx.as_dict() for name, idx in grid.neighbors(tile).items()
        },
        "content_hash": content_hash,
    }
