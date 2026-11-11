# LearnCad courses (V0)

V0 is a free, static course catalog. A course is a data-only `.learncad` zip
package. It contains a root `manifest.json` and optional preview or checkpoint
assets. LearnCad imports the package, adds it to the course list, and replays
the same guided walkthrough used by the built-in lessons.

There is no server, account, or payment flow in V0. Courses are submitted by
pull request and reviewed before they appear on the site.

## What a package contains

```text
my-course.learncad
  manifest.json
  media/preview.png        optional
  checkpoints/after-pad.FCStd   optional
```

`manifest.json`:

```json
{
  "schema": "learncad.course/1",
  "id": "desk-hook",
  "version": "1.0.0",
  "title": "Design a desk hook",
  "summary": "Sketch, pad, and fillet a printable hook in four lessons.",
  "author": "Your Name",
  "license": "CC-BY-SA-4.0",
  "difficulty": "beginner",
  "tags": ["cad", "beginner", "3d-printing"],
  "goal": "a desk hook",
  "learncad_min": "0.6.5",
  "lessons": [
    {
      "id": "profile",
      "title": "Sketch the side profile",
      "summary": "Draw one closed outline.",
      "outcome": "A closed, sized profile.",
      "walkthrough": {
        "id": "hook-profile",
        "title": "Desk hook 1 - Sketch the profile",
        "steps": [
          {
            "text": "Click Sketch, then choose the XY plane.",
            "target": "main:Sketch",
            "when": "not_sketch",
            "wait_for_sketch": true
          }
        ]
      }
    }
  ],
  "assets": [
    {
      "path": "media/preview.png",
      "sha256": "<lowercase sha256>",
      "size": 12345
    }
  ]
}
```

### Rules

- `id` is lowercase letters, digits, dots, dashes, or underscores.
- `version` is semantic, for example `1.0.0`.
- Lesson ids and walkthrough ids are unique within the package.
- `target` uses a stable UI id such as `main:Pad`, `sketch:Rect`,
  `dialog:OK`, or `panel:course`. Leave it empty for a reading step.
- `when` is empty, `sketch`, or `not_sketch`.
- Assets must be safe relative paths and use an allowed extension:
  `.fcstd`, `.stl`, `.step`, `.stp`, `.obj`, `.3mf`, `.png`, `.jpg`,
  `.jpeg`, `.webp`, `.svg`, `.md`, or `.txt`.
- Every asset is listed in `assets` with its SHA256 and size. Unlisted files are
  rejected.
- No Python, macros, executables, symlinks, hidden files, or path traversal.
- Packages are capped at 64 MB compressed and 128 MB uncompressed.

The importer validates the package before extracting it. The package cannot
execute code or write outside its course folder.

## Build and validate locally

Course sources live in `courses/`, one folder per course with a
`manifest.json`. From the repository root:

```bash
python3 tools/course_tool.py build
python3 tools/course_tool.py validate site/courses/packages/*.learncad
python3 tools/course_tool.py check site/courses/catalog.json
```

`build` packs every source folder into `site/courses/packages/`, removes stale
packages, and regenerates `site/courses/catalog.json`. `check` validates the
catalog, package paths, sizes, and checksums.

To pack a single course folder that already contains `manifest.json`:

```bash
python3 tools/course_tool.py pack path/to/course-folder my-course.learncad
python3 tools/course_tool.py validate my-course.learncad
```

To rebuild the catalog from an existing package directory without repacking:

```bash
python3 tools/course_tool.py catalog site/courses/packages \
  --out site/courses/catalog.json --package-base packages/
```

## Submit a course

1. Create a folder with `manifest.json` and any assets.
2. Pack it with `tools/course_tool.py pack`.
3. Run `validate` and confirm there are no errors.
4. Add the package to `site/courses/packages/`.
5. Rebuild `site/courses/catalog.json` with the `catalog` command.
6. Open a pull request. CI runs the tests and validates the catalog.
7. A maintainer reviews the lesson text, license, and assets.

V0 has no recording tool yet. Authors write manifests by hand or copy an
existing package and edit it. A semantic recorder is the next major piece.

## Licensing

- LearnCad code is LGPL-2.1-or-later.
- Course packages default to `CC BY-SA 4.0`. Use another license only if you
  have the right to do so, and put the license id in `manifest.json`.
- Do not upload a CAD document or image that contains someone else's
  proprietary design.
- The LearnCad name and logo are not covered by the code license.

## Safety and review

The V0 catalog is curated by pull request. Reviewers should check:

- The manifest validates and every asset hash matches.
- The course does not contain executable content or unexpected files.
- The lesson text describes the real LearnCad controls.
- The author has the right to share the model and images.
- The license is present and compatible with redistribution.

If a package is broken or unsafe, remove it from `site/courses/packages/`,
rebuild the catalog, and open a pull request.
