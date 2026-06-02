# Contributing

Thanks for your interest — this is an unusual project (a persistent, editable,
VR digital twin of real Earth) and there's a lot of room to make a mark. This
guide gets you productive fast and explains the few rules that keep the two
halves of the system in sync.

> New here? Read [`docs/QUICKSTART.md`](docs/QUICKSTART.md) first to get the
> service running, then [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the
> big picture and [`docs/GLOSSARY.md`](docs/GLOSSARY.md) for the vocabulary.

## The shape of the repo

```
terrain_service/   Python: the terrain service (grid, providers, pipeline,
                   cache, edit layer, HTTP API). Fully testable here.
tests_service/     Pytest suite for terrain_service + tools.
tools/             demo launcher + contract smoke test.
unreal/            The UE 5.5 C++ plugin "DynamicWorldStreaming".
docs/              Architecture, contract, roadmap, quickstart, glossary.
(repo root)        The original single-shot importer tool (see
                   docs/LEGACY_IMPORTER.md). Maintained but not the focus.
```

Two halves meet at one **contract** (`docs/CONTRACT.md`). The golden rule:

> **If you change the WorldGrid math, the heightmap/manifest format, the
> elevation encoding, or the HTTP API, you change it on _both_ sides and bump
> `schema_version` in `CONTRACT.md`.** The Python `WorldGrid`/manifest and the
> Unreal `FWorldGrid`/parsers must agree exactly, or seams and misplacement
> appear.

## Dev setup

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements-service.txt
python -m pytest tests_service/ -q          # everything should pass
```

CI runs the suite on Python 3.10/3.11/3.12 (`.github/workflows/terrain-service-ci.yml`).

For the Unreal side you need UE 5.5+; see
[`unreal/DynamicWorldStreaming/SETUP.md`](unreal/DynamicWorldStreaming/SETUP.md).

## Workflow

1. Branch from the active development branch.
2. Make focused commits with clear messages (imperative mood: "add", "fix").
3. **Add or update tests** for any behaviour change on the Python side. The
   seam/persistence invariants are the project's crown jewels — protect them
   with tests.
4. Keep docs in step (contract, roadmap, glossary as relevant).
5. Open a PR describing *what* and *why*; link the roadmap item if there is one.

There are no required approvals enforced yet (early project); favour small,
reviewable PRs and explain trade-offs.

## Coding conventions

**Python**
- Type hints throughout; `from __future__ import annotations` at module top.
- Docstrings on public functions/classes explaining *intent*, not mechanics.
- Pure, deterministic core (grid, encoding, edit ops) — no hidden global state;
  same inputs → same outputs. This is what makes caching and seamlessness work.
- Prefer NumPy vectorised ops over Python loops in the hot path.

**Unreal C++**
- Match Unreal conventions (`UCLASS`/`USTRUCT`/`UPROPERTY`, `F`/`U`/`A`
  prefixes, `TObjectPtr`, `UE_LOG(LogDynamicWorldStreaming, …)`).
- Heavy work (mesh gen, fetch, collision) goes off the game thread; publish
  results back on the game thread. Never block the frame.
- All geodesy stays in Python; the engine consumes pre-computed manifest values.

## Common extension points (good places to start)

- **Add a DEM provider** — subclass `DEMProvider`, implement `sample_grid`,
  `@register_provider`. See `providers/synthetic.py` (analytic) and
  `providers/opentopography.py` (raster fetch + reproject). Candidates: USGS
  3DEP, Copernicus DEM, local GeoTIFF files.
- **Add an edit-op type** — extend `terrain_service/edits.py` (`apply_op`) and
  the `SURFACE_OPS` set, mirror it in the UE `EBrushType` + `ApplyBrushLocal`,
  and add a test proving it stays seamless across tiles.
- **Improve the UE plugin** — first valuable task is simply **compiling it in a
  live UE 5.5 project** and reporting the build fixes; see SETUP.md's
  "Common first-build fixes".
- **Roadmap phases 4–7** (enter-anywhere/precision, VR, objects, volumetric) —
  see `docs/ROADMAP.md`; these are big, design-first; open a discussion before
  large work.

## Reporting issues

Include: what you ran, what you expected, what happened, and your platform +
Python/UE version. For service bugs, the output of
`python -m tools.contract_smoke` against your running service is very helpful.

## A note on the data contract & determinism

The reason a brush stroke crossing a tile boundary leaves *zero* seam, and the
reason a tile generated today matches one cached last week, is that the entire
core is a **pure function of `(project config, tile index, op log)`**. When
adding features, preserve that property. If you find yourself reaching for
randomness, wall-clock time, or per-tile state that isn't derived from the
config, stop and reconsider — there's almost always a deterministic formulation.
