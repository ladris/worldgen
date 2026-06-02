# Changelog

All notable changes to this project. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); the project uses date-based
milestones during early development.

## [Unreleased] — Dynamic World Streaming (v2 line)

The project grew from a single-shot terrain importer into a system for
streaming and editing a persistent, real-world digital twin. Working toward the
ultimate goal: enter VR anywhere on Earth at 1:1 scale and sculpt/build/modify
persistently.

### Added — Python terrain service (`terrain_service/`)
- **WorldGrid** (`tile_grid.py`): deterministic tile↔Earth mapping in a metric
  UTM CRS, with exact shared edges between neighbours and per-tile sample grids.
- **Absolute elevation encoding** (`elevation.py`): project-wide uint16 mapping →
  constant world Z-scale; NoData hole-filling.
- **Providers** (`providers/`): pluggable `DEMProvider` registry; `synthetic`
  (offline analytic terrain) and `opentopography` (real Earth, reproject +
  resample onto the exact grid).
- **Pipeline** (`pipeline.py`): sample → fill NoData → absolute-encode → write
  `.r16`/`.png`/manifest.
- **Cache** (`cache.py`): on-disk tile cache with per-tile locking, generate-on-
  miss, prestage, and decode/encode height round-trips for editing.
- **HTTP service** (`service.py`, FastAPI): `/health`, `/project`, tile manifest
  & `heightmap.r16`, `/prestage`.
- **CLI** (`cli.py`): `init` / `generate` / `serve`.

### Added — Editable terrain layer (surface)
- **Brush ops** (`edits.py`): `raise_lower`, `flatten`, `smooth`, evaluated in
  world space so edits are seamless across tiles.
- **Edit store** (`edit_store.py`): authoritative op log (JSONL) + base-terrain
  snapshots; applies edits via a shared mosaic (seamless, drift-free); undo.
- **Endpoints**: `POST /edit`, `POST /edit/undo`, `GET …/edits`.

### Added — Unreal Engine plugin (`unreal/DynamicWorldStreaming/`, UE 5.5)
- `FWorldGrid`, `UTerrainDataClient` (async HTTP + JSON + `.r16`),
  `ATerrainTileActor` (heightmap → `UDynamicMeshComponent` on a worker thread,
  async collision), `FTileStitcher` (edge-normal averaging),
  `UPlayerPredictionComponent`, `URegionStreamingManager` (orchestrator
  subsystem), `UDynamicWorldStreamingSettings`.
- Runtime sculpting: `ApplyBrushLocal`, `PostEdit`/`PostUndo`, `ApplySculpt`,
  `UTerrainSculptComponent` (VR/desktop hook).
- Example content: `AExampleExplorerPawn`, `AExampleGameMode`.
- *Status: written to the UE 5.5 API; not yet compiled in a live engine.*

### Added — Tooling, tests, docs
- `tools/demo.py` (one-command service) and `tools/contract_smoke.py`
  (client-equivalent end-to-end validation).
- Test suite (`tests_service/`) incl. seam, persistence, and smoke tests; CI on
  Python 3.10/3.11/3.12.
- Docs: `ARCHITECTURE`, `CONTRACT` (v1.1), `ROADMAP`, `QUICKSTART`, `GLOSSARY`,
  plugin `SETUP`/`EXAMPLE`, `CONTRIBUTING`.

### Security (hardening of the now network-exposed service)
- **Resource bounds** (`terrain_service/limits.py`) enforced at the HTTP boundary
  and defensively in the core: tile `level` constrained to `[0, 24]` (fixes an
  unauthenticated memory-exhaustion DoS via negative `level`), bounded tile
  indices, capped edit `radius_m`/`iterations`/affected-tile count/mosaic size,
  and a `/prestage` tile-count cap.
- **Optional bearer-token auth** via `WORLDGEN_API_TOKEN` (all data endpoints);
  startup warns when running open, and binding beyond localhost warns.
- **Clean error mapping** (4xx/5xx, non-revealing messages) instead of bare 500s.
- **Secret hygiene**: OpenTopography API key redacted from upstream error text;
  NumPy `.npy` loaded with `allow_pickle=False`.
- Added `SECURITY.md` (threat model, private reporting, operator hardening).

### Design decisions
- Origin-anchored **metric** grid (UTM), not Web Mercator — true 1:1 scale.
- **Absolute** project-wide elevation encoding — constant world Z-scale.
- Pre-staged caching over live-blocking fetches.
- `UDynamicMeshComponent` primary mesh component (UE 5.5 Lumen path).

---

## Legacy importer

### v1.0.2 — 2023-10-29
- CLI via `argparse`; automatic UTM zone/EPSG detection for placename mode.

### v1.0.1 — 2023-10-28
- Tiling of large DEMs; geocoding + bbox-from-center; placename/bbox AOI modes.

### v1.0.0 — 2023-10-27
- Initial release: fetch DEM from OpenTopography, process to 16-bit heightmap
  (PNG & RAW+JSON), compute UE scale/location, generate import report.

See [`docs/LEGACY_IMPORTER.md`](docs/LEGACY_IMPORTER.md) for the standalone tool.
