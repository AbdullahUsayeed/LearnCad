# LearnCad

A live CAD coach inside FreeCAD. It reads the active model, explains what is wrong, highlights the next control, and walks you through building a real part.

- Free, local-first, no account required.
- FreeCAD 1.1+ workbench.
- Deterministic review engine; optional AI explanations.
- Free community `.learncad` courses.

## Install

**Windows:** run `site/downloads/LearnCad-Setup-0.6.5.exe` and close FreeCAD first.

**Manual:** copy this folder into your FreeCAD `Mod` directory so `LearnCad/package.xml` exists:

```text
Windows  %APPDATA%\FreeCAD\v1-1\Mod\LearnCad
Linux    ~/.local/share/FreeCAD/Mod/LearnCad
macOS    ~/Library/Application Support/FreeCAD/Mod/LearnCad
```

Restart FreeCAD.

## Start

1. Select **LearnCad** in the workbench selector, or press `Ctrl+Shift+M`.
2. Type what you want to build in **Ask LearnCad**, for example `a phone stand`.
3. Press **Guide me**.
4. Follow the highlighted control in the panel.
5. Press **Fix constraints for me** when a sketch is under-constrained.
6. Use **Courses** for guided lessons, or **Import course...** for a downloaded `.learncad` package.
7. Export STL for printing or STEP for CAD exchange.

No Python packages are required. The local coach works offline.

## Learn more

- [GUIDE.md](GUIDE.md) - install, first project, panel buttons, courses, AI setup, troubleshooting.
- [docs/USAGE.md](docs/USAGE.md) - full usage reference.
- [docs/COURSES.md](docs/COURSES.md) - author and publish a course.

## Develop

```bash
python3 -m pytest -q
python3 tools/course_tool.py build
python3 tools/course_tool.py check site/courses/catalog.json
```

## License

Code: LGPL-2.1-or-later. The LearnCad name, logo, and course content are separate.
