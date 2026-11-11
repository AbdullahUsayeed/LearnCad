# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileNotice: Part of the CADet addon.
"""Structural tests for the guided courses. No FreeCAD required."""

from __future__ import annotations

from freecad.CADet import course

VALID_TARGETS = {
    "main:Sketch",
    "main:Pad",
    "main:Pocket",
    "main:Hole",
    "main:Fillet",
    "main:Export",
    "main:Render",
    "sketch:Rect",
    "sketch:Circle",
    "sketch:Line",
    "sketch:Coincident",
    "sketch:Dimension",
    "sketch:Dim",
    "sketch:Horizontal",
    "sketch:Horiz",
    "sketch:Vertical",
    "sketch:Vert",
    "sketch:Radius",
    "sketch:Done",
    "dialog:OK",
    "panel:primary",
    "panel:course",
    "panel:studio",
    "panel:render",
    "panel:setup",
    "panel:more",
    "panel:ask",
}


def test_two_courses():
    assert [item.id for item in course.COURSES] == ["starter", "phone_stand"]
    assert len(course.COURSES) == 2


def test_course_metadata_is_complete():
    for item in course.COURSES:
        assert item.title.strip()
        assert item.summary.strip()
        assert item.lessons
        for lesson in item.lessons:
            assert lesson.id.strip()
            assert lesson.title.strip()
            assert lesson.summary.strip()
            assert lesson.outcome.strip()
            assert lesson.walkthrough.steps


def test_lesson_ids_are_unique():
    ids = [lesson.id for lesson in course.LESSONS]
    assert len(ids) == len(set(ids))
    walkthroughs = [lesson.walkthrough.id for lesson in course.LESSONS]
    assert len(walkthroughs) == len(set(walkthroughs))


def test_phone_stand_course_shape():
    phone = course.course_by_id("phone_stand")
    assert phone is not None
    assert len(phone.lessons) == 4
    assert [lesson.id for lesson in phone.lessons] == [
        "phone_profile",
        "phone_pad",
        "phone_cable",
        "phone_finish",
    ]


def test_flat_lessons_and_lookups():
    assert len(course.LESSONS) == 7
    for item in course.COURSES:
        for lesson in item.lessons:
            assert course.lesson_by_id(lesson.id) is lesson
            assert course.course_for_lesson(lesson.id) is item
    assert course.lesson_by_id("missing") is None
    assert course.course_by_id("missing") is None


def test_walkthrough_targets_exist():
    for lesson in course.LESSONS:
        for step in lesson.walkthrough.steps:
            assert step.text.strip()
            if step.target:
                assert step.target in VALID_TARGETS, (lesson.id, step.target)
