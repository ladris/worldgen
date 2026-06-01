"""Synthetic DEM provider — deterministic analytic terrain.

Generates elevation as a smooth function of absolute world coordinates. Because
it is purely a function of position, adjacent tiles automatically agree on their
shared edges, making this ideal for testing the full pipeline, the HTTP service,
and Unreal stitching with no API key and no network access.
"""

from __future__ import annotations

import numpy as np

from .base import DEMProvider, register_provider
from ..tile_grid import WorldGrid, TileIndex


@register_provider
class SyntheticProvider(DEMProvider):
    name = "synthetic"

    def __init__(self, base_elevation_m: float = 800.0,
                 relief_m: float = 1200.0, seed: int = 1337, **_):
        self.base = base_elevation_m
        self.relief = relief_m
        self.seed = seed

    def sample_grid(self, grid: WorldGrid, tile: TileIndex, work_dir: str) -> np.ndarray:
        # Absolute projected coordinates of every sample (metres). Using absolute
        # world coords (not tile-local) is what makes edges line up across tiles.
        xs, ys = grid.sample_coords_projected(tile)
        # Reference to the grid origin to keep wavelengths intuitive.
        u = (xs - grid.origin_easting)
        v = (ys - grid.origin_northing)

        # A few octaves of sinusoidal ridges + a broad dome. Continuous and
        # smooth everywhere, so seams are trivially testable.
        elev = (
            self.base
            + 0.50 * self.relief * np.sin(u / 4000.0) * np.cos(v / 3500.0)
            + 0.30 * self.relief * np.sin(u / 1200.0 + 1.7) * np.cos(v / 1500.0 - 0.4)
            + 0.20 * self.relief * np.sin((u + v) / 600.0)
            + 0.10 * self.relief * np.cos((u - 2 * v) / 250.0)
        )
        return elev.astype(np.float64)
