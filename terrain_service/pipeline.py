"""Tile generation pipeline.

For a tile index, produces the wire artifacts defined in the contract:
``<tile>.r16`` (raw uint16 heightmap), ``<tile>.png`` (16-bit preview), and
``<tile>.json`` (manifest). Pure orchestration over the WorldGrid, a DEM
provider, and the absolute elevation encoder.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os

import numpy as np

from .config import ProjectConfig
from .tile_grid import WorldGrid, TileIndex
from .providers import DEMProvider, get_provider
from .elevation import fill_nodata, encode_absolute
from .manifest import build_manifest

logger = logging.getLogger(__name__)


class TileArtifacts:
    """Paths + manifest for one generated tile."""

    def __init__(self, manifest: dict, r16_path: str, png_path: str | None,
                 json_path: str, heightmap: np.ndarray):
        self.manifest = manifest
        self.r16_path = r16_path
        self.png_path = png_path
        self.json_path = json_path
        self.heightmap = heightmap


class TilePipeline:
    def __init__(self, config: ProjectConfig, provider: DEMProvider | None = None,
                 work_dir: str = ".worldgen_work"):
        self.config = config
        self.grid = WorldGrid(config)
        self.provider = provider or get_provider(
            config.provider, dem_type=config.dem_type
        )
        self.work_dir = work_dir
        os.makedirs(work_dir, exist_ok=True)

    def generate(self, tile: TileIndex, out_dir: str,
                 write_png: bool = True) -> TileArtifacts:
        """Generate and write all artifacts for ``tile`` into ``out_dir``."""
        os.makedirs(out_dir, exist_ok=True)

        # 1. Sample elevations on the tile's exact grid (metres, NaN = NoData).
        elev = self.provider.sample_grid(self.grid, tile, self.work_dir)
        n = self.config.samples_per_edge
        if elev.shape != (n, n):
            raise ValueError(
                f"Provider returned {elev.shape}, expected {(n, n)} for {tile}"
            )

        # 2. Remove holes — a streamed world cannot contain gaps.
        elev = fill_nodata(elev)
        tile_min = float(np.min(elev))
        tile_max = float(np.max(elev))

        # 3. Encode with the project-wide absolute map (constant world Z-scale).
        u16 = encode_absolute(elev, self.config.elevation_min_m,
                              self.config.elevation_max_m)

        # 4. Write heightmap (.r16, little-endian, row-major, north at top).
        base = f"{tile.level}_{tile.x}_{tile.y}"
        r16_path = os.path.join(out_dir, base + ".r16")
        u16_le = u16.astype("<u2", copy=False)
        u16_le.tofile(r16_path)
        content_hash = "sha256:" + hashlib.sha256(u16_le.tobytes()).hexdigest()

        png_path = None
        if write_png:
            png_path = os.path.join(out_dir, base + ".png")
            self._write_png16(u16, png_path)

        # 5. Manifest.
        manifest = build_manifest(self.config, self.grid, tile,
                                  tile_min, tile_max, content_hash)
        json_path = os.path.join(out_dir, base + ".json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        logger.info("Generated tile %s (elev %.1f..%.1f m) -> %s",
                    tile, tile_min, tile_max, r16_path)
        return TileArtifacts(manifest, r16_path, png_path, json_path, u16)

    @staticmethod
    def _write_png16(u16: np.ndarray, path: str) -> None:
        try:
            from PIL import Image
        except ImportError:
            logger.warning("Pillow not installed; skipping PNG preview.")
            return
        # uint16 arrays map to Pillow's 'I;16' mode automatically.
        Image.fromarray(u16).save(path)
