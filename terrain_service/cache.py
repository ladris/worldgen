"""On-disk tile cache.

Generated tiles are expensive (network fetch + reprojection), so they are stored
once and reused. The cache is the layer the HTTP service talks to: ask for a
tile, get it from disk or generate-then-store. Per-tile locks prevent duplicate
work when concurrent requests race for the same tile.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from collections import defaultdict

from .config import ProjectConfig
from .pipeline import TilePipeline, TileArtifacts
from .tile_grid import TileIndex
from .providers import DEMProvider

logger = logging.getLogger(__name__)


class TileCache:
    def __init__(self, config: ProjectConfig, cache_root: str = ".worldgen_cache",
                 provider: DEMProvider | None = None, write_png: bool = True):
        self.config = config
        self.cache_root = cache_root
        self.write_png = write_png
        self.pipeline = TilePipeline(
            config, provider=provider,
            work_dir=os.path.join(cache_root, config.project_id, "_work"),
        )
        self.project_dir = os.path.join(cache_root, config.project_id)
        os.makedirs(self.project_dir, exist_ok=True)
        self._locks: dict[str, threading.Lock] = defaultdict(threading.Lock)
        self._locks_guard = threading.Lock()
        self._persist_config()

    # -- paths ------------------------------------------------------------

    def _tile_dir(self, tile: TileIndex) -> str:
        return os.path.join(self.project_dir, str(tile.level), str(tile.x))

    def _base(self, tile: TileIndex) -> str:
        return os.path.join(self._tile_dir(tile), str(tile.y))

    def paths(self, tile: TileIndex) -> dict[str, str]:
        base = self._base(tile)
        return {"r16": base + ".r16", "png": base + ".png", "json": base + ".json"}

    def _lock_for(self, tile: TileIndex) -> threading.Lock:
        with self._locks_guard:
            return self._locks[str(tile)]

    # -- access -----------------------------------------------------------

    def has(self, tile: TileIndex) -> bool:
        p = self.paths(tile)
        return os.path.exists(p["r16"]) and os.path.exists(p["json"])

    def get_manifest(self, tile: TileIndex) -> dict:
        """Return the manifest, generating the tile if absent."""
        self.ensure(tile)
        with open(self.paths(tile)["json"], "r", encoding="utf-8") as f:
            return json.load(f)

    def get_heightmap_path(self, tile: TileIndex) -> str:
        self.ensure(tile)
        return self.paths(tile)["r16"]

    def ensure(self, tile: TileIndex) -> TileArtifacts | None:
        """Generate the tile if it is not already cached. Returns artifacts when
        freshly generated, ``None`` when served from cache."""
        if self.has(tile):
            return None
        lock = self._lock_for(tile)
        with lock:
            if self.has(tile):  # double-check after acquiring the lock
                return None
            os.makedirs(self._tile_dir(tile), exist_ok=True)
            art = self.pipeline.generate(
                tile, self._tile_dir(tile), write_png=self.write_png,
                base_name=str(tile.y),
            )
            return art

    def prestage(self, tiles: list[TileIndex]) -> dict[str, int]:
        """Generate any missing tiles in the list (synchronously). Returns
        counts; intended to be called from a background worker/thread."""
        generated = cached = 0
        for t in tiles:
            if self.has(t):
                cached += 1
            else:
                self.ensure(t)
                generated += 1
        logger.info("Prestage complete: %d generated, %d already cached",
                    generated, cached)
        return {"generated": generated, "cached": cached, "total": len(tiles)}

    # -- bookkeeping ------------------------------------------------------

    def _persist_config(self) -> None:
        path = os.path.join(self.project_dir, "project.json")
        payload = {"config": self.config.to_dict(),
                   "derived": self.config.derived()}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
