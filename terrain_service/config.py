"""Project configuration for the terrain service.

A :class:`ProjectConfig` fully defines a streamable world: its geographic
anchor, projected CRS, tile geometry, elevation encoding range, and DEM source.
All grid math and tile generation derive deterministically from this config, so
the same config always produces the same world (a hard requirement for seamless
stitching and caching — see ``docs/CONTRACT.md``).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, asdict, field
from typing import Any

logger = logging.getLogger(__name__)

# Default elevation envelope covering essentially all of Earth's land surface.
# Vertical precision at this range is ~0.145 m / uint16 level.
DEFAULT_ELEVATION_MIN_M = -500.0
DEFAULT_ELEVATION_MAX_M = 9000.0

# Unreal Engine's internal landscape height span, in UE units. Used to derive a
# constant world Z-scale from the project elevation range (see CONTRACT §4).
UE_INTERNAL_HEIGHT_SPAN = 512.0
CM_PER_M = 100.0


@dataclass(frozen=True)
class ProjectConfig:
    """Immutable definition of a streamable world.

    Attributes:
        project_id: Stable identifier (also the cache namespace).
        origin_lat, origin_lon: WGS84 anchor; Unreal world origin maps here.
        tile_size_m: Side length of one square tile, in metres.
        meters_per_pixel: Ground sample distance of the heightmaps.
        elevation_min_m, elevation_max_m: Project-wide absolute encoding range.
        dem_type: Provider DEM product identifier (e.g. ``SRTMGL1``).
        provider: Registered provider name (e.g. ``opentopography``).
        crs: Projected metric CRS. ``None`` → auto UTM zone of the origin.
    """

    project_id: str
    origin_lat: float
    origin_lon: float
    tile_size_m: float = 1008.0
    meters_per_pixel: float = 1.0
    elevation_min_m: float = DEFAULT_ELEVATION_MIN_M
    elevation_max_m: float = DEFAULT_ELEVATION_MAX_M
    dem_type: str = "SRTMGL1"
    provider: str = "opentopography"
    crs: str | None = None

    # ---- validation -----------------------------------------------------

    def __post_init__(self) -> None:
        if not self.project_id:
            raise ValueError("project_id must be non-empty")
        if not (-90.0 <= self.origin_lat <= 90.0):
            raise ValueError(f"origin_lat out of range: {self.origin_lat}")
        if not (-180.0 <= self.origin_lon <= 180.0):
            raise ValueError(f"origin_lon out of range: {self.origin_lon}")
        if self.tile_size_m <= 0:
            raise ValueError(f"tile_size_m must be > 0: {self.tile_size_m}")
        if self.meters_per_pixel <= 0:
            raise ValueError(f"meters_per_pixel must be > 0: {self.meters_per_pixel}")
        if self.elevation_max_m <= self.elevation_min_m:
            raise ValueError(
                "elevation_max_m must exceed elevation_min_m "
                f"({self.elevation_max_m} <= {self.elevation_min_m})"
            )
        # cells must be a whole number so edges land exactly on grid lines.
        cells = self.tile_size_m / self.meters_per_pixel
        if abs(cells - round(cells)) > 1e-9:
            raise ValueError(
                f"tile_size_m / meters_per_pixel must be integral, got {cells}. "
                "Adjust tile_size_m or meters_per_pixel so edges align."
            )

    # ---- derived constants ---------------------------------------------

    @property
    def cells_per_tile(self) -> int:
        """Number of cells (quads) along a tile edge."""
        return round(self.tile_size_m / self.meters_per_pixel)

    @property
    def samples_per_edge(self) -> int:
        """Number of samples (vertices) along a tile edge. ``cells + 1`` so
        neighbouring tiles share their boundary samples."""
        return self.cells_per_tile + 1

    @property
    def elevation_span_m(self) -> float:
        return self.elevation_max_m - self.elevation_min_m

    @property
    def vertex_spacing_cm(self) -> float:
        return self.meters_per_pixel * CM_PER_M

    @property
    def ue_scale_z(self) -> float:
        """Constant Unreal Z-scale for the whole world (CONTRACT §4)."""
        return (self.elevation_span_m * CM_PER_M) / UE_INTERNAL_HEIGHT_SPAN

    @property
    def vertical_precision_m(self) -> float:
        return self.elevation_span_m / 65535.0

    # ---- (de)serialization ---------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def derived(self) -> dict[str, Any]:
        """Derived constants, for the ``/project`` endpoint and debugging."""
        return {
            "cells_per_tile": self.cells_per_tile,
            "samples_per_edge": self.samples_per_edge,
            "elevation_span_m": self.elevation_span_m,
            "vertex_spacing_cm": self.vertex_spacing_cm,
            "ue_scale_z": self.ue_scale_z,
            "vertical_precision_m": self.vertical_precision_m,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProjectConfig":
        fields = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        unknown = set(data) - fields
        if unknown:
            logger.warning("Ignoring unknown config keys: %s", sorted(unknown))
        return cls(**{k: v for k, v in data.items() if k in fields})

    @classmethod
    def load(cls, path: str) -> "ProjectConfig":
        with open(path, "r", encoding="utf-8") as f:
            return cls.from_dict(json.load(f))

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)
