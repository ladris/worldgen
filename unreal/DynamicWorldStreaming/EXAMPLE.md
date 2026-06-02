# First-Compile Walkthrough (desktop, no VR, no Blueprints)

Goal: get the streaming + sculpting loop running in-engine with the least
possible setup, so you can validate the compile milestone. Everything here is
C++ and config — no asset wiring.

## 0. Validate the backend first (30 seconds, no engine)

Before touching Unreal, confirm the service end of the contract is healthy:

```bash
pip install -r requirements-service.txt
python -m tools.demo --port 8000            # synthetic Denver; no API key needed
# in another shell:
python -m tools.contract_smoke --url http://127.0.0.1:8000
```

You want `Contract smoke test PASSED`. If the engine later misbehaves but this
passes, the issue is on the Unreal side, not the data.

Leave `tools.demo` running — the engine points at it.

## 1. Install the plugin

1. Copy `unreal/DynamicWorldStreaming/` into `<YourProject>/Plugins/`.
2. Generate project files / open the project; let it compile the plugin.
3. Confirm the **GeometryScripting** plugin is enabled (it's a declared
   dependency). Restart if prompted.

## 2. Point the engine at the service

**Project Settings → Plugins → Dynamic World Streaming → Service Base Url** →
`http://127.0.0.1:8000`. Leave **Auto Start** on. A `LoadRadius` of 2 is fine to
begin.

## 3. Add input mappings

Paste into `<YourProject>/Config/DefaultInput.ini` (creates the legacy
action/axis mappings the example pawn uses). If the file exists, merge the
`[/Script/Engine.InputSettings]` section.

```ini
[/Script/Engine.InputSettings]
+ActionMappings=(ActionName="Sculpt_Raise",Key=LeftMouseButton)
+ActionMappings=(ActionName="Sculpt_Lower",Key=RightMouseButton)
+ActionMappings=(ActionName="Brush_Flatten",Key=F)
+ActionMappings=(ActionName="Brush_Smooth",Key=G)
+ActionMappings=(ActionName="Brush_RaiseLower",Key=R)
+ActionMappings=(ActionName="Brush_Bigger",Key=MouseScrollUp)
+ActionMappings=(ActionName="Brush_Smaller",Key=MouseScrollDown)
+ActionMappings=(ActionName="Sculpt_Undo",Key=Z)
+AxisMappings=(AxisName="MoveForward",Key=W,Scale=1.0)
+AxisMappings=(AxisName="MoveForward",Key=S,Scale=-1.0)
+AxisMappings=(AxisName="MoveRight",Key=D,Scale=1.0)
+AxisMappings=(AxisName="MoveRight",Key=A,Scale=-1.0)
+AxisMappings=(AxisName="MoveUp",Key=E,Scale=1.0)
+AxisMappings=(AxisName="MoveUp",Key=Q,Scale=-1.0)
+AxisMappings=(AxisName="Turn",Key=MouseX,Scale=1.0)
+AxisMappings=(AxisName="LookUp",Key=MouseY,Scale=-1.0)
```

> The example pawn inherits `ADefaultPawn` flight, which uses the `MoveForward/
> MoveRight/MoveUp/Turn/LookUp` axes above. (If your project uses Enhanced Input
> exclusively, ensure "bEnableLegacyInputScales"/legacy bindings are active, or
> rebind in your own Enhanced Input setup and call the pawn's handlers.)

## 4. Set the GameMode

Either set it project-wide (**Project Settings → Maps & Modes → Default
GameMode → `ExampleGameMode`**) or per-map (**World Settings → GameMode Override
→ `ExampleGameMode`**). `ExampleGameMode` spawns `ExampleExplorerPawn`.

Open or create a simple empty level with a directional light + sky. (A
PlayerStart anywhere is fine; the pawn lifts itself up at BeginPlay.)

## 5. Play

Press Play. The explorer pawn lifts above the origin and looks down; the
streaming manager auto-starts, fetches the project config, and tiles begin
appearing around you.

**Controls**
| Input | Action |
|-------|--------|
| W A S D / Q E | fly (Q/E down/up) |
| Mouse | look |
| Hold LMB | raise terrain where you look |
| Hold RMB | lower terrain |
| F / G / R | brush: Flatten / Smooth / Raise-Lower |
| Scroll | brush radius |
| Z | undo last edit |

Fly to a tile edge and keep going — new terrain should stream in seamlessly.
Sculpt a hill, fly away past the unload radius, fly back — it should still be
there (persistence via the service).

## Troubleshooting

- **No terrain appears**: is `tools.demo` running and reachable at the configured
  URL? Re-run `contract_smoke`. Check the Output Log for `LogDynamicWorldStreaming`.
- **"Project config invalid"** in the log: the service isn't reachable or returned
  an error — check the URL/port and firewall.
- **Terrain renders inside-out / black**: flip the triangle winding in
  `TerrainTileActor.cpp` (swap the two `AppendTriangle` arg orders) — a one-line
  change noted in the comments there.
- **Build errors**: see the "Common first-build fixes" section in `SETUP.md`
  (GeometryFramework headers, collision API, normal overlay API).

When this works on desktop, VR is the next step (`SETUP.md` §7): same plugin,
add an OpenXR pawn and put a `TerrainSculptComponent` on each motion controller.
```
