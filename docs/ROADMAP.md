# Roadmap & Status

Legend: ✅ done · 🟡 in progress · ⬜ todo · 🧪 has tests

## Phase 0 — Foundations
- ✅ `docs/ARCHITECTURE.md` — master blueprint
- ✅ `docs/CONTRACT.md` — Python↔Unreal contract (WorldGrid, encoding, formats, API)
- ✅ `docs/ROADMAP.md`

## Phase 1 — Python Terrain Service (fully runnable + tested)
- 🟡 `terrain_service/config.py` — project/grid config + derived constants
- 🟡 `terrain_service/tile_grid.py` — **WorldGrid**: deterministic tile↔Earth math 🧪
- ⬜ `terrain_service/elevation.py` — absolute uint16 encode/decode 🧪
- ⬜ `terrain_service/providers/` — pluggable DEM sources (OpenTopography first)
- ⬜ `terrain_service/pipeline.py` — fetch→reproject→resample→encode→manifest 🧪
- ⬜ `terrain_service/cache.py` — on-disk tile cache + dedup + async prestage
- ⬜ `terrain_service/service.py` — FastAPI app implementing the HTTP contract 🧪
- ⬜ `terrain_service/cli.py` — generate/prestage/serve commands
- ⬜ CI: GitHub Actions running the test suite

## Phase 2 — Unreal C++ Plugin `DynamicWorldStreaming`
- ⬜ Plugin scaffold: `.uplugin`, `Build.cs`, module bootstrap
- ⬜ `FWorldGrid` — mirror of the Python grid math (must match `CONTRACT.md`)
- ⬜ `UTerrainDataClient` — async HTTP fetch of heightmap + manifest
- ⬜ `ATerrainTileActor` — heightmap→`UDynamicMeshComponent`, worker-thread gen
- ⬜ `UTileStitcher` — cross-tile shared-edge normal averaging
- ⬜ Runtime LOD (mesh simplification / multi-res sampling)
- ⬜ Async collision cooking
- ⬜ `UPlayerPredictionComponent` — velocity/trajectory + buffer zones
- ⬜ `URegionStreamingManager` — request queue, lifecycle, World Partition reg.
- ⬜ Dev notes: required plugins (GeometryScripting), build instructions

## Phase 3 — Integration
- ⬜ Example project + example map setup guide
- ⬜ End-to-end "infinite walk" verification checklist
- ⬜ Performance pass (async profiling, memory budget)

## Known design decisions (locked unless revisited)
- Metric origin-anchored grid (UTM of origin), **not** Web Mercator — for true
  1:1 scale.
- Absolute project-wide elevation encoding → constant world Z-scale.
- `UDynamicMeshComponent` primary mesh component (UE 5.5 Lumen support);
  `RuntimeMeshComponent` documented alternative.
- Pre-staged caching over live-blocking fetches.
