# LearnCad usage guide

LearnCad is a coach inside FreeCAD. It reads the active document, explains what is
wrong, and opens the tool needed for the next step. It does not generate a
black-box model. You still draw, constrain, and confirm the feature.

## 1. Install

### Windows installer

1. Close FreeCAD.
2. Run `LearnCad-Setup-0.4.6.exe`.
3. The installer places LearnCad in the FreeCAD user Mod folder:
   `%APPDATA%\FreeCAD\v1-1\Mod\LearnCad`.
4. It creates an uninstall entry in Windows Apps & Features.
5. Optionally, it creates a desktop shortcut to FreeCAD.

The installer is per-user. It does not require an administrator password and
does not modify the FreeCAD installation folder.

### Portable zip

Extract the `LearnCad` folder from `LearnCad-0.4.6-portable.zip` into:

```text
%APPDATA%\FreeCAD\v1-1\Mod\
```

The result must be:

```text
%APPDATA%\FreeCAD\v1-1\Mod\LearnCad\package.xml
%APPDATA%\FreeCAD\v1-1\Mod\LearnCad\freecad\CADet\init_gui.py
```

No Python packages are required.

## 2. Open LearnCad

1. Start FreeCAD.
2. Select **LearnCad** in the workbench selector.
3. Or press `Ctrl+Shift+M` from any workbench.

The panel opens on the right. FreeCAD remembers the last workbench, so the next
launch is usually one click.

If the panel is already open but hidden, press `Ctrl+Shift+M` or use
**View > Panels**.

## 3. The first five minutes

1. In **I'm making**, type what you are building, for example:
   - `a phone stand`
   - `a bracket for a 40x40 extrusion`
   - `an enclosure for an ESP32 board`
2. Press Enter.
3. Press the big **Guide me** button.
4. Follow the next step in the panel.

With no document open, Guide me creates:

- a new document,
- a PartDesign Body,
- a sketch attached to the XY plane,
- Sketcher edit mode.

You draw the outer profile. LearnCad watches the solver and updates the review.

## 4. What the panel means

### Status pill

- **Ready** - no document, or nothing modeled yet.
- **On track** - the model has no structural problems and the goal checks pass.
- **Needs work** - the model is valid enough to continue, but something important
  is missing or risky.
- **Fix first** - a conflicting sketch, an open profile, an invalid solid, or a
  failing feature must be fixed before adding more.

### Do this next

One instruction. Not a wall of text. The first item is the immediate move.

### Guide me

This is the main button. It can:

- create a document, body, and attached sketch;
- switch to Sketcher or PartDesign;
- enter sketch edit mode;
- preselect the exact two vertices that need a Coincident constraint;
- preselect a line that should be Horizontal or Vertical;
- preselect two lines that look equal;
- open the Pad dialog with the profile selected;
- select the top face and open the Hole dialog;
- preselect vertical edges and open the Fillet dialog;
- open the first failing feature;
- open the Export dialog with the solid selected.

It does not click toolbar buttons for you, silently apply constraints, or
confirm a feature. Some dialogs are modal; close them when you are done.

### Your mentor says

The panel shows only the top warning or critical issue and one earned praise.
Each note has:

- **Fix / Watch** - what is wrong.
- **The reason** - why it matters for editing or printing.
- **Do** - the specific action.

Press **More details** for the full context, the complete plan, the activity
log, the full review, and the Ask box.

### More details

- **Plan** - the suggested sequence from the current state to export.
- **Activity** - live transitions: document opened, new warnings, resolved
  warnings, fully constrained sketches, clean solids, and Guide me actions.
- **Review** - a full engineering review you can copy into a design review or
  handoff.
- **Ask** - a question box. Without AI, the local mentor answers from the same
  deterministic analysis.

## 5. A first project: bracket

1. Set the goal: `a bracket for a 40x40 extrusion`.
2. Press **Guide me**.
3. Draw a rectangle and constrain it:
   - Coincident at the corners,
   - Horizontal and Vertical on the lines,
   - width and height dimensions,
   - anchor one corner to the origin.
4. Leave Sketcher. The panel should suggest **Open the Pad dialog**.
5. Press **Guide me**, set a thickness, and confirm the Pad.
6. The panel should now say **Needs work** and mention mounting holes.
7. Press **Guide me** to select the top face and open the Hole dialog.
8. Add the holes, confirm, and review the result.
9. Add small fillets to load-bearing corners.
10. Press **Guide me** when the panel suggests export, and save STL or STEP.

The goal is not to follow LearnCad forever. The goal is to internalize the review.

## 6. A first project: phone stand

1. Goal: `a phone stand`.
2. Sketch the side profile: a base, a sloped back, and a front lip.
3. Pad the profile.
4. Add a cable opening near the back.
5. Check the panel for the phone-stand checklist: base footprint, front lip,
   cable opening.
6. Export and test with the real phone before printing.

## 7. A first project: enclosure

1. Goal: `an enclosure for an ESP32 board`.
2. Model the outer shell first.
3. Hollow it with PartDesign Thickness or Shell.
4. Add standoffs at the board mounting holes.
5. Add connector cutouts.
6. Design the lid and the fastening method.
7. Check wall thickness and clearances before exporting.

## 8. AI explanations (paid add-on)

The deterministic mentor works offline and is free. AI explanations require an
active subscription and are off by default.

1. Press **Subscribe** in Setup and complete the PayPal subscription on the web page.
2. Check your email for the LearnCad license code.
3. In Setup, enter the AI server URL, the same email, and the license code.
4. Press **Activate**, accept the privacy note, enable AI, then Save.
5. Press **Check subscription** if you need to confirm the token.

What is sent: a compact summary of object names, dimensions, constraint counts,
states, and the deterministic review, plus your question. Geometry files are not
uploaded. The language-model key stays on the LearnCad server; the desktop app
stores only the access token with Windows DPAPI when available.

## Studio look (visual quality)

FreeCAD's default viewport is conservative: anti-aliasing is often off, the
background is flat, navigation may be Blender-style, curves can be coarse, and
the UI uses 16 px icons. That is why it can feel less polished than SolidWorks.

Press **Studio** in the LearnCad panel. It applies:

- MSAA 4x anti-aliasing (requires restart)
- a linear gradient background
- SolidWorks navigation
- an orthographic camera
- navigation cube on, axis cross off
- light gray bodies with dark edges, 2 px lines, Flat Lines display
- finer Part tessellation
- 24 px toolbar icons (requires restart)

Restart FreeCAD after pressing Studio for anti-aliasing and icons. For a light
UI, use **LearnCad > Studio Light Theme** from the workbench menu, then restart.

The full explanation and manual settings are on the landing page:
`site/freecad-look-like-solidworks.html`.

Studio changes presentation, not geometry. It does not make FreeCAD a
photorealistic renderer or a clone of SolidWorks.

## Studio render in Blender (optional)

The FreeCAD viewport is for editing. For a presentation image, LearnCad can
render the active solid in Blender with a studio light rig, camera, and soft
shadows.

1. Install Blender from <https://www.blender.org/download/> (or
   `scoop install blender`).
2. Open **Setup** in LearnCad and set the **Blender** path. The field
   auto-detects common install locations.
3. Choose a **Studio material**:
   - **Aluminum (brushed)** - metallic silver with a directional roughness texture.
   - **Plastic (satin orange)** - LearnCad orange with a clearcoat highlight.
   - **Rubber (matte black)** - high roughness with a fine surface bump.
4. Choose a **Render engine**: **Cycles** for accurate metal reflections, or
   **EEVEE** for a faster preview.
5. Click **Render** in the LearnCad panel, or use
   **LearnCad > Render Preview in Blender**.
6. LearnCad exports the active solid, runs Blender headless, and opens the
   resulting 1200x800 PNG. Use **Save image** to keep it.

The render takes roughly 10-90 seconds on a normal laptop. It is a still image,
not an interactive Blender viewport. Blender is optional; the mentor and the
orange/black viewport do not require it.

The bridge builds the material and studio lighting procedurally. It does not
download textures or HDRIs. Blender is a separate GPL application; LearnCad does
not ship Blender or link its source into FreeCAD.

## 9. Troubleshooting

### LearnCad is not in the workbench selector

- Confirm FreeCAD 1.1 or newer.
- Confirm this file exists:
  `%APPDATA%\FreeCAD\v1-1\Mod\LearnCad\package.xml`
- Restart FreeCAD.
- If using the portable zip, make sure the folder is `Mod\LearnCad\package.xml`,
  not `Mod\LearnCad\LearnCad\package.xml`.

### Guide me says it cannot enter Sketcher

- Double-click the sketch in the tree.
- Make sure the sketch belongs to a PartDesign Body.
- If the body is not active, activate it first.

### The panel does not update

- Press **Review** or switch away from the workbench and back.
- Check that the document is the active one.
- Restart FreeCAD if the panel was loaded from an older version.

### A dialog did not open

Some FreeCAD commands need a valid selection or an active body. Read the message
in the Activity tab, then select the requested object and try again.

### I installed while FreeCAD was running

Close FreeCAD and reopen it. Python modules are loaded at startup; the new
version is not hot-reloaded.

### I want a clean removal

Uninstall LearnCad from Windows Apps & Features. Then delete the settings folder:

```text
%APPDATA%\FreeCAD\v1-1\LearnCad
```

Deleting the settings folder removes the goal, the AI access token and the license metadata.

## 10. Why this is a pro tool

- **It reads the actual document.** The checks come from FreeCAD's solver and
  shape data, not from a screenshot or a language model's memory.
- **It separates facts from explanations.** Deterministic rules decide what is
  wrong. AI only explains; it cannot invent a dimension or silently change the
  model.
- **It teaches instead of hiding.** Every warning has a reason and a specific
  action. The geometry is preselected, but the user confirms the feature.
- **It is goal-aware.** A bracket and a phone stand have different failure
  modes. The review changes with the stated design intent.
- **It is local-first.** The free coach uploads nothing and needs no account.
  Paid AI is explicit, requires an active subscription, and sends only a compact
  model summary to the LearnCad server.
- **It produces reviewable output.** The full review can be copied into a
  handoff or design review. That is the difference between a toy and a tool.
- **It does not lock the model in.** It works on real FreeCAD files and the
  PartDesign tree. The model remains editable in FreeCAD.
- **It is honest about its limits.** It does not claim to be a slicer, a CAM
  system, or a replacement for engineering judgment. It flags what it can see
  and tells you what it cannot.

## 11. Limits

- Windows is the tested platform. The code uses FreeCAD's Qt wrappers, but Linux
  and macOS are not verified yet.
- True wall-thickness measurement, draft analysis, tolerance stacks, and
  assembly clearance checks are not implemented.
- The AI is explanation-only. It does not execute code or edit the model.
- The simple review is conservative. It will not catch every design error.
- FreeCAD 1.1+ is required.

## 12. Help and feedback

- Open an issue on the project repository.
- Include the FreeCAD version, the LearnCad version, the exact message in the
  Activity tab, and a screenshot if possible.
- For a bug in the installed build, test the portable zip to rule out a stale
  installation.
