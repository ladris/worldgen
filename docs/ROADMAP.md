# Roadmap & Status

Legend: ✅ done · 🟡 in progress · ⬜ todo · 🧪 has tests

## Phase 0 — Foundations
- ✅ `docs/ARCHITECTURE.md` — master blueprint
- ✅ `docs/CONTRACT.md` — Python↔Unreal contract (WorldGrid, encoding, formats, API)
- ✅ `docs/ROADMAP.md`

## Phase 1 — Python Terrain Service (fully runnable + tested) ✅
- ✅ `terrain_service/config.py` — project/grid config + derived constants
- ✅ `terrain_service/tile_grid.py` — **WorldGrid**: deterministic tile↔Earth math 🧪
- ✅ `terrain_service/elevation.py` — absolute uint16 encode/decode 🧪
- ✅ `terrain_service/providers/` — pluggable DEM sources (synthetic + OpenTopography) 🧪
- ✅ `terrain_service/pipeline.py` — fetch→reproject→resample→encode→manifest 🧪
- ✅ `terrain_service/cache.py` — on-disk tile cache + dedup + prestage
- ✅ `terrain_service/service.py` — FastAPI app implementing the HTTP contract 🧪
- ✅ `terrain_service/cli.py` — init/generate/serve commands
- ✅ CI: GitHub Actions running the test suite (30 tests, 3 Python versions)

## Phase 2 — Unreal C++ Plugin `DynamicWorldStreaming` (written; compile in-engine)
- ✅ Plugin scaffold: `.uplugin`, `Build.cs`, module bootstrap
- ✅ `FWorldGrid` — mirror of the Python grid math (matches `CONTRACT.md`)
- ✅ `UTerrainDataClient` — async HTTP fetch of `/project`, manifest + heightmap
- ✅ `ATerrainTileActor` — heightmap→`UDynamicMeshComponent`, worker-thread gen
- ✅ `FTileStitcher` — cross-tile shared-edge normal averaging
- ✅ Async collision cooking (`UpdateCollision(bAsyncCook=true)`)
- ✅ `UPlayerPredictionComponent` — velocity/trajectory + buffer zones
- ✅ `URegionStreamingManager` — world subsystem: fetch/spawn/stitch/unload
- ✅ `UDynamicWorldStreamingSettings` + `SETUP.md` build instructions
- ⬜ **Compile & validate in-engine** (needs a UE 5.5 install)
- ⬜ Runtime LOD pyramid (level>0 sampling is wired in the grid; mesh LOD TODO)
- ⬜ World Partition runtime-hash injection (currently a custom streaming layer)

## Phase 3 — Integration
- ⬜ Example project + example map setup guide
- ⬜ End-to-end "infinite walk" verification checklist
- ⬜ Performance pass (async profiling, memory budget)

## Ultimate goal: persistent, editable, VR digital twin of Earth

Enter VR at any chosen coordinate at 1:1 scale and physically sculpt, build,
add/remove, and modify anything — persistently.

### Phase 3 — Editable terrain layer (surface) ✅ (service); UE written
- ✅ `terrain_service/edits.py` — brush ops (raise/lower, flatten, smooth) 🧪
- ✅ `terrain_service/edit_store.py` — authoritative op log + base cache;
  seamless mosaic compositing; undo 🧪
- ✅ cache `decode_heights`/`write_heights`; service `/edit`, `/edit/undo`,
  tile edits 🧪
- ✅ CONTRACT v1.1 (editable-terrain section)
- ✅ UE: `ApplyBrushLocal`, `PostEdit/PostUndo`, `ApplySculpt`, `UndoLastEdit`,
  `UTerrainSculptComponent` (VR hook) — written; compile in-engine
- ⬜ Smooth-across-region-boundary refinement (minor; documented)
- ⬜ Material/biome paint layer (texture, not height)

### Phase 4 — Enter anywhere + large-world precision ⬜
- ⬜ Re-anchorable project origin / drop at any lat/lon at runtime
- ⬜ UE Large World Coordinates + World Partition origin rebasing for precision
  far from origin
- ⬜ "Teleport to coordinate" flow (and a place-search → coordinate helper)

### Phase 5 — VR presence & tools ⬜
- ⬜ OpenXR pawn, motion controllers, hand-driven brush UI/gizmos
- ⬜ 90fps perf pass: LOD pyramid, async budgeting, Lumen settings
- ⬜ Brush preview decal, strength/radius gestures

### Phase 6 — Build / add / remove objects ⬜
- ⬜ Place/remove props & meshes, persisted to the edit store (object layer)
- ⬜ Object persistence keyed to world coordinates; reload on stream-in

### Phase 7 — Volumetric terrain (caves/overhangs) ⬜
- ⬜ Voxel/SDF region type as a second layer alongside heightfield
- ⬜ Dual-contouring/marching-cubes meshing; add/remove solid matter
- ⬜ Volumetric edit ops extending the same op-log transport

## Known design decisions (locked unless revisited)
- Metric origin-anchored grid (UTM of origin), **not** Web Mercator — for true
  1:1 scale.
- Absolute project-wide elevation encoding → constant world Z-scale.
- `UDynamicMeshComponent` primary mesh component (UE 5.5 Lumen support);
  `RuntimeMeshComponent` documented alternative.
- Pre-staged caching over live-blocking fetches.
