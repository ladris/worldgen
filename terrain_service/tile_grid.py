"""WorldGrid — deterministic mapping between tile indices and the real Earth.

This is the keystone of the system (see ``docs/ARCHITECTURE.md`` §2 and
``docs/CONTRACT.md`` §1). It defines a regular, origin-anchored, metric grid in
the project's projected CRS. Every integer tile index ``(x, y)`` names exactly
one patch of Earth, adjacent tiles share edge lines exactly, and all geometry is
a pure function of the index plus :class:`ProjectConfig`.

The Unreal C++ ``FWorldGrid`` mirrors this math exactly; any change here must be
reflected there and the contract ``schema_version`` bumped.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from pyproj import CRS, Transformer

from .config import ProjectConfig, CM_PER_M


@dataclass(frozen=True)
class TileIndex:
    """A tile address in the world grid."""

    x: int
    y: int
    level: int = 0

    def as_dict(self) -> dict[str, int]:
        return {"level": self.level, "x": self.x, "y": self.y}

    def __str__(self) -> str:
        return f"L{self.level}/{self.x}/{self.y}"


@dataclass(frozen=True)
class TileBounds:
    """Axis-aligned bounds of a tile in a given CRS (min/max easting/northing)."""

    min_x: float
    min_y: float
    max_x: float
    max_y: float

    def as_dict(self) -> dict[str, float]:
        return {"min_x": self.min_x, "min_y": self.min_y,
                "max_x": self.max_x, "max_y": self.max_y}


def utm_epsg_for_lonlat(lat: float, lon: float) -> str:
    """Return the EPSG code of the UTM zone containing ``(lat, lon)``.

    Mirrors the standard UTM zone formula so the result is dependency-light and
    identical to the Unreal side.
    """
    if not (-80.0 <= lat <= 84.0):
        # Outside UTM's normal band; fall back to polar stereographic.
        return "EPSG:3413" if lat > 0 else "EPSG:3031"
    zone = int(math.floor((lon + 180.0) / 6.0)) + 1
    zone = min(max(zone, 1), 60)
    base = 32600 if lat >= 0 else 32700
    return f"EPSG:{base + zone}"


class WorldGrid:
    """Deterministic tile geometry for one project.

    Resolves the project CRS (auto-UTM if unspecified), anchors the grid at the
    origin, and provides tile↔bounds↔Unreal conversions plus the per-tile sample
    coordinate grid used to resample DEM data.
    """

    def __init__(self, config: ProjectConfig):
        self.config = config

        # Resolve projected CRS (metric). Auto-pick UTM zone of the origin.
        crs_str = config.crs or utm_epsg_for_lonlat(config.origin_lat, config.origin_lon)
        self.crs = CRS.from_user_input(crs_str)
        self.crs_string = crs_str
        if not self.crs.is_projected:
            raise ValueError(
                f"Project CRS {crs_str} is not projected; a metric projected CRS "
                "(e.g. a UTM zone) is required for 1:1 world scale."
            )

        # Transformers between WGS84 and the project CRS (always lon/lat order).
        self._to_proj = Transformer.from_crs("EPSG:4326", self.crs, always_xy=True)
        self._to_wgs84 = Transformer.from_crs(self.crs, "EPSG:4326", always_xy=True)

        # Grid origin in projected metres.
        self.origin_easting, self.origin_northing = self._to_proj.transform(
            config.origin_lon, config.origin_lat
        )

    # ---- tile geometry --------------------------------------------------

    def tile_bounds_projected(self, tile: TileIndex) -> TileBounds:
        """Projected (metric) bounds of a tile."""
        size = self._level_tile_size_m(tile.level)
        min_x = self.origin_easting + tile.x * size
        min_y = self.origin_northing + tile.y * size
        return TileBounds(min_x, min_y, min_x + size, min_y + size)

    def tile_bounds_wgs84(self, tile: TileIndex) -> TileBounds:
        """WGS84 bounds of a tile, padded to safely cover the projected square.

        The projected square's corners do not map to an axis-aligned WGS84 box,
        so we transform all four corners and take their envelope. A small margin
        is added so DEM fetches fully cover the tile after reprojection.
        """
        b = self.tile_bounds_projected(tile)
        xs, ys = [], []
        for px, py in [(b.min_x, b.min_y), (b.max_x, b.min_y),
                       (b.max_x, b.max_y), (b.min_x, b.max_y)]:
            lon, lat = self._to_wgs84.transform(px, py)
            xs.append(lon)
            ys.append(lat)
        # ~2 cells of margin to guarantee coverage for resampling at the edges.
        margin_deg = (2.0 * self.config.meters_per_pixel) / 111_000.0
        return TileBounds(min(xs) - margin_deg, min(ys) - margin_deg,
                          max(xs) + margin_deg, max(ys) + margin_deg)

    def sample_coords_projected(self, tile: TileIndex) -> tuple[np.ndarray, np.ndarray]:
        """Projected coordinates of every sample in the tile.

        Returns ``(xs, ys)`` arrays of shape ``(samples_per_edge,
        samples_per_edge)``. Row 0 is the north edge (image top); column 0 is the
        west edge. Edge samples land exactly on the shared grid lines, which is
        what makes neighbouring tiles weld.
        """
        b = self.tile_bounds_projected(tile)
        n = self._samples_per_edge(tile.level)
        mpp = self._level_mpp(tile.level)
        cols = b.min_x + np.arange(n) * mpp          # west → east
        rows = b.max_y - np.arange(n) * mpp          # north → south
        xs, ys = np.meshgrid(cols, rows)
        return xs, ys

    def sample_coords_wgs84(self, tile: TileIndex) -> tuple[np.ndarray, np.ndarray]:
        """Same as :meth:`sample_coords_projected` but in lon/lat."""
        xs, ys = self.sample_coords_projected(tile)
        lon, lat = self._to_wgs84.transform(xs, ys)
        return np.asarray(lon), np.asarray(lat)

    # ---- inverse + neighbours ------------------------------------------

    def tile_for_projected(self, easting: float, northing: float,
                           level: int = 0) -> TileIndex:
        """Which tile contains a projected point."""
        size = self._level_tile_size_m(level)
        x = int(math.floor((easting - self.origin_easting) / size))
        y = int(math.floor((northing - self.origin_northing) / size))
        return TileIndex(x, y, level)

    def tile_for_lonlat(self, lat: float, lon: float, level: int = 0) -> TileIndex:
        """Which tile contains a WGS84 point (e.g. the player's location)."""
        easting, northing = self._to_proj.transform(lon, lat)
        return self.tile_for_projected(easting, northing, level)

    def neighbors(self, tile: TileIndex) -> dict[str, TileIndex]:
        return {
            "north": TileIndex(tile.x, tile.y + 1, tile.level),
            "south": TileIndex(tile.x, tile.y - 1, tile.level),
            "east": TileIndex(tile.x + 1, tile.y, tile.level),
            "west": TileIndex(tile.x - 1, tile.y, tile.level),
        }

    def tiles_in_radius(self, center: TileIndex, radius: int) -> list[TileIndex]:
        """All tiles within a Chebyshev (square) radius of ``center``."""
        out = []
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                out.append(TileIndex(center.x + dx, center.y + dy, center.level))
        return out

    # ---- Unreal placement ----------------------------------------------

    def unreal_location_cm(self, tile: TileIndex) -> tuple[float, float, float]:
        """Unreal world location (cm) of the tile's grid origin corner.

        Unreal world == project CRS scaled to cm, with the project origin at
        Unreal (0,0). See ``docs/CONTRACT.md`` §4.
        """
        b = self.tile_bounds_projected(tile)
        x_cm = (b.min_x - self.origin_easting) * CM_PER_M
        y_cm = (b.min_y - self.origin_northing) * CM_PER_M
        return (x_cm, y_cm, 0.0)

    # ---- level helpers (LOD pyramid; level 0 = native) ------------------

    def _level_mpp(self, level: int) -> float:
        return self.config.meters_per_pixel * (2 ** level)

    def _level_tile_size_m(self, level: int) -> float:
        # Tile footprint is constant across levels; only resolution changes.
        return self.config.tile_size_m

    def _samples_per_edge(self, level: int) -> int:
        cells = round(self._level_tile_size_m(level) / self._level_mpp(level))
        return cells + 1
