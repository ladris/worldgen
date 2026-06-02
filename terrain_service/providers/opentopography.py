"""OpenTopography DEM provider.

Fetches a GeoTIFF covering the tile's WGS84 envelope, then reprojects and
resamples it onto the tile's *exact* projected sample grid with bilinear
interpolation. Sampling onto the shared grid (rather than per-tile arbitrary
pixels) is what preserves edge continuity between neighbours.
"""

from __future__ import annotations

import hashlib
import logging
import os

import numpy as np
import requests

from .base import DEMProvider, register_provider
from ..tile_grid import WorldGrid, TileIndex

logger = logging.getLogger(__name__)

OPENTOPOGRAPHY_API_URL = "https://portal.opentopography.org/API/globaldem"


class OpenTopographyError(RuntimeError):
    pass


@register_provider
class OpenTopographyProvider(DEMProvider):
    name = "opentopography"

    def __init__(self, dem_type: str = "SRTMGL1", api_key: str | None = None,
                 timeout: int = 180, **_):
        self.dem_type = dem_type
        self.api_key = api_key or os.environ.get("OPENTOPOGRAPHY_API_KEY")
        self.timeout = timeout

    # -- fetch ------------------------------------------------------------

    def _fetch_geotiff(self, west, south, east, north, out_path) -> None:
        if not self.api_key:
            raise OpenTopographyError(
                "No OpenTopography API key. Set OPENTOPOGRAPHY_API_KEY or pass "
                "api_key=. (Use the 'synthetic' provider for offline testing.)"
            )
        params = {
            "demtype": self.dem_type,
            "west": west, "south": south, "east": east, "north": north,
            "outputFormat": "GTiff",
            "API_Key": self.api_key,
        }
        logger.info("OpenTopography fetch %s bbox=(%.5f,%.5f,%.5f,%.5f)",
                    self.dem_type, west, south, east, north)
        resp = requests.get(OPENTOPOGRAPHY_API_URL, params=params,
                            stream=True, timeout=self.timeout)
        if resp.status_code != 200:
            # Redact the API key before it can land in logs/exceptions, in case
            # an upstream error body reflects the request.
            body = resp.text[:300]
            if self.api_key:
                body = body.replace(self.api_key, "***REDACTED***")
            raise OpenTopographyError(f"HTTP {resp.status_code}: {body}")
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        with open(out_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        if os.path.getsize(out_path) < 512:
            with open(out_path, "rb") as f:
                head = f.read(256).decode(errors="ignore")
            raise OpenTopographyError(f"Suspiciously small response: {head!r}")

    # -- sample -----------------------------------------------------------

    def sample_grid(self, grid: WorldGrid, tile: TileIndex, work_dir: str) -> np.ndarray:
        # Import rasterio lazily so the synthetic path needs no GDAL.
        import rasterio
        from rasterio.warp import reproject, Resampling
        from rasterio.transform import Affine

        b_wgs = grid.tile_bounds_wgs84(tile)
        # Deterministic cache filename for the raw source download.
        key = hashlib.sha1(
            f"{self.dem_type}:{b_wgs.min_x:.6f},{b_wgs.min_y:.6f},"
            f"{b_wgs.max_x:.6f},{b_wgs.max_y:.6f}".encode()
        ).hexdigest()[:16]
        raw_path = os.path.join(work_dir, f"src_{self.dem_type}_{key}.tif")
        if not os.path.exists(raw_path):
            self._fetch_geotiff(b_wgs.min_x, b_wgs.min_y, b_wgs.max_x,
                                b_wgs.max_y, raw_path)

        b = grid.tile_bounds_projected(tile)
        n = grid.config.samples_per_edge
        mpp = grid.config.meters_per_pixel
        # Destination transform such that pixel CENTERS land exactly on the tile
        # sample grid: center(col,row) = (min_x + col*mpp, max_y - row*mpp).
        dst_transform = Affine(mpp, 0, b.min_x - 0.5 * mpp,
                               0, -mpp, b.max_y + 0.5 * mpp)
        dst = np.full((n, n), np.nan, dtype=np.float64)

        with rasterio.open(raw_path) as src:
            src_nodata = src.nodata
            reproject(
                source=rasterio.band(src, 1),
                destination=dst,
                src_transform=src.transform,
                src_crs=src.crs,
                src_nodata=src_nodata,
                dst_transform=dst_transform,
                dst_crs=grid.crs,
                dst_nodata=np.nan,
                resampling=Resampling.bilinear,
            )
        return dst
