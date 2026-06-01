# DynamicWorldStreaming — Unreal Setup Guide

This plugin streams real-world terrain tiles served by the worldgen Python
terrain service into a seamless, predictively-loaded world. Target engine:
**UE 5.5+**.

> Heads-up: this C++ was authored without an Unreal toolchain available, so it
> is written to the 5.5 API but has **not been compiled in-engine yet**. Expect
> to fix a few API mismatches on first build; the structure and logic are
> complete. Build errors are easiest to resolve against the notes below.

## 1. Install

1. Copy `unreal/DynamicWorldStreaming/` into your project's `Plugins/` folder.
2. Enable the **GeometryScripting** plugin (it is listed as a dependency and
   should auto-enable). Restart and let it compile.
3. Required modules (already in `Build.cs`): `GeometryFramework`, `GeometryCore`,
   `GeometryScriptingCore`, `HTTP`, `Json`, `JsonUtilities`,
   `ProceduralMeshComponent`.

## 2. Start the terrain service

From the repo root (Python side):

```bash
pip install -r requirements-service.txt
python -m terrain_service.cli init --project-id demo \
    --lat 39.7392 --lon -104.9903 --provider synthetic -o demo.json
python -m terrain_service.cli serve -c demo.json --host 0.0.0.0 --port 8000
```

Use `--provider opentopography` (and set `OPENTOPOGRAPHY_API_KEY`) for real
Earth terrain; `synthetic` needs no key or network and is perfect for first
bring-up.

## 3. Configure the plugin

**Project Settings → Plugins → Dynamic World Streaming**:
- **Service Base Url**: `http://127.0.0.1:8000` (or your host).
- **Load Radius / Unload Radius**: rings kept loaded / distance before unload.
- **Max Concurrent Fetches**, **Update Interval**, **Enable Stitching**.
- **Auto Start**: streams as soon as play begins.

## 4. Add prediction to your pawn (optional but recommended)

Add a **PlayerPredictionComponent** to your player pawn (C++ or Blueprint). It
extrapolates velocity to pre-load tiles ahead of travel. Without it, the manager
falls back to a plain radius block around the player.

## 5. Play

Hit Play. `URegionStreamingManager` (a world subsystem) fetches the project
config, then each update:
1. asks the predictor which tiles are needed,
2. fetches missing tiles from the service (bounded concurrency),
3. spawns `ATerrainTileActor`s that build `UDynamicMeshComponent` meshes on
   worker threads,
4. stitches new tiles to active neighbours,
5. unloads tiles behind the player.

The avatar can now walk indefinitely; terrain materialises ahead seamlessly.

## How seams are prevented

- **Geometry**: neighbouring tiles share identical edge sample positions
  (guaranteed by the WorldGrid + absolute encoding on the Python side), so
  vertices weld with zero gap — no cracks, ever.
- **Lighting**: `FTileStitcher` averages shared-edge vertex normals between
  adjacent tiles. (Recommended future optimisation: haloed heightmaps so edge
  normals match by construction — see `TileStitcher.cpp`.)

## Common first-build fixes

- **`UDynamicMeshComponent` / `UDynamicMesh` not found** → ensure
  GeometryScripting plugin is enabled and `GeometryFramework` is in `Build.cs`.
- **`FMeshNormals` / `FDynamicMesh3` include errors** → headers live under
  `DynamicMesh/` in `GeometryCore`.
- **`SetComplexAsSimpleCollisionEnabled` signature** → API has shifted across
  5.x; if it differs, use `MeshComponent->EnableComplexAsSimpleCollision()` /
  set `CollisionType` then `UpdateCollision(true)`.
- **Normal overlay element API** (`PrimaryNormals()`, `SetElement`) → verify
  against your engine version's `FDynamicMeshNormalOverlay`.

## Architecture map

| File | Role |
|------|------|
| `WorldGrid.h` | metric grid arithmetic (mirrors Python `tile_grid.py`) |
| `TerrainDataClient` | async HTTP fetch + JSON/`.r16` parsing |
| `TerrainTileActor` | heightmap → `UDynamicMeshComponent` on a worker thread |
| `TileStitcher` | shared-edge normal averaging |
| `PlayerPredictionComponent` | velocity/buffer-zone tile prediction |
| `RegionStreamingManager` | the orchestrator (world subsystem) |
| `DynamicWorldStreamingSettings` | Project Settings config |

See `docs/CONTRACT.md` for the exact data contract both halves implement.

## World Partition note

These dynamically-spawned tiles are streamed by `URegionStreamingManager`
itself (a custom streaming layer) and coexist with World Partition rather than
injecting into WP's runtime spatial hash. Injecting via
`InjectExternalStreamingObject` is possible but advanced (design report §6) and
is left as a future enhancement.
