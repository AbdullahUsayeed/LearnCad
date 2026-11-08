# LearnCad

**A senior mechanical engineer, watching your FreeCAD model live.**

LearnCad is a FreeCAD workbench that reads the active document, understands what you are trying to build, and tells you what is working, what is wrong, and what to do next. It is not a chat toy that generates a model for you. It is the reviewer sitting next to a beginner, looking at the same screen.

This is the first working local build. The deterministic review engine is functional. The paid AI explanation layer is optional and off by default; the deterministic coach is free.

## Documentation

- [Usage guide](docs/USAGE.md) - install, first project, status pill, Guide me, AI setup, troubleshooting, and why this is a pro tool.
- [Landing page](site/README.md) - local preview, deployment, SEO checklist, and demo video instructions.
- [Installer notes](installer/README.txt) - what the Windows installer does and how to open LearnCad after installing.

## What it does

- Watches the active FreeCAD document while you work.
- Lets you state the goal in the panel ("a phone stand", "a bracket for a 40x40 extrusion"). The review is then checked against that goal, not just generic best practice.
- Infers intent from the goal, names, feature types, and proportions: "this looks like a flat plate", "this looks like a bracket".
- Reads bodies, sketches, constraints, dimensions, feature states, selection, edit mode, and the active workbench.
- Gives a simple status (Ready, On track, Needs work, Fix first) with earned praise and specific warnings.
- Explains the one next step in plain language.
- Answers questions locally, with no network: constraints, dimensions, printability, holes, walls, errors, and the next feature.
- Optionally sends a compact project summary to the LearnCad AI server for paid conversational explanations. Off by default.
- Applies a cleaner SolidWorks-like viewport with one click: anti-aliasing, gradient background, SolidWorks navigation, orthographic camera, smooth tessellation, light gray bodies with dark edges, and larger icons.
- Exports the active solid to Blender for a photorealistic studio still, with a built-in light rig, camera, and shadow-catching floor.

The review is deterministic. The AI is an explanation layer, not the source of truth about geometry.

## What it checks today

Sketches:

- degrees of freedom, fully constrained state
- conflicting, redundant, partially redundant, and malformed constraints
- open profiles and zero-length edges
- missing coincident, horizontal/vertical, radius, and equality constraints
- unattached sketches
- tiny or huge geometry, tiny radii

Bodies and features:

- feature errors and invalid topology
- open shells and zero volume
- missing tip feature
- multiple bodies
- geometry far from the origin
- thin pads, small holes, low material fill
- missing fillets on larger parts

Design intent:

- solid brackets that should be pocketed
- solid enclosures that should be shelled
- thick plates and unstable phone stands

## Install on Windows

Use the installer when you want a normal Windows install:

```text
dist\LearnCad-Setup-<version>.exe
```

Close FreeCAD first, then run it. The installer copies the addon to
`%APPDATA%\FreeCAD\v1-1\Mod\LearnCad`, creates an uninstall entry in Windows
Apps & Features, and optionally adds a desktop shortcut to FreeCAD.

A portable build is also available:

```text
dist\LearnCad-<version>-portable.zip
```

Extract the `LearnCad` folder into `%APPDATA%\FreeCAD\v1-1\Mod\` so that
`LearnCad\package.xml` exists. No Python packages are required.

Unsigned installers may trigger a SmartScreen warning. For public distribution,
sign the executable with an Authenticode certificate:

```powershell
signtool sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 /a dist\LearnCad-Setup-<version>.exe
```

## Build the installer

The installer is built with Inno Setup 6. On Windows, install it per-user with
Scoop:

```powershell
scoop install inno-setup
```

Then build both artifacts:

```powershell
powershell -ExecutionPolicy Bypass -File .\installer\build_installer.ps1
powershell -ExecutionPolicy Bypass -File .\tools\build_portable.ps1
```

Outputs go to `dist\`. The build script reads the version from
`package.xml`, warns if the development junction exists, and prints the SHA256
hash.

Do not run the installer on a machine where `Mod\LearnCad` is a junction to a
source checkout. Test it on a clean Windows profile or a VM. The installer
copies real files into the Mod folder; it does not use the junction.

The addon installs as **LearnCad**, but the internal Python package is still named `CADet` (`freecad/CADet/`). That keeps upgrades, tests, and the existing settings layout stable while the product identity is LearnCad.

## Install locally (development)

FreeCAD 1.1 is expected. The addon uses the modern `freecad/CADet/` layout and the FreeCAD-provided Qt wrappers.

1. Clone or copy this repository to a permanent folder.
2. Link it into the FreeCAD user Mod directory. On Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\install_dev.ps1
```

The script creates a junction:

```text
%APPDATA%\FreeCAD\v1-1\Mod\LearnCad  ->  <repo>
```

You can also create it manually:

```powershell
New-Item -ItemType Junction -Path "$env:APPDATA\FreeCAD\v1-1\Mod\LearnCad" -Target "F:\CADet"
```

3. Restart FreeCAD.
4. Select **LearnCad** in the workbench selector, or press **Ctrl+Shift+M**.
5. The mentor dock opens on the right.

No Python dependencies are required. The addon uses only the FreeCAD API and the Python standard library.

## Using it

The default panel is intentionally small. It shows:

- **I'm making** ? one line for the goal. Press Enter after typing.
- **Status pill** ? Ready, On track, Needs work, or Fix first.
- **Do this next** ? one step, in plain language.
- **Guide me** ? the big button. It opens the workbench, sketch, or dialog needed for that step.
- **Your mentor says** ? the most important warning or praise, not a wall of text.

Press **More details** for the live context, the suggested sequence, the activity log, the full review, and the Ask box. The numeric score is in the full review.

**Setup** configures the paid AI subscription, AI server, privacy consent, and polling interval.

Example questions:

```text
what am I building?
why is my sketch not constrained?
what should I do next?
is this printable?
what are the dimensions?
why is this feature failing?
review this model
```

## How far the guidance goes

The **Guide Me** button can:

- create a document, a PartDesign Body, and a sketch attached to the XY plane;
- switch to Sketcher or PartDesign;
- enter sketch edit mode for the active or selected sketch, including sketches inside a body that is not currently active;
- run the solver detectors and preselect the exact two vertices that need a Coincident constraint;
- preselect a line that needs Horizontal/Vertical, or two lines that look equal;
- open the Pad dialog with the profile selected;
- select the top face and open the Hole dialog;
- preselect vertical edges and open the Fillet dialog;
- open the first failing feature;
- open the Export dialog with the solid selected.

It does **not**:

- click a specific toolbar button for you;
- silently edit geometry, apply constraints, or confirm a feature;
- draw a pixel-perfect arrow over a toolbar icon;
- know what an in-progress tool is doing with the mouse. It reads the document, the solver, and the selection, not the mouse.

That boundary is intentional. The product is a mentor, not a macro recorder. It sets the table; the user still does the work.

## AI is a paid add-on

The local mentor never needs the network and remains free.

AI explanations require an active subscription:

- Only a compact summary is sent: object names and labels, dimensions, constraint counts, states, and the review. Geometry files are never uploaded.
- The desktop app never stores a language-model key. It talks to the LearnCad AI server, which verifies the subscription and holds the provider key.
- Activation uses the email and license code issued after PayPal checkout. The returned access token is stored with Windows DPAPI on Windows.
- Consent is explicit. AI stays disabled until the user accepts the privacy note.
- If the server rejects the subscription or is unreachable, LearnCad falls back to the local answer.

## Subscription server contract

The desktop client expects these endpoints on the AI server:

```text
POST /v1/license/activate
  {"email": "...", "license_code": "...", "device_id": "..."}
  -> {"token": "...", "expires_at": "2027-01-01T00:00:00Z"}

GET /v1/license/me
  Authorization: Bearer <token>
  -> {"status": "active", "expires_at": "..."}

POST /v1/chat/completions
  Authorization: Bearer <token>
  body: OpenAI-compatible chat payload
  -> OpenAI-compatible response
```

`site/subscribe.html` contains the PayPal subscription button. It posts the
subscription ID and email to `POST /v1/paypal/checkout`; the server verifies the
subscription with PayPal, stores it, and emails the license code.

## Architecture

```text
freecad/CADet/
  init_gui.py        workbench and commands
  panel.py           dock UI, live cards, activity, settings
  engine.py          polling, change detection, transitions
  context.py         FreeCAD document -> plain Snapshot
  model.py           plain dataclasses (no FreeCAD, no Qt)
  intent.py          name/geometry/feature intent inference
  analysis.py        deterministic senior-engineer rules
  coach.py           local answers and full review
  ai_client.py       paid AI client for the LearnCad server
  cloud_ai.py        activation, status and chat proxy calls
  settings.py        local config
  secret_store.py    Windows DPAPI / file fallback
  resources/icons/   workbench icon
```

Design rules:

- The UI never talks to FreeCAD geometry directly; it consumes a Snapshot.
- The rules never import Qt or the AI client.
- The AI never executes code and never invents dimensions.
- Polling is cheap; the full review runs only when the document fingerprint changes.
- No third-party Python dependencies, so the addon can be installed cleanly from the Addon Manager.

## Development

Run the pure tests with any Python 3.11+ interpreter:

```powershell
python -m pytest -q
```

Probe the FreeCAD API and the live context builder with the FreeCAD Python:

```powershell
& "C:\Program Files\FreeCAD 1.1\bin\FreeCADCmd.exe" .\tools\probe_freecad.py
```

The probe creates a scratch document, builds a sketch and a pad, runs the context builder and the analysis, and prints the result. It does not modify your files.

## Status and roadmap

Working now:

- live document snapshot
- intent inference
- deterministic review rules
- live mentor panel
- local question answering
- full review report
- optional AI explanations
- local install script
- studio viewport preset (one-click visual polish)
- Blender studio render bridge (photorealistic stills with aluminum, plastic, and rubber presets)

Next:

- guided lessons with step validation
- "show me" demonstrations in a scratch document
- more design rules (fillets, draft, wall thickness, hole clearance)
- assembly-aware review
- packaging and Addon Index submission
- screenshots and a demo video

## Current limitations

- Tested with FreeCAD 1.1.1 on Windows. The code uses the FreeCAD-provided Qt wrappers, but Linux and macOS have not been verified yet.
- The design rules are deliberately conservative. Draft analysis, true wall-thickness measurement, tolerance stacks, and assembly clearance checks are not implemented yet.
- Guided lessons and "show me" demonstrations are the next product layer; the current build is the live reviewer.
- The AI is explanation-only. It never executes code or edits the model.

## Before publishing to the Addon Index

- Replace the placeholder maintainer email and repository URLs in `package.xml`.
- Add screenshots or a short demo GIF to the README.
- Tag a release and submit an Addon - Addition issue to `FreeCAD/Addons`.
- Keep the free addon substantially complete; the index does not accept alpha-level submissions.

## Privacy

LearnCad reads the open document locally. It does not save or upload geometry. Telemetry is not implemented. The only network call is an explicit AI request when the user has enabled AI and accepted the privacy note.

## License

Code: LGPL-2.1-or-later. See `LICENSE`.

The product name, lesson content, and future paid project packs are separate from the open-source code.
