"""FastAPI app implementing the HTTP contract (CONTRACT.md §5).

This is the boundary Unreal talks to. Endpoints are thin wrappers over
:class:`TileCache`; the real work lives below them. The boundary enforces
resource limits (see ``limits.py``) and maps expected failures to clean HTTP
errors, so untrusted input cannot exhaust memory or leak internals.

Optional auth: if the ``WORLDGEN_API_TOKEN`` environment variable is set, every
request must carry ``Authorization: Bearer <token>``. Unset (the default) leaves
the service open for local single-user use — do not expose it that way (see
SECURITY.md).
"""

from __future__ import annotations

import logging
import os

from .config import ProjectConfig
from .cache import TileCache
from .tile_grid import TileIndex
from . import limits

logger = logging.getLogger(__name__)

# Imports are at module scope so that, under ``from __future__ import
# annotations``, FastAPI can resolve the stringized type hints against this
# module's globals when building the routes.
try:
    from fastapi import (
        FastAPI, BackgroundTasks, HTTPException, Path, Depends, Header,
    )
    from fastapi.responses import Response, JSONResponse
    from pydantic import BaseModel, Field

    class TileRef(BaseModel):
        level: int = Field(0, ge=limits.MIN_TILE_LEVEL, le=limits.MAX_TILE_LEVEL)
        x: int = Field(..., ge=-limits.MAX_ABS_TILE_INDEX, le=limits.MAX_ABS_TILE_INDEX)
        y: int = Field(..., ge=-limits.MAX_ABS_TILE_INDEX, le=limits.MAX_ABS_TILE_INDEX)

    class PrestageRequest(BaseModel):
        tiles: list[TileRef] = Field(..., max_length=limits.MAX_PRESTAGE_TILES)

    class EditRequest(BaseModel):
        type: str
        center_x_cm: float
        center_y_cm: float
        radius_m: float = Field(..., gt=0.0, le=limits.MAX_EDIT_RADIUS_M)
        strength_m: float = 0.0
        target_height_m: float = 0.0
        falloff: str = "smooth"
        iterations: int = Field(1, ge=1, le=limits.MAX_EDIT_ITERATIONS)

    _FASTAPI_OK = True
except ImportError:  # pragma: no cover
    _FASTAPI_OK = False


# Path() parameter constraints (reused across the tile routes). Negative or huge
# `level` is the most dangerous input (it upsamples the sample grid), so it is
# rejected with a 422 before any allocation.
def _level_path():
    return Path(..., ge=limits.MIN_TILE_LEVEL, le=limits.MAX_TILE_LEVEL)


def _coord_path():
    return Path(..., ge=-limits.MAX_ABS_TILE_INDEX, le=limits.MAX_ABS_TILE_INDEX)


def create_app(cache: TileCache, edit_store=None):
    """Build a FastAPI application bound to a configured tile cache.

    If ``edit_store`` is omitted, an :class:`EditStore` is created over the cache
    so the editable-terrain endpoints are available by default.
    """
    if not _FASTAPI_OK:  # pragma: no cover
        raise RuntimeError(
            "FastAPI is required to run the service. "
            "Install with: pip install fastapi uvicorn"
        )

    if edit_store is None:
        from .edit_store import EditStore
        edit_store = EditStore(cache)

    config = cache.config
    app = FastAPI(
        title="Dynamic World Streaming — Terrain Service",
        version="1.1",
        summary=f"Real-world terrain tiles for project '{config.project_id}'.",
    )

    # ---- optional bearer-token auth ------------------------------------
    api_token = os.environ.get("WORLDGEN_API_TOKEN")
    if api_token:
        logger.info("Terrain service auth enabled (WORLDGEN_API_TOKEN set).")
    else:
        logger.warning(
            "Terrain service running WITHOUT auth. Bind to localhost only; do "
            "not expose to untrusted networks (see SECURITY.md)."
        )

    def require_auth(authorization: str | None = Header(default=None)) -> None:
        if not api_token:
            return  # auth disabled
        expected = f"Bearer {api_token}"
        if authorization != expected:
            raise HTTPException(status_code=401, detail="Unauthorized")

    auth = [Depends(require_auth)]

    def _idx(level: int, x: int, y: int) -> TileIndex:
        # Belt-and-braces: Path/Field constraints already reject bad values, but
        # validate again so the helper is safe regardless of caller.
        try:
            limits.validate_tile(level, x, y)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        return TileIndex(x=x, y=y, level=level)

    def _safe_manifest(idx: TileIndex) -> dict:
        """Generate/serve a manifest, mapping expected failures to clean HTTP
        errors instead of bare 500s."""
        from .providers.opentopography import OpenTopographyError
        try:
            return cache.get_manifest(idx)
        except OpenTopographyError as e:
            logger.warning("Upstream DEM error for %s: %s", idx, e)
            raise HTTPException(status_code=502, detail="Upstream DEM provider error.")
        except MemoryError:
            raise HTTPException(status_code=413, detail="Requested tile too large.")
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Tile not found.")
        except Exception:
            logger.exception("Tile generation failed for %s", idx)
            raise HTTPException(status_code=500, detail="Tile generation failed.")

    @app.get("/health")
    def health():
        return {"status": "ok", "project_id": config.project_id}

    @app.get("/project", dependencies=auth)
    def project():
        return {"config": config.to_dict(), "derived": config.derived()}

    @app.get("/tile/{level}/{x}/{y}/manifest", dependencies=auth)
    def tile_manifest(level: int = _level_path(), x: int = _coord_path(),
                      y: int = _coord_path()):
        m = _safe_manifest(_idx(level, x, y))
        m["heightmap_url"] = f"/tile/{level}/{x}/{y}/heightmap.r16"
        return JSONResponse(m)

    @app.get("/tile/{level}/{x}/{y}/heightmap.r16", dependencies=auth)
    def tile_heightmap(level: int = _level_path(), x: int = _coord_path(),
                       y: int = _coord_path()):
        idx = _idx(level, x, y)
        _safe_manifest(idx)  # ensure generated (and surface clean errors)
        try:
            with open(cache.paths(idx)["r16"], "rb") as f:
                data = f.read()
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Tile not found.")
        return Response(
            content=data,
            media_type="application/octet-stream",
            headers={
                "X-Tile-Manifest": f"/tile/{level}/{x}/{y}/manifest",
                "Content-Disposition": f'inline; filename="{level}_{x}_{y}.r16"',
            },
        )

    @app.get("/tile/{level}/{x}/{y}", dependencies=auth)
    def tile(level: int = _level_path(), x: int = _coord_path(),
             y: int = _coord_path()):
        """Convenience: manifest JSON plus the heightmap URL (one logical tile)."""
        m = _safe_manifest(_idx(level, x, y))
        m["heightmap_url"] = f"/tile/{level}/{x}/{y}/heightmap.r16"
        return JSONResponse(m)

    @app.post("/prestage", dependencies=auth)
    def prestage(req: PrestageRequest, background: BackgroundTasks):
        # Field(max_length=...) already bounds the list; validate each tile too.
        tiles = [_idx(t.level, t.x, t.y) for t in req.tiles]
        background.add_task(cache.prestage, tiles)
        return {"status": "scheduled", "count": len(tiles)}

    # ---- editable terrain (CONTRACT §7) --------------------------------

    @app.post("/edit", dependencies=auth)
    def edit(req: EditRequest):
        from .edits import EditOp
        try:
            op = EditOp(
                type=req.type, center_x_cm=req.center_x_cm,
                center_y_cm=req.center_y_cm, radius_m=req.radius_m,
                strength_m=req.strength_m, target_height_m=req.target_height_m,
                falloff=req.falloff, iterations=req.iterations,
            )
            result = edit_store.apply_edit(op)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except MemoryError:
            raise HTTPException(status_code=413, detail="Edit region too large.")
        return JSONResponse(result)

    @app.post("/edit/undo", dependencies=auth)
    def edit_undo():
        return JSONResponse(edit_store.undo_last())

    @app.get("/tile/{level}/{x}/{y}/edits", dependencies=auth)
    def tile_edits(level: int = _level_path(), x: int = _coord_path(),
                   y: int = _coord_path()):
        return {"tile": {"level": level, "x": x, "y": y},
                "ops": edit_store.ops_for_tile(_idx(level, x, y))}

    return app
