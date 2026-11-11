# LearnCad

A CAD workspace with a live coach. It reads your model, explains what is wrong, highlights the next tool, and walks you through building a real part.

- Free and local-first. No account required.
- Live constraint, feature, and printability review.
- Optional AI explanations.
- Free community `.learncad` courses.
- Windows installer and Linux AppImage.

## Install

**Windows:** run `site/downloads/LearnCad-Setup-0.6.5.exe`.

**Linux:** build the AppImage with `./linux/build_appimage.sh`, or run LearnCad from the repository.

## Start

1. Open LearnCad.
2. Type what you want to build in **Ask LearnCad**, for example `a phone stand`.
3. Press **Guide me**.
4. Follow the highlighted control.
5. Press **Fix constraints for me** when a sketch is under-constrained.
6. Use **Courses** for guided lessons, or **Import course...** for a downloaded `.learncad` package.
7. Export STL for printing or STEP for CAD exchange.

## Learn more

- [GUIDE.md](GUIDE.md) - install, first project, panel controls, courses, AI setup, troubleshooting.
- [docs/COURSES.md](docs/COURSES.md) - author and publish a course.

## Develop

```bash
python3 -m pytest -q
python3 tools/course_tool.py build
python3 tools/course_tool.py check site/courses/catalog.json
```

## License

Code: LGPL-2.1-or-later. The LearnCad name, logo, and course content are separate.
