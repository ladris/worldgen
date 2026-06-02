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

## Branching & PR conventions

- **`main`** is the canonical, always-working core. Don't commit to it directly;
  branch off it.
- **Branch names** are typed by purpose:
  - `feat/<short-name>` — a new feature
  - `fix/<short-name>` — a bug fix
  - `docs/<short-name>` — documentation only
  - `refactor/<short-name>` / `chore/<short-name>` — internal / housekeeping
  - `exp/<short-name>` — experiments / spikes
- **Commits**: imperative mood, scoped where useful, e.g.
  `feat(service): add Copernicus DEM provider`. Explain *why* in the body when
  it isn't obvious.
- **Pull requests**: open against `main`, fill in the PR template, keep them
  small and focused. Draft early to get feedback before it's "done."
- **Keep green**: `python -m pytest tests_service/ -q` must pass; CI runs it on
  3.10/3.11/3.12.

## Workflow

1. `git switch main && git pull`, then `git switch -c feat/your-thing`.
2. Make focused commits with clear messages.
3. **Add or update tests** for any behaviour change on the Python side. The
   seam/persistence invariants are the project's crown jewels — protect them
   with tests.
4. Keep docs in step (contract, roadmap, glossary as relevant).
5. Open a PR against `main` using the template; link the issue/roadmap item.

There are no required approvals enforced yet (early project); favour small,
reviewable PRs and explain trade-offs. Be kind — see
[`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).

Looking for somewhere to start? See
[`docs/GOOD_FIRST_ISSUES.md`](docs/GOOD_FIRST_ISSUES.md).

## Coding conventions

**Python**
- Type hints throughout; `from __future__ import annotations` at module top.
- Docstrings on public functions/classes explaining *intent*, not mechanics.
- Pure, deterministic core (grid, encoding, edit ops) — no hidden global state;
  same inputs → same outputs. This is what makes caching and seamlessness work.
- Prefer NumPy vectorised ops over Python loops in the hot path.
- **Respect the resource limits.** Any request parameter that drives an
  allocation, a loop, generation work, or an outbound call must be bounded —
  add the bound to `terrain_service/limits.py` and enforce it at the HTTP
  boundary *and* defensively in the core. Never remove an existing bound. See
  `SECURITY.md` and the tests in `tests_service/test_security.py`.

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
