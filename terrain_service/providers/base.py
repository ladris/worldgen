"""DEM provider interface + registry.

A provider returns elevations sampled on a tile's *exact* projected sample grid
(metres, NaN for NoData). Keeping the contract at "sample this grid" rather than
"download this file" lets analytic sources (synthetic) and raster sources
(OpenTopography) share one clean pipeline.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np

from ..tile_grid import WorldGrid, TileIndex


class DEMProvider(ABC):
    """Abstract source of real (or synthetic) elevation data."""

    name: str = "base"

    @abstractmethod
    def sample_grid(self, grid: WorldGrid, tile: TileIndex, work_dir: str) -> np.ndarray:
        """Return ``(samples_per_edge, samples_per_edge)`` float elevations in
        metres on the tile's exact sample grid (project CRS). NaN = NoData.

        Implementations must be deterministic: identical inputs → identical
        output, so that shared edges between tiles coincide exactly.
        """
        raise NotImplementedError


_REGISTRY: dict[str, type[DEMProvider]] = {}


def register_provider(cls: type[DEMProvider]) -> type[DEMProvider]:
    _REGISTRY[cls.name] = cls
    return cls


def get_provider(name: str, **kwargs) -> DEMProvider:
    if name not in _REGISTRY:
        raise KeyError(
            f"Unknown provider '{name}'. Registered: {sorted(_REGISTRY)}"
        )
    return _REGISTRY[name](**kwargs)


def available_providers() -> list[str]:
    return sorted(_REGISTRY)
