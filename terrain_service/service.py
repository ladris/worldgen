"""FastAPI app implementing the HTTP contract (CONTRACT.md §5).

This is the boundary Unreal talks to. Endpoints are intentionally thin wrappers
over :class:`TileCache`; all the real work (grid math, fetch, encode) lives
below them.
"""

from __future__ import annotations

import logging

from .config import ProjectConfig
from .cache import TileCache
from .tile_grid import TileIndex

logger = logging.getLogger(__name__)

# Imports are at module scope so that, under ``from __future__ import
# annotations``, FastAPI can resolve the stringized type hints (BackgroundTasks,
# PrestageRequest) against this module's globals when building the routes.
try:
    from fastapi import FastAPI, BackgroundTasks
    from fastapi.responses import Response, JSONResponse
    from pydantic import BaseModel

    class TileRef(BaseModel):
        level: int = 0
        x: int
        y: int

    class PrestageRequest(BaseModel):
        tiles: list[TileRef]

    class EditRequest(BaseModel):
        type: str
        center_x_cm: float
        center_y_cm: float
        radius_m: float
        strength_m: float = 0.0
        target_height_m: float = 0.0
        falloff: str = "smooth"
        iterations: int = 1

    _FASTAPI_OK = True
except ImportError:  # pragma: no cover
    _FASTAPI_OK = False


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
        version="1.0",
        summary=f"Real-world terrain tiles for project '{config.project_id}'.",
    )

    def _idx(level: int, x: int, y: int) -> TileIndex:
        return TileIndex(x=x, y=y, level=level)

    @app.get("/health")
    def health():
        return {"status": "ok", "project_id": config.project_id}

    @app.get("/project")
    def project():
        return {"config": config.to_dict(), "derived": config.derived()}

    @app.get("/tile/{level}/{x}/{y}/manifest")
    def tile_manifest(level: int, x: int, y: int):
        m = cache.get_manifest(_idx(level, x, y))
        m["heightmap_url"] = f"/tile/{level}/{x}/{y}/heightmap.r16"
        return JSONResponse(m)

    @app.get("/tile/{level}/{x}/{y}/heightmap.r16")
    def tile_heightmap(level: int, x: int, y: int):
        path = cache.get_heightmap_path(_idx(level, x, y))
        with open(path, "rb") as f:
            data = f.read()
        return Response(
            content=data,
            media_type="application/octet-stream",
            headers={
                "X-Tile-Manifest": f"/tile/{level}/{x}/{y}/manifest",
                "Content-Disposition": f'inline; filename="{level}_{x}_{y}.r16"',
            },
        )

    @app.get("/tile/{level}/{x}/{y}")
    def tile(level: int, x: int, y: int):
        """Convenience: manifest JSON plus the heightmap URL (one logical tile)."""
        m = cache.get_manifest(_idx(level, x, y))
        m["heightmap_url"] = f"/tile/{level}/{x}/{y}/heightmap.r16"
        return JSONResponse(m)

    @app.post("/prestage")
    def prestage(req: PrestageRequest, background: BackgroundTasks):
        tiles = [_idx(t.level, t.x, t.y) for t in req.tiles]
        background.add_task(cache.prestage, tiles)
        return {"status": "scheduled", "count": len(tiles)}

    # ---- editable terrain (CONTRACT §7) --------------------------------

    @app.post("/edit")
    def edit(req: EditRequest):
        from fastapi import HTTPException
        from .edits import EditOp
        try:
            op = EditOp(
                type=req.type, center_x_cm=req.center_x_cm,
                center_y_cm=req.center_y_cm, radius_m=req.radius_m,
                strength_m=req.strength_m, target_height_m=req.target_height_m,
                falloff=req.falloff, iterations=req.iterations,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        return JSONResponse(edit_store.apply_edit(op))

    @app.post("/edit/undo")
    def edit_undo():
        return JSONResponse(edit_store.undo_last())

    @app.get("/tile/{level}/{x}/{y}/edits")
    def tile_edits(level: int, x: int, y: int):
        return {"tile": {"level": level, "x": x, "y": y},
                "ops": edit_store.ops_for_tile(_idx(level, x, y))}

    return app
