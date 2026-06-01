# Dynamic World Streaming — System Architecture

> Goal: an Unreal Engine avatar can walk in any direction, forever, across the
> **real Earth**, and terrain materializes seamlessly ahead of them — no loading
> screens, no visible tile seams, generated on the fly from real DEM data.

This document is the master blueprint. It implements the design described in
*"Dynamic World Expansion in Unreal Engine: A Technical Report on Seamless,
Predictive Region Loading."* Each numbered module below maps to that report's
§9.1 architectural blueprint.

---

## 1. The two halves

The system is split along the natural performance seam the design report
identifies (§9.2): heavy geospatial processing in **Python (offline / service)**,
and the hard real-time runtime in **Unreal Engine C++**. They meet at a single,
strict **contract** (`CONTRACT.md`).

```
                          ┌─────────────────────────────────────────────┐
   Real-world DEM APIs    │            PYTHON TERRAIN SERVICE            │
   (OpenTopography, …) ──▶│  providers → pipeline → WorldGrid → cache    │
                          │            HTTP API  (FastAPI)               │
                          └───────────────────────┬─────────────────────┘
                                                  │  GET /tile/{level}/{x}/{y}
                                                  │  → heightmap (.r16) + manifest (JSON)
                                                  ▼
                          ┌─────────────────────────────────────────────┐
                          │          UNREAL ENGINE C++ PLUGIN           │
                          │            "DynamicWorldStreaming"          │
                          │                                             │
                          │  PlayerPrediction → StreamingManager →      │
                          │  TerrainDataClient → TerrainTileActor       │
                          │  (mesh gen · stitch · LOD · collision) →    │
                          │  World Partition registration               │
                          └─────────────────────────────────────────────┘
```

Why this seam: live mesh generation and rendering must never block the game
thread, but DEM fetch/reproject/resample is I/O- and CPU-heavy and far easier in
Python's geospatial stack (GDAL/Rasterio/PyProj). So Python pre-stages tiles
*just ahead* of the player; Unreal does only fast, local work at runtime.

---

## 2. The core idea that makes seams impossible: the WorldGrid

The single most important design decision. Naïve tiling (the original
proof-of-concept) scaled **each tile to its own min/max elevation** and named
tiles by arbitrary local index. That guarantees seams: neighbouring tiles get
different Z-scales and their shared edge doesn't line up.

The fix is a **global, deterministic, metric grid** with **absolute elevation
encoding**:

1. **Origin-anchored metric grid.** A project picks an origin (lat/lon). Its UTM
   zone becomes the project CRS (metric, 1:1 real scale — exactly what Unreal
   wants: 1 px = 1 m, XY scale 100). The world is a regular grid of square tiles
   in that projected CRS. Tile `(x, y)` always covers the *same* patch of Earth.

2. **Shared edges by construction.** Tile `(x, y)` is sampled at `N+1 × N+1`
   points spanning `N` cells. Tile `(x+1, y)`'s west edge samples the *exact same
   world coordinates* as tile `(x, y)`'s east edge. Sampling the same continuous
   DEM at identical coordinates yields identical heights → vertices weld with
   zero gap (design report §5.3.1).

3. **Absolute elevation encoding.** Every tile maps elevation → uint16 using one
   **project-wide** range (`elevation_min_m … elevation_max_m`), not per-tile
   min/max. The Unreal Z-scale is therefore a single constant for the entire
   world, so heights are continuous across every boundary.

These three properties turn "seamless stitching" from a runtime search problem
into a *guarantee baked into the data*.

See `CONTRACT.md` for the exact math and formats.

---

## 3. Module map (→ design report §9.1)

| # | Module | Side | Where |
|---|--------|------|-------|
| 1 | **WorldGrid Core** — deterministic tile↔Earth mapping | Python + UE | `terrain_service/tile_grid.py`, mirrored in UE `WorldGrid.cpp` |
| 2 | **DEM Providers** — pluggable data sources | Python | `terrain_service/providers/` |
| 3 | **Tile Pipeline** — fetch→reproject→resample→encode | Python | `terrain_service/pipeline.py` |
| 4 | **Tile Cache** — pre-staged tiles, dedup, async | Python | `terrain_service/cache.py` |
| 5 | **Terrain Service API** — HTTP contract endpoint | Python | `terrain_service/service.py` |
| 6 | **TerrainDataClient** — async HTTP fetch into UE | UE C++ | `unreal/.../TerrainDataClient` |
| 7 | **TerrainTileActor** — heightmap→mesh, LOD, collision | UE C++ | `unreal/.../TerrainTileActor` |
| 8 | **Tile Stitcher** — cross-tile normal averaging | UE C++ | `unreal/.../TileStitcher` |
| 9 | **PlayerPrediction** — velocity/buffer-zone region prediction | UE C++ | `unreal/.../PlayerPredictionComponent` |
| 10 | **RegionStreamingManager** — request queue, lifecycle, WP registration | UE C++ | `unreal/.../RegionStreamingManager` |

---

## 4. Runtime flow (one step of the avatar's walk)

1. `PlayerPredictionComponent` samples the pawn's velocity + trajectory each
   tick, projects it forward, and computes the set of grid tiles the player will
   likely need within a horizon (buffer zone). (§3)
2. `RegionStreamingManager` diff's that set against currently-loaded tiles and
   enqueues missing ones by priority (nearest-in-travel-direction first). (§3.2)
3. `TerrainDataClient` issues async HTTP GETs to the Python service for each
   needed `(level, x, y)`. The service returns a cached `.r16` + manifest, or
   generates it on demand. (§4)
4. For each arrived tile, `RegionStreamingManager` spawns a `TerrainTileActor`,
   which builds a `UDynamicMeshComponent` from the heightmap on a worker thread,
   then publishes to the game thread. (§5)
5. `TileStitcher` recomputes shared-edge vertex normals using neighbour data so
   lighting is continuous. (§5.3)
6. The actor is registered with World Partition for streaming/unloading, and
   async collision is cooked. (§6, §5.5)
7. Tiles behind the player drop to lower LOD then unload. (§5.4, §2)

---

## 5. Non-negotiables (design report §7, §9.3 pitfalls)

- **Never block the game thread.** All fetch, mesh-gen, simplification, and
  collision cooking happen async / on worker threads.
- **Determinism.** Tile geometry is a pure function of `(level, x, y)` + project
  config. Same input → byte-identical output → reproducible, cacheable, weldable.
- **Constant world Z-scale.** Absolute elevation encoding; no per-tile scaling.
- **Pre-stage, don't live-block.** Prediction loads ahead so fetch latency is
  hidden; the service caches aggressively.

---

## 6. Build phases

- **Phase 0** — Architecture + contract (this + `CONTRACT.md`, `ROADMAP.md`). ✅
- **Phase 1** — Python terrain service: WorldGrid, pipeline, cache, HTTP API,
  tests. *(Fully runnable & tested in CI.)*
- **Phase 2** — Unreal C++ plugin `DynamicWorldStreaming`: tile actor, data
  client, prediction, stitching, LOD, WP integration. *(Compiled in-engine.)*
- **Phase 3** — Integration: example project, setup guides, end-to-end walk.

See `ROADMAP.md` for the detailed task breakdown and status.
