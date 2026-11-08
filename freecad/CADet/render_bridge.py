# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileNotice: Part of the CADet addon.
"""LearnCad studio render bridge.

FreeCAD's viewport is a fast OpenGL engineering view, not a photorealistic
renderer. For presentation images, LearnCad exports the active solid and runs
Blender headless with a studio scene. Blender does the lighting, shadows,
materials, anti-aliasing, and camera; LearnCad shows the resulting PNG.

This is a still-image bridge, not an interactive Blender viewport.
"""

from __future__ import annotations

import glob
import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass

from . import settings


BLENDER_DOWNLOAD = "https://www.blender.org/download/"


class RenderError(RuntimeError):
    def __init__(self, message: str, download_url: str = BLENDER_DOWNLOAD):
        super().__init__(message)
        self.message = message
        self.download_url = download_url


@dataclass
class RenderResult:
    path: str
    blender: str
    engine: str
    material: str = ""
    blend_path: str = ""


def _candidate_paths() -> list[str]:
    candidates: list[str] = []
    candidates.append(os.path.join(os.environ.get("USERPROFILE", ""), "scoop", "apps", "blender", "current", "blender.exe"))
    candidates.extend(glob.glob(r"C:\Program Files\Blender Foundation\Blender*\blender.exe"))
    candidates.extend(glob.glob(r"C:\Program Files\Blender Foundation\Blender\blender.exe"))
    candidates.extend(glob.glob(os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Blender Foundation", "Blender*", "blender.exe")))
    candidates.extend(glob.glob(os.path.join(os.environ.get("PROGRAMFILES", ""), "Blender Foundation", "Blender*", "blender.exe")))
    return [path for path in candidates if path and os.path.isfile(path)]


def find_blender(configured: str = "") -> str:
    if configured and os.path.isfile(configured):
        return configured
    found = shutil.which("blender")
    if found:
        return found
    candidates = _candidate_paths()
    if candidates:
        candidates.sort(reverse=True)
        return candidates[0]
    return ""


def render_script() -> str:
    return os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "resources",
        "blender",
        "learncad_render.py",
    )


def _export_stl(path: str) -> str:
    import FreeCAD as App

    doc = App.ActiveDocument
    if doc is None:
        raise RenderError("No document is open. Create a solid first.")

    selected = []
    try:
        import FreeCADGui as Gui

        selected = [item.Object for item in Gui.Selection.getSelectionEx()]
    except Exception:
        selected = []

    candidates = []
    for obj in selected:
        if getattr(obj, "Shape", None) is not None and getattr(obj.Shape, "Volume", 0) > 0:
            candidates.append(obj)
    if not candidates:
        for obj in doc.Objects:
            if str(getattr(obj, "TypeId", "")).startswith("PartDesign::Body"):
                if getattr(obj, "Shape", None) is not None and getattr(obj.Shape, "Volume", 0) > 0:
                    candidates.append(obj)
    if not candidates:
        for obj in doc.Objects:
            shape = getattr(obj, "Shape", None)
            if shape is not None and getattr(shape, "Volume", 0) > 0:
                candidates.append(obj)
    if not candidates:
        raise RenderError("No solid to render. Finish the Pad or Revolve first.")

    obj = candidates[0]
    try:
        obj.Shape.exportStl(path)
    except Exception as exc:
        raise RenderError(f"Could not export the solid for the studio engine: {exc}") from exc
    return str(getattr(obj, "Label", None) or getattr(obj, "Name", "solid"))


def render_preview(engine: str = "CYCLES", resolution: tuple[int, int] = (1200, 800), samples: int = 64, material: str = "aluminum") -> RenderResult:
    config = settings.load()
    blender = find_blender(str(config.get("blender_path", "") or ""))
    if not blender:
        raise RenderError(
            "The studio engine was not found. Reinstall LearnCad, or set its path in Setup."
        )
    script = render_script()
    if not os.path.isfile(script):
        raise RenderError("The LearnCad studio render script is missing.")

    render_dir = os.path.join(settings.config_dir(), "renders")
    os.makedirs(render_dir, exist_ok=True)
    stem = "learncad-render-" + time.strftime("%Y%m%d-%H%M%S")
    output = os.path.join(render_dir, stem + ".png")
    blend_path = os.path.join(render_dir, stem + ".blend")

    with tempfile.TemporaryDirectory(prefix="learncad-render-") as temp_dir:
        stl_path = os.path.join(temp_dir, "model.stl")
        label = _export_stl(stl_path)
        command = [
            blender,
            "--background",
            "--factory-startup",
            "--python",
            script,
            "--",
            stl_path,
            output,
            engine,
            str(int(resolution[0])),
            str(int(resolution[1])),
            str(int(samples)),
            str(material or "aluminum"),
            blend_path,
        ]
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=300,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except subprocess.TimeoutExpired as exc:
            raise RenderError("The studio render took longer than 5 minutes. Try a smaller resolution.") from exc
        except Exception as exc:
            raise RenderError(f"Could not start the studio engine: {exc}") from exc

    if completed.returncode != 0 or not os.path.isfile(output):
        tail = (completed.stderr or completed.stdout or "").strip().splitlines()[-8:]
        detail = "\n".join(tail) if tail else "No output from the studio engine."
        raise RenderError("The studio engine could not render the model.\n\n" + detail)
    return RenderResult(path=output, blender=blender, engine=engine, material=material, blend_path=blend_path)
