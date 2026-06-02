# Quickstart — Jump In and Test

This guide gets you from a fresh clone to **watching seamless real-world terrain
stream and editing it**, in stages. You can stop after Stage 2 and have already
seen the core of the project working — no Unreal Engine, no API key, no GPU.

> **Two halves.** This project is a **Python terrain service** (fully runnable
> today) and an **Unreal Engine plugin** (compile it yourself in UE 5.5). Stages
> 1–3 are pure Python and run anywhere. Stage 4 is the engine.

---

## Stage 0 — Prerequisites

- **Python 3.10+**
- For the engine side later: **Unreal Engine 5.5+**.
- No API key needed: the default **`synthetic`** provider generates deterministic
  terrain offline. (For *real Earth*, grab a free
  [OpenTopography API key](https://portal.opentopography.org/myopentopo) — see
  Stage 5.)

```bash
git clone <repo-url>
cd worldgen
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements-service.txt
```

`rasterio` ships GDAL wheels, so no separate GDAL install is needed on most
platforms.

---

## Stage 1 — Run the tests (≈1 min)

Prove the whole Python half works on your machine:

```bash
python -m pytest tests_service/ -q
```

You should see all tests pass. These include the two that matter most: that
adjacent tiles share **byte-identical edges** (no seams), and that edits persist
and stay seamless.

---

## Stage 2 — Start the service and smoke-test it (≈1 min)

In one terminal, start the demo backend (synthetic Denver, no key):

```bash
python -m tools.demo --port 8000
```

In another terminal, run the contract smoke test — it exercises the service
exactly the way the Unreal client will:

```bash
python -m tools.contract_smoke --url http://127.0.0.1:8000
```

Expected:

```
Contract smoke test PASSED
  samples_per_edge: ...
  seam_check: ok
  edit_check: ok
  undo_check: ok
```

You just validated streaming + editing + undo end to end over HTTP. 🎉

While the service is up, open <http://127.0.0.1:8000/docs> for interactive API
docs (FastAPI/Swagger). Try `GET /tile/0/0/0/manifest`.

> 🔒 The demo binds to `127.0.0.1` and has **no auth**. Don't expose it on a
> public interface. If you must, set `WORLDGEN_API_TOKEN` to require a bearer
> token and front it with a rate-limiting proxy — see
> [`SECURITY.md`](../SECURITY.md).

---

## Stage 3 — Generate and look at terrain (optional, ≈2 min)

Create a project config and generate a block of tiles to disk:

```bash
python -m terrain_service.cli init --project-id demo \
    --lat 39.7392 --lon -104.9903 --tile-size-m 256 --mpp 4 \
    --provider synthetic -o demo.json

python -m terrain_service.cli generate -c demo.json --center 0 0 --radius 1
```

This writes 16-bit PNG previews + `.r16` heightmaps + manifests under
`.worldgen_cache/demo/`. Open the PNGs to see the terrain. Adjacent tiles line
up perfectly — that's the WorldGrid guarantee.

Want to stitch them into one image to *see* the seamlessness? Any 3×3 block of
PNGs tiles together with a 1-pixel shared edge (see `docs/GLOSSARY.md` →
"shared edge").

---

## Stage 4 — The full loop in Unreal Engine

Follow **[`unreal/DynamicWorldStreaming/EXAMPLE.md`](../unreal/DynamicWorldStreaming/EXAMPLE.md)**
— a step-by-step, no-Blueprint, no-VR first-compile walkthrough:

1. Keep `python -m tools.demo` running.
2. Copy `unreal/DynamicWorldStreaming/` into your project's `Plugins/`, compile.
3. Paste the input mappings, set the Service URL + GameMode (all in EXAMPLE.md).
4. Press Play → fly with WASD, hold LMB to raise terrain, fly to an edge and new
   terrain streams in, fly back and your edits persist.

> The Unreal C++ is written to the UE 5.5 API but **hasn't been compiled in a
> live engine yet**. Expect a few first-build API nits; `SETUP.md` lists the
> usual fixes. If you hit errors, that feedback is gold — file an issue.

---

## Stage 5 — Use real Earth terrain

Swap the synthetic provider for OpenTopography:

```bash
export OPENTOPOGRAPHY_API_KEY=your_key_here
python -m tools.demo --provider opentopography --dem-type SRTMGL1 \
    --lat 27.9881 --lon 86.9250 --port 8000      # Everest
```

Everything downstream (tiles, edits, the engine) is identical — only the data
source changes. Available DEM types depend on OpenTopography (e.g. `SRTMGL1`,
`NASADEM`, `COP30`).

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `ModuleNotFoundError: numpy/pyproj/rasterio` | `pip install -r requirements-service.txt` (in your venv) |
| Smoke test can't connect | Is `tools.demo` running on the same `--port`? |
| `No OpenTopography API key` | Use `--provider synthetic`, or set `OPENTOPOGRAPHY_API_KEY` |
| Tests fail on a fresh clone | Open an issue with the output — that's a real bug |
| Unreal: no terrain appears | Run `contract_smoke` first; check the Service URL and the Output Log for `LogDynamicWorldStreaming` |

See also: [ARCHITECTURE](ARCHITECTURE.md) · [CONTRACT](CONTRACT.md) ·
[GLOSSARY](GLOSSARY.md) · [ROADMAP](ROADMAP.md) · [CONTRIBUTING](../CONTRIBUTING.md)
