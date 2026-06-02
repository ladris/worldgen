"""Authoritative edit layer + persistence.

The op log (JSONL, on disk) is the source of truth. Composited tiles in the
cache are derived: for any region we assemble the *base* terrain as one mosaic,
replay the overlapping ops in order, then split back into seamless tiles. This
guarantees raise/lower/flatten edits are identical on shared edges by
construction, is drift-free (always rebuilt from base, never re-quantised), and
makes persistence automatic — the normal tile-fetch path serves edited terrain.

Single-user / local for now; the same op-log + endpoints upgrade cleanly to a
server-backed multi-user store later.
"""

from __future__ import annotations

import json
import logging
import os
import threading

import numpy as np

from .config import ProjectConfig
from .cache import TileCache
from .tile_grid import WorldGrid, TileIndex
from .edits import EditOp, apply_op
from .elevation import fill_nodata

logger = logging.getLogger(__name__)


class EditStore:
    def __init__(self, cache: TileCache):
        self.cache = cache
        self.config: ProjectConfig = cache.config
        self.grid: WorldGrid = cache.pipeline.grid
        self.provider = cache.pipeline.provider
        self.work_dir = cache.pipeline.work_dir

        self.project_dir = cache.project_dir
        self.log_path = os.path.join(self.project_dir, "edits.jsonl")
        self.base_dir = os.path.join(self.project_dir, "_base")
        os.makedirs(self.base_dir, exist_ok=True)

        self._lock = threading.Lock()
        self.ops: list[EditOp] = []
        self._load_log()

    # -- op log persistence ----------------------------------------------

    def _load_log(self) -> None:
        if not os.path.exists(self.log_path):
            return
        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    self.ops.append(EditOp.from_dict(json.loads(line)))
        logger.info("Loaded %d edit ops for project '%s'.",
                    len(self.ops), self.config.project_id)

    def _rewrite_log(self) -> None:
        with open(self.log_path, "w", encoding="utf-8") as f:
            for op in self.ops:
                f.write(json.dumps(op.to_dict()) + "\n")

    def _append_log(self, op: EditOp) -> None:
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(op.to_dict()) + "\n")

    # -- coordinate helpers ----------------------------------------------

    def _center_projected(self, op: EditOp) -> tuple[float, float]:
        """Brush centre (Unreal cm) → projected metres."""
        easting = self.grid.origin_easting + op.center_x_cm / 100.0
        northing = self.grid.origin_northing + op.center_y_cm / 100.0
        return easting, northing

    def _affected_tiles(self, op: EditOp) -> list[TileIndex]:
        ce, cn = self._center_projected(op)
        size = self.config.tile_size_m
        e0, e1 = ce - op.radius_m, ce + op.radius_m
        n0, n1 = cn - op.radius_m, cn + op.radius_m
        x0 = int(np.floor((e0 - self.grid.origin_easting) / size))
        x1 = int(np.floor((e1 - self.grid.origin_easting) / size))
        y0 = int(np.floor((n0 - self.grid.origin_northing) / size))
        y1 = int(np.floor((n1 - self.grid.origin_northing) / size))
        tiles = []
        for ty in range(y0, y1 + 1):
            for tx in range(x0, x1 + 1):
                tiles.append(TileIndex(tx, ty))
        return tiles

    def _op_overlaps_extent(self, op: EditOp, x0: int, x1: int,
                            y0: int, y1: int) -> bool:
        ce, cn = self._center_projected(op)
        size = self.config.tile_size_m
        rx0 = self.grid.origin_easting + x0 * size
        rx1 = self.grid.origin_easting + (x1 + 1) * size
        ry0 = self.grid.origin_northing + y0 * size
        ry1 = self.grid.origin_northing + (y1 + 1) * size
        return not (ce + op.radius_m < rx0 or ce - op.radius_m > rx1 or
                    cn + op.radius_m < ry0 or cn - op.radius_m > ry1)

    # -- base terrain (pristine, pre-edit) -------------------------------

    def _base_heights(self, tile: TileIndex) -> np.ndarray:
        """Pristine base heights (metres) for a tile, cached on disk as .npy."""
        path = os.path.join(self.base_dir, f"{tile.level}_{tile.x}_{tile.y}.npy")
        if os.path.exists(path):
            # allow_pickle=False (the default) — never deserialize pickled objects.
            return np.load(path, allow_pickle=False)
        elev = self.provider.sample_grid(self.grid, tile, self.work_dir)
        elev = fill_nodata(elev)
        np.save(path, elev.astype(np.float32))
        return elev.astype(np.float64)

    # -- mosaic assembly / split -----------------------------------------

    def _extent(self, tiles: list[TileIndex]) -> tuple[int, int, int, int]:
        xs = [t.x for t in tiles]
        ys = [t.y for t in tiles]
        return min(xs), max(xs), min(ys), max(ys)

    def _mosaic_shape(self, x0: int, x1: int, y0: int, y1: int) -> tuple[int, int]:
        n = self.config.samples_per_edge
        cells = n - 1
        w = (x1 - x0 + 1) * cells + 1
        h = (y1 - y0 + 1) * cells + 1
        return h, w

    def _assemble_base_mosaic(self, x0, x1, y0, y1) -> np.ndarray:
        n = self.config.samples_per_edge
        cells = n - 1
        h, w = self._mosaic_shape(x0, x1, y0, y1)
        mosaic = np.zeros((h, w), dtype=np.float64)
        for ty in range(y0, y1 + 1):
            for tx in range(x0, x1 + 1):
                base = self._base_heights(TileIndex(tx, ty))
                # row 0 = north (largest y) at mosaic top.
                r0 = (y1 - ty) * cells
                c0 = (tx - x0) * cells
                mosaic[r0:r0 + n, c0:c0 + n] = base
        return mosaic

    def _mosaic_coords(self, x0, x1, y0, y1) -> tuple[np.ndarray, np.ndarray]:
        mpp = self.config.meters_per_pixel
        size = self.config.tile_size_m
        h, w = self._mosaic_shape(x0, x1, y0, y1)
        e_west = self.grid.origin_easting + x0 * size
        n_north = self.grid.origin_northing + (y1 + 1) * size
        cols = e_west + np.arange(w) * mpp
        rows = n_north - np.arange(h) * mpp
        easting, northing = np.meshgrid(cols, rows)
        return easting, northing

    def _split_and_write(self, mosaic: np.ndarray, x0, x1, y0, y1) -> list[dict]:
        n = self.config.samples_per_edge
        cells = n - 1
        manifests = []
        for ty in range(y0, y1 + 1):
            for tx in range(x0, x1 + 1):
                r0 = (y1 - ty) * cells
                c0 = (tx - x0) * cells
                sub = mosaic[r0:r0 + n, c0:c0 + n]
                m = self.cache.write_heights(TileIndex(tx, ty), sub)
                manifests.append(m)
        return manifests

    # -- public API -------------------------------------------------------

    def apply_edit(self, op: EditOp) -> dict:
        """Apply an edit, persist it, and rebuild the affected tiles seamlessly.

        Returns the affected tile keys and their refreshed manifests.
        """
        with self._lock:
            tiles = self._affected_tiles(op)
            if not tiles:
                return {"affected": [], "op_id": op.op_id}
            x0, x1, y0, y1 = self._extent(tiles)

            # Resource guard: bound the affected-tile count and the mosaic
            # dimensions so a large radius / fine resolution cannot allocate an
            # enormous array (defence in depth behind the HTTP-layer limits).
            from .limits import (
                MAX_EDIT_AFFECTED_TILES, MAX_EDIT_MOSAIC_SAMPLES_PER_SIDE,
            )
            if len(tiles) > MAX_EDIT_AFFECTED_TILES:
                raise ValueError(
                    f"edit affects {len(tiles)} tiles (max {MAX_EDIT_AFFECTED_TILES}); "
                    "reduce radius_m."
                )
            mh, mw = self._mosaic_shape(x0, x1, y0, y1)
            if max(mh, mw) > MAX_EDIT_MOSAIC_SAMPLES_PER_SIDE:
                raise ValueError(
                    f"edit mosaic {mw}x{mh} exceeds "
                    f"{MAX_EDIT_MOSAIC_SAMPLES_PER_SIDE}; reduce radius_m."
                )

            mosaic = self._assemble_base_mosaic(x0, x1, y0, y1)
            easting, northing = self._mosaic_coords(x0, x1, y0, y1)

            # Replay every existing op overlapping this region, then the new op,
            # in timestamp order — so the result is the full composited state.
            region_ops = [o for o in self.ops
                          if self._op_overlaps_extent(o, x0, x1, y0, y1)]
            region_ops.append(op)
            region_ops.sort(key=lambda o: o.timestamp)
            for o in region_ops:
                ce, cn = self._center_projected(o)
                mosaic = apply_op(mosaic, easting, northing, o, ce, cn)

            manifests = self._split_and_write(mosaic, x0, x1, y0, y1)

            self.ops.append(op)
            self._append_log(op)

            logger.info("Applied edit %s (%s) over %d tiles.",
                        op.op_id[:8], op.type, len(tiles))
            return {
                "op_id": op.op_id,
                "affected": [t.as_dict() for t in tiles],
                "manifests": manifests,
            }

    def undo_last(self) -> dict:
        """Remove the most recent op and rebuild its region from base + the
        remaining overlapping ops."""
        with self._lock:
            if not self.ops:
                return {"undone": None, "affected": []}
            op = self.ops.pop()
            self._rewrite_log()

            tiles = self._affected_tiles(op)
            if not tiles:
                return {"undone": op.op_id, "affected": []}
            x0, x1, y0, y1 = self._extent(tiles)

            mosaic = self._assemble_base_mosaic(x0, x1, y0, y1)
            easting, northing = self._mosaic_coords(x0, x1, y0, y1)
            region_ops = [o for o in self.ops
                          if self._op_overlaps_extent(o, x0, x1, y0, y1)]
            region_ops.sort(key=lambda o: o.timestamp)
            for o in region_ops:
                ce, cn = self._center_projected(o)
                mosaic = apply_op(mosaic, easting, northing, o, ce, cn)

            self._split_and_write(mosaic, x0, x1, y0, y1)
            logger.info("Undid edit %s; rebuilt %d tiles.", op.op_id[:8], len(tiles))
            return {"undone": op.op_id, "affected": [t.as_dict() for t in tiles]}

    def ops_for_tile(self, tile: TileIndex) -> list[dict]:
        result = []
        for o in self.ops:
            if self._op_overlaps_extent(o, tile.x, tile.x, tile.y, tile.y):
                result.append(o.to_dict())
        return result
