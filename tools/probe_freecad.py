# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileNotice: Part of the CADet addon.
"""Probe the live FreeCAD API and the CADet context builder.

Run with FreeCAD's Python:

    "C:\\Program Files\\FreeCAD 1.1\\bin\\FreeCADCmd.exe" tools\\probe_freecad.py

It creates a scratch document, never saves it, and closes it at the end.
"""

import os
import sys

import FreeCAD as App
import Part
import Sketcher

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

import freecad  # noqa: E402

addon_path = os.path.join(REPO, "freecad")
if addon_path not in freecad.__path__:
    freecad.__path__.append(addon_path)

from freecad.CADet.analysis import analyze  # noqa: E402
from freecad.CADet.coach import answer, review_report  # noqa: E402
from freecad.CADet.context import build_snapshot  # noqa: E402


def main() -> int:
    doc = App.newDocument("CADetProbe")
    try:
        body = doc.addObject("PartDesign::Body", "Body")
        sketch = body.newObject("Sketcher::SketchObject", "Sketch")
        points = [
            App.Vector(0, 0, 0),
            App.Vector(40, 0, 0),
            App.Vector(40, 20, 0),
            App.Vector(0, 20, 0),
        ]
        for index in range(4):
            sketch.addGeometry(Part.LineSegment(points[index], points[(index + 1) % 4]), False)
        for index in range(4):
            sketch.addConstraint(Sketcher.Constraint("Coincident", index, 2, (index + 1) % 4, 1))
        sketch.addConstraint(Sketcher.Constraint("Horizontal", 0))
        sketch.addConstraint(Sketcher.Constraint("Vertical", 1))
        sketch.addConstraint(Sketcher.Constraint("Horizontal", 2))
        sketch.addConstraint(Sketcher.Constraint("Vertical", 3))
        sketch.addConstraint(Sketcher.Constraint("DistanceX", 0, 1, 0, 2, 40.0))
        sketch.addConstraint(Sketcher.Constraint("DistanceY", 1, 1, 1, 2, 20.0))
        pad = body.newObject("PartDesign::Pad", "Pad")
        pad.Profile = sketch
        pad.Length = 10.0
        doc.recompute()

        snapshot = build_snapshot(goal="a mounting plate")
        analysis = analyze(snapshot)
        print("goal:", snapshot.goal)
        print("score:", analysis.score)
        print("intent:", analysis.intent.label, "-", analysis.intent.description)
        print("bodies:", len(snapshot.doc.bodies) if snapshot.doc else 0)
        print("sketches:", len(snapshot.doc.sketches) if snapshot.doc else 0)
        print("issues:", [(issue.code, issue.severity) for issue in analysis.issues])
        print("praise:", [item.code for item in analysis.praise])
        print("next:", analysis.next_step)
        print("dims:", answer("what are the dimensions?", snapshot, analysis))
        print("printable:", answer("is this printable?", snapshot, analysis))
        print("--- review ---")
        print(review_report(snapshot, analysis))
        if snapshot.doc is None:
            print("PROBE_FAILED: no document in snapshot")
            return 1
        if not snapshot.doc.bodies:
            print("PROBE_FAILED: no body in snapshot")
            return 1
        if analysis.score <= 0:
            print("PROBE_FAILED: score did not compute")
            return 1
        print("PROBE_OK")
        return 0
    finally:
        App.closeDocument(doc.Name)


main()
