# LearnCad guide

LearnCad is a coach inside FreeCAD. It reads the active document, explains what
is wrong, and highlights the next control. You still draw and confirm the
geometry.

## What you need

- FreeCAD 1.1 or newer.
- Windows for the tested build. Linux and macOS use the manual install.
- No Python packages or account for the local coach.

## Install

### Windows installer

1. Close FreeCAD.
2. Run `LearnCad-Setup-0.6.5.exe` from `site/downloads/`.
3. Reopen FreeCAD.

The installer copies LearnCad into
`%APPDATA%\FreeCAD\v1-1\Mod\LearnCad` and adds an uninstall entry.

### Manual install

Copy this repository into the FreeCAD `Mod` folder so this file exists:

```text
<Mod>/LearnCad/package.xml
```

Common locations:

```text
Windows  %APPDATA%\FreeCAD\v1-1\Mod\
Linux    ~/.local/share/FreeCAD/Mod/
macOS    ~/Library/Application Support/FreeCAD/Mod/
```

Restart FreeCAD after copying.

## Open LearnCad

1. Start FreeCAD.
2. Choose **LearnCad** in the workbench selector.
3. Or press `Ctrl+Shift+M` from any workbench.
4. The coach opens on the left.

If the panel is hidden, press `Ctrl+Shift+M` or use **View > Panels**.

## Your first part: a bracket

1. In **Ask LearnCad**, type `a bracket for a 40x40 extrusion` and press Enter.
2. Press **Guide me**. With no document open, it creates a document, a
   PartDesign Body, and a sketch on the XY plane.
3. Draw a rectangle with **Rect**. Click two opposite corners.
4. Select the bottom edge, click **Dimension**, and set 40 mm.
5. Select an upright edge, click **Dimension**, and set 40 mm.
6. Click **Done** to close the sketch.
7. Press **Guide me** to open the Pad dialog. Set the width and confirm.
8. Press **Guide me** again to select the top face and open the Hole dialog.
9. Add mounting holes, then press **Guide me** for Fillet and Export.
10. Export STL for printing or STEP for CAD exchange.

The goal is not to follow LearnCad forever. The goal is to learn the review.

## Read the panel

### Status

- **Ready** - no document, or nothing modeled yet.
- **On track** - no structural problems found.
- **Needs work** - valid enough to continue, but something is missing.
- **Fix first** - fix the highlighted problem before adding features.

### Main controls

- **Guide me** - opens the tool or selects the geometry needed for the next step.
- **Fix constraints for me** - appears when a sketch is under-constrained. It adds
  obvious coincident, horizontal/vertical, and dimension constraints.
- **Courses** - opens the guided lessons and installed community courses.
- **Ask LearnCad** - sets the project goal or answers a question.
- **Three-dot menu** - Courses, Import course, All tools, Studio look, Render
  studio, Setup, Collapse coach.

Guide me does not click toolbar buttons for you or confirm a feature. It sets the
table; you do the work.

## Courses

### Start a built-in course

1. Press **Courses** under the status.
2. Choose **Start here** or **Design a phone stand**.
3. Press **Start lesson**.
4. Follow the highlighted control. Progress is saved locally.

### Import a community course

1. Download a `.learncad` package from `site/courses/`.
2. In LearnCad, open **Courses** and press **Import course...**, or use
   **LearnCad > Import Course...**.
3. Choose the package. It is validated, then added to your course list.
4. Open **Courses** and start a lesson.

Packages are data only. They cannot execute code. See
[docs/COURSES.md](docs/COURSES.md) to author one.

## Optional AI explanations

The local coach is free and works offline. AI is off by default.

1. Open **Setup** from the three-dot menu.
2. Choose a provider:
   - **DeepSeek** - paste a DeepSeek API key.
   - **OpenAI-compatible** - enter a base URL, model, and key.
   - **Ollama** - run a local model such as `llama3.1`.
   - **LearnCad cloud** - activate with the email and license code.
3. Accept the privacy note, enable AI, and save.
4. Press **Test AI connection**.

Only a compact model summary and your question are sent. Geometry files are
never uploaded. If the provider fails, LearnCad falls back to the local answer.

## Studio look and render

- **Studio look** applies anti-aliasing, a gradient background, orthographic
  camera, light bodies, dark edges, and larger icons. Restart FreeCAD for icons
  and anti-aliasing.
- **Render studio** exports the active solid to Blender for a still image.
  Blender is optional; set its path in **Setup**.

## Troubleshooting

### LearnCad is not in the workbench selector

- Confirm FreeCAD 1.1 or newer.
- Confirm `<Mod>/LearnCad/package.xml` exists.
- Restart FreeCAD.

### Guide me cannot enter Sketcher

- Finish the current sketch with **Done**.
- Make sure the sketch belongs to the active PartDesign Body.

### The panel does not update

- Press **Review** or switch workbenches and back.
- Check that the intended document is active.

### A dialog did not open

- The tool may need a selection or an active body.
- Read the Activity tab, select the requested object, and try again.

### Pad does nothing

The profile is open or empty. Use **Coincident** to close the gaps and make one
closed wire.

### Remove LearnCad

Uninstall it from Windows Apps & Features, then delete
`%APPDATA%\FreeCAD\v1-1\LearnCad` to remove settings, the goal, and license data.

## Privacy

The local coach reads the open document and uploads nothing. Telemetry is not
implemented. The only network request is an AI explanation after you explicitly
enable AI and accept the privacy note.

## More documentation

- [docs/USAGE.md](docs/USAGE.md) - full reference.
- [docs/COURSES.md](docs/COURSES.md) - course package format and publishing.
- [site/README.md](site/README.md) - landing page and deployment notes.

## License

Code: LGPL-2.1-or-later. The LearnCad name, lesson text, and course packages are
licensed separately.
