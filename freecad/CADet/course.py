# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileNotice: Part of the CADet addon.
"""The LearnCad courses.

Two courses share the same guided-walkthrough engine as the coach:

- Start here: the three core moves every part needs.
- Design a phone stand: a real desk part from profile to printable STL.

The panel stores completion by lesson id in the local settings file so progress
survives restarts and adding a course does not reset the old one.
"""

from __future__ import annotations

from dataclasses import dataclass

from .guide import Walkthrough, WalkthroughStep


@dataclass(frozen=True)
class Lesson:
    id: str
    title: str
    summary: str
    outcome: str
    walkthrough: Walkthrough


@dataclass(frozen=True)
class Course:
    id: str
    title: str
    summary: str
    lessons: tuple[Lesson, ...]


LESSON_ONE = Lesson(
    "sketch",
    "Sketch a sized profile",
    "Open a sketch, draw a rectangle, and give one edge a real size.",
    "A closed profile with a dimension on it.",
    Walkthrough(
        "course_sketch",
        "Lesson 1 - Sketch a sized profile",
        (
            WalkthroughStep(
                "Click Sketch on the main toolbar, then choose the XY plane. "
                "It is glowing orange.",
                target="main:Sketch",
                when="not_sketch",
                wait_for_sketch=True,
            ),
            WalkthroughStep(
                "Click Rect in the sketch toolbar. It is glowing orange.",
                target="sketch:Rect",
            ),
            WalkthroughStep(
                "Click one corner, then the opposite corner in the 3D view. "
                "Then click Next."
            ),
            WalkthroughStep(
                "Select one edge, then click Dim. It is glowing orange.",
                target="sketch:Dim",
            ),
            WalkthroughStep(
                "Type the size in the LearnCad dialog, then click OK.",
                target="dialog:OK",
            ),
            WalkthroughStep(
                "Click Done to close the sketch.",
                target="sketch:Done",
            ),
            WalkthroughStep(
                "Lesson 1 complete. You have a closed, sized profile."
            ),
        ),
    ),
)


LESSON_TWO = Lesson(
    "constrain",
    "Constrain it",
    "Join the corners and lock the lines horizontal or vertical so the profile stops moving.",
    "A sketch that reports 0 degrees of freedom.",
    Walkthrough(
        "course_constrain",
        "Lesson 2 - Constrain the profile",
        (
            WalkthroughStep(
                "Double-click the sketch in the Model tree to reopen it, then click Next."
            ),
            WalkthroughStep(
                "Select two endpoints that should touch, then click Coincident. "
                "It is glowing orange.",
                target="sketch:Coincident",
            ),
            WalkthroughStep(
                "Select a line that should be level, then click Horiz.",
                target="sketch:Horiz",
            ),
            WalkthroughStep(
                "Select an upright line, then click Vert.",
                target="sketch:Vert",
            ),
            WalkthroughStep(
                "Select edges and click Dim until the coach says 0 DoF left.",
                target="sketch:Dim",
            ),
            WalkthroughStep(
                "Lesson 2 complete. The geometry should stop jumping when you drag it."
            ),
        ),
    ),
)


LESSON_THREE = Lesson(
    "part",
    "Pad and export",
    "Turn the profile into a solid and save it as STL or STEP.",
    "A real file you can print or share.",
    Walkthrough(
        "course_part",
        "Lesson 3 - Pad and export",
        (
            WalkthroughStep(
                "If the sketch is still open, click Done to close it.",
                target="sketch:Done",
                when="sketch",
            ),
            WalkthroughStep(
                "Select the sketch in the tree, then click Pad on the main toolbar. "
                "It is glowing orange.",
                target="main:Pad",
            ),
            WalkthroughStep(
                "Set the length in the LearnCad Pad dialog, then click OK.",
                target="dialog:OK",
            ),
            WalkthroughStep(
                "Click Export on the main toolbar. It is glowing orange.",
                target="main:Export",
            ),
            WalkthroughStep(
                "Choose STL for printing or STEP for CAD exchange, then save. "
                "Lesson 3 complete."
            ),
        ),
    ),
)


PHONE_PROFILE = Lesson(
    "phone_profile",
    "Sketch the side profile",
    "Draw the base, the sloped back, and the front lip as one closed outline.",
    "A closed side profile shaped like a phone stand.",
    Walkthrough(
        "course_phone_profile",
        "Phone stand 1 - Sketch the side profile",
        (
            WalkthroughStep(
                "Click Sketch on the main toolbar, then choose the XY plane. "
                "It is glowing orange.",
                target="main:Sketch",
                when="not_sketch",
                wait_for_sketch=True,
            ),
            WalkthroughStep(
                "Click Line in the sketch toolbar. It is glowing orange.",
                target="sketch:Line",
            ),
            WalkthroughStep(
                "Click the bottom-left corner, then the bottom-right, up the back, "
                "forward along the top slope, down to the lip, and back to the start. "
                "Right-click or Escape to finish, then click Next."
            ),
            WalkthroughStep(
                "Select two endpoints that should touch, then click Coincident. "
                "Repeat for every open corner.",
                target="sketch:Coincident",
            ),
            WalkthroughStep(
                "Select the base edge, then click Horiz. Select the front lip and "
                "click Horiz again.",
                target="sketch:Horizontal",
            ),
            WalkthroughStep(
                "Select the back edge, then click Vert.",
                target="sketch:Vertical",
            ),
            WalkthroughStep(
                "Select the base edge, then click Dim. A phone stand is usually "
                "80-100 mm deep.",
                target="sketch:Dimension",
            ),
            WalkthroughStep(
                "Type the base depth in the LearnCad dialog, then click OK.",
                target="dialog:OK",
            ),
            WalkthroughStep(
                "Select the back edge, click Dim, and set the height to roughly "
                "110-130 mm.",
                target="sketch:Dimension",
            ),
            WalkthroughStep(
                "Type the height in the LearnCad dialog, then click OK.",
                target="dialog:OK",
            ),
            WalkthroughStep(
                "Select the front lip, click Dim, and set 10-15 mm so the phone "
                "cannot slide off.",
                target="sketch:Dimension",
            ),
            WalkthroughStep(
                "Type the lip size in the LearnCad dialog, then click OK.",
                target="dialog:OK",
            ),
            WalkthroughStep(
                "Click Done to close the sketch. The coach should report 0 DoF left.",
                target="sketch:Done",
            ),
        ),
    ),
)


PHONE_PAD = Lesson(
    "phone_pad",
    "Give the stand its width",
    "Pad the side profile into a solid that matches your phone.",
    "A solid phone stand body.",
    Walkthrough(
        "course_phone_pad",
        "Phone stand 2 - Pad the stand to width",
        (
            WalkthroughStep(
                "If the profile sketch is still open, click Done in the sketch toolbar.",
                target="sketch:Done",
                when="sketch",
            ),
            WalkthroughStep(
                "Select the closed profile, then click Pad on the main toolbar. "
                "It is glowing orange.",
                target="main:Pad",
            ),
            WalkthroughStep(
                "Set the width in the LearnCad Pad dialog. Most phones are "
                "70-80 mm wide, so 75 mm is a safe start.",
                target="dialog:OK",
            ),
            WalkthroughStep(
                "The profile is now a solid. Orbit the view and check that the "
                "stand is wider than the phone."
            ),
        ),
    ),
)


PHONE_CABLE = Lesson(
    "phone_cable",
    "Add the cable opening",
    "Cut a pass-through near the back so the charging cable fits while the phone sits in the stand.",
    "A cable opening in the stand.",
    Walkthrough(
        "course_phone_cable",
        "Phone stand 3 - Add a cable opening",
        (
            WalkthroughStep(
                "Select the face where the cable should pass, then click Next."
            ),
            WalkthroughStep(
                "Click Sketch on the main toolbar and choose that face.",
                target="main:Sketch",
            ),
            WalkthroughStep(
                "Click Circle in the sketch toolbar. It is glowing orange.",
                target="sketch:Circle",
            ),
            WalkthroughStep(
                "Click the centre for the cable, then drag a radius of about "
                "8-10 mm. Click Next."
            ),
            WalkthroughStep(
                "Select the circle edge, then click Radius to set the size.",
                target="sketch:Radius",
            ),
            WalkthroughStep(
                "Type the radius in the LearnCad dialog, then click OK.",
                target="dialog:OK",
            ),
            WalkthroughStep(
                "Click Done to close the sketch.",
                target="sketch:Done",
            ),
            WalkthroughStep(
                "Open the Model menu and choose Pocket. The menu button is glowing orange.",
                target="main:Pocket",
            ),
            WalkthroughStep(
                "Set the depth so the cut reaches through the back wall, then click OK.",
                target="dialog:OK",
            ),
            WalkthroughStep(
                "The cable opening is cut. Check that the phone still rests on the "
                "base, not on the cable."
            ),
        ),
    ),
)


PHONE_FINISH = Lesson(
    "phone_finish",
    "Fillet and export",
    "Soften the edges that touch the phone and the desk, then save a printable file.",
    "A printable STL or a STEP file for sharing.",
    Walkthrough(
        "course_phone_finish",
        "Phone stand 4 - Fillet and export",
        (
            WalkthroughStep(
                "Select the edges where the phone and the desk touch. Hold Ctrl to "
                "add more edges, then click Next."
            ),
            WalkthroughStep(
                "Open the Model menu and choose Fillet. The menu button is glowing orange.",
                target="main:Fillet",
            ),
            WalkthroughStep(
                "Set a 1-2 mm radius in the LearnCad Fillet dialog, then click OK.",
                target="dialog:OK",
            ),
            WalkthroughStep(
                "Click Export on the main toolbar. It is glowing orange.",
                target="main:Export",
            ),
            WalkthroughStep(
                "Choose STL for printing or STEP for CAD exchange, save the file, "
                "and print a test before the final copy."
            ),
        ),
    ),
)


COURSE_STARTER = Course(
    "starter",
    "Start here",
    "The three core moves every part needs: a sized sketch, a clean constraint set, and a pad.",
    (LESSON_ONE, LESSON_TWO, LESSON_THREE),
)


COURSE_PHONE = Course(
    "phone_stand",
    "Design a phone stand",
    "Build a real desk part from a side profile, then add the cable opening, fillets, and an export.",
    (PHONE_PROFILE, PHONE_PAD, PHONE_CABLE, PHONE_FINISH),
)


COURSES: tuple[Course, ...] = (COURSE_STARTER, COURSE_PHONE)

# Flat list keeps the progress counter, menu hints, and older callers working.
LESSONS: tuple[Lesson, ...] = tuple(
    lesson for course in COURSES for lesson in course.lessons
)

_INSTALLED: tuple[Course, ...] = ()


def register_installed(courses: tuple[Course, ...] | list[Course]) -> tuple[int, int]:
    """Register imported courses without replacing built-in ids."""
    used_courses = {item.id for item in COURSES}
    used_lessons = {lesson.id for lesson in LESSONS}
    accepted: list[Course] = []
    for item in courses:
        if item.id in used_courses:
            continue
        if any(lesson.id in used_lessons for lesson in item.lessons):
            continue
        accepted.append(item)
        used_courses.add(item.id)
        used_lessons.update(lesson.id for lesson in item.lessons)
    global _INSTALLED
    _INSTALLED = tuple(accepted)
    return len(accepted), len(courses)


def all_courses() -> tuple[Course, ...]:
    return COURSES + _INSTALLED


def all_lessons() -> tuple[Lesson, ...]:
    return tuple(lesson for item in all_courses() for lesson in item.lessons)


def course_by_id(course_id: str) -> Course | None:
    for item in all_courses():
        if item.id == course_id:
            return item
    return None


def lesson_by_id(lesson_id: str) -> Lesson | None:
    for lesson in all_lessons():
        if lesson.id == lesson_id:
            return lesson
    return None


def course_for_lesson(lesson_id: str) -> Course | None:
    for item in all_courses():
        if any(lesson.id == lesson_id for lesson in item.lessons):
            return item
    return None
