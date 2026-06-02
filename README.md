<h1 align="center">worldgen — Dynamic World Streaming</h1>

<p align="center"><em>A streamable, seamlessly-editable, persistent digital twin of the real Earth — built to be entered, at 1:1 scale, in VR.</em></p>

---

## The dream

Put on a headset. Pick **any** coordinate on Earth. Drop in at true 1:1 scale.
Walk in any direction *forever* as real-world terrain materialises ahead of you
with no loading screens and no visible seams — and reach out with your hands to
**sculpt, build, add, remove, and modify** anything. Leave, come back tomorrow,
and your changes are still there.

That's the destination. This repo is the engine being built toward it, in the
open.

## Where it is today

| Capability | Status |
|---|:--|
| Seamless real-Earth terrain streaming | 🟢 **Service done & tested** · UE plugin written |
| Persistent surface editing (sculpt) | 🟢 **Service done & tested** · UE hooks written |
| Desktop test harness + example pawn | 🟢 **Done** (try it now, no engine) |
| Unreal plugin compiled in a live engine | 🟡 Written to UE 5.5 API — **first compile pending** |
| Enter anywhere + large-world precision | ⚪ Planned (roadmap Phase 4) |
| VR presence & hand tools | ⚪ Planned (Phase 5) — sculpt hook already in place |
| Place / remove objects | ⚪ Planned (Phase 6) |
| Volumetric terrain (caves, overhangs) | ⚪ Planned (Phase 7) |

The **Python terrain service runs and is fully tested right now**. The **Unreal
C++ plugin is complete and structured** but hasn't been compiled in a live
engine yet — that's the current milestone.

## Try it in 5 minutes (no Unreal, no API key, no GPU)

```bash
git clone <repo-url> && cd worldgen
python -m venv venv && source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements-service.txt

python -m pytest tests_service/ -q                   # 1) everything passes

python -m tools.demo --port 8000 &                   # 2) start the terrain service
python -m tools.contract_smoke --url http://127.0.0.1:8000   # 3) validate it end-to-end
```

`Contract smoke test PASSED` means streaming + editing + undo all work on your
machine, over HTTP, exactly as the Unreal client will use them. Open
<http://127.0.0.1:8000/docs> to poke the API.

➡️ **Full guide, stage by stage:** [`docs/QUICKSTART.md`](docs/QUICKSTART.md)
(includes generating/visualising tiles, the in-engine loop, and switching to
real Earth data).

## How it works

Two halves that meet at one strict **[contract](docs/CONTRACT.md)**:

```
   Real DEM APIs        ┌─────────── PYTHON TERRAIN SERVICE ───────────┐
 (OpenTopography,  ───▶ │ providers → pipeline → WorldGrid → edit layer │
  or synthetic)         │ → cache → FastAPI                            │
                        └───────────────────────┬──────────────────────┘
                                       GET /tile/{level}/{x}/{y}  (.r16 + manifest)
                                       POST /edit                 (persistent sculpt)
                                                ▼
                        ┌──────── UNREAL ENGINE C++ PLUGIN ────────────┐
                        │ Prediction → StreamingManager → DataClient → │
                        │ TerrainTileActor (mesh · stitch · collision) │
                        │ + Sculpt tools (VR / desktop)                │
                        └──────────────────────────────────────────────┘
```

**Why there are never seams.** A naïve tiler scales each tile to its own
elevation range and the edges don't line up. Instead, this project uses a
**deterministic metric grid** where neighbouring tiles sample *identical* shared
edges, plus **absolute elevation encoding** (one project-wide range → one
constant world Z-scale). Seamlessness becomes a property *guaranteed by the
data*, not something fought at runtime — and the same trick keeps edits seamless
even when a brush stroke crosses tile boundaries.

Deep dive: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Repository layout

```
terrain_service/        Python service — the runnable, tested half
  tile_grid.py            WorldGrid: deterministic tile↔Earth math (the keystone)
  elevation.py            absolute uint16 encode/decode + NoData fill
  providers/              pluggable DEM sources (synthetic, opentopography)
  pipeline.py             fetch → reproject → resample → encode → manifest
  cache.py                on-disk tile cache + height round-trips
  edits.py, edit_store.py persistent surface-edit layer (op log + compositing)
  service.py, cli.py      FastAPI HTTP service + command line
tests_service/          pytest suite (seams, persistence, HTTP, smoke)
tools/                  demo.py (one-command service) · contract_smoke.py
unreal/DynamicWorldStreaming/   UE 5.5 C++ plugin (+ SETUP.md, EXAMPLE.md)
docs/                   architecture · contract · roadmap · quickstart · glossary
(repo root)             original single-shot importer tool (docs/LEGACY_IMPORTER.md)
```

## Run the full loop in Unreal Engine

When you're ready for the engine side, follow
[`unreal/DynamicWorldStreaming/EXAMPLE.md`](unreal/DynamicWorldStreaming/EXAMPLE.md):
copy the plugin in, paste the input config, set the service URL + a one-line
GameMode, press Play — then fly with WASD and sculpt terrain with the mouse. No
Blueprints, no VR required for the first compile. Build hiccups? See
[`SETUP.md`](unreal/DynamicWorldStreaming/SETUP.md) → "Common first-build fixes".

## Roadmap

Done: the terrain service + editable layer (tested), the UE plugin (written),
the test harness + example pawn. Next: compile in-engine, then enter-anywhere +
precision, VR tools, object placement, and volumetric terrain. Full breakdown:
[`docs/ROADMAP.md`](docs/ROADMAP.md).

## Contributing

This is a one-of-a-kind project and contributions are welcome. Good first steps:
get the service running ([QUICKSTART](docs/QUICKSTART.md)), then compile the UE
plugin and report build fixes, or add a DEM provider / edit-op. The one rule
that matters: the two halves share a contract — change it on both sides and bump
`schema_version`. See **[CONTRIBUTING.md](CONTRIBUTING.md)** and the
**[GLOSSARY](docs/GLOSSARY.md)**.

## Documentation

[Docs index](docs/README.md) ·
[Quickstart](docs/QUICKSTART.md) ·
[Architecture](docs/ARCHITECTURE.md) ·
[Contract](docs/CONTRACT.md) ·
[Roadmap](docs/ROADMAP.md) ·
[Glossary](docs/GLOSSARY.md) ·
[Contributing](CONTRIBUTING.md) ·
[Changelog](CHANGELOG.md)

## Acknowledgements & data

Elevation data via [OpenTopography](https://opentopography.org/) (SRTM, NASADEM,
Copernicus, …). Geocoding via OpenStreetMap
[Nominatim](https://operations.osmfoundation.org/policies/nominatim/) (mind its
usage policy). Built for [Unreal Engine](https://www.unrealengine.com/) 5.5+.

## License

MIT — see [`LICENSE`](LICENSE).

---

<p align="center"><sub>The original single-shot importer this grew from lives on in <a href="docs/LEGACY_IMPORTER.md">docs/LEGACY_IMPORTER.md</a>.</sub></p>
