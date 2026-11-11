# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileNotice: Part of the CADet addon.
"""Tests for the .learncad course package format. No CAD engine required."""

from __future__ import annotations

import json
import zipfile

import pytest

from freecad.CADet import course, course_package


def test_builtin_manifest_roundtrip():
    manifest = course_package.build_manifest(course.COURSE_STARTER)
    assert course_package.validate_manifest(manifest) == []
    restored = course_package.course_from_manifest(manifest)
    assert restored.id == "starter"
    assert [lesson.id for lesson in restored.lessons] == ["sketch", "constrain", "part"]
    assert restored.lessons[0].walkthrough.steps[0].target == "main:Sketch"


def test_pack_validate_install_and_load(tmp_path):
    manifest = course_package.build_manifest(course.COURSE_PHONE)
    package = tmp_path / "phone_stand.learncad"
    course_package.write_package(manifest, package)

    assert course_package.validate_package(package) == []

    installed_dir = tmp_path / "courses"
    installed = course_package.install_package(package, installed_dir)
    assert installed["id"] == "phone_stand"
    assert (installed_dir / "phone_stand" / "manifest.json").is_file()

    loaded = course_package.load_installed(installed_dir)
    assert [item.id for item in loaded] == ["phone_stand"]
    assert len(loaded[0].lessons) == 4


def test_pack_directory_with_asset(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    manifest = course_package.build_manifest(course.COURSE_STARTER)
    (source / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    media = source / "media"
    media.mkdir()
    (media / "plate.stl").write_bytes(b"solid plate\nendsolid plate\n")

    package = tmp_path / "starter.learncad"
    packed = course_package.pack_directory(source, package)
    assert packed["assets"][0]["path"] == "media/plate.stl"
    assert course_package.validate_package(package) == []


def test_reject_path_traversal(tmp_path):
    manifest = course_package.build_manifest(course.COURSE_STARTER)
    manifest["assets"] = [{"path": "../evil.txt", "sha256": "0" * 64, "size": 1}]
    package = tmp_path / "bad.learncad"
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        archive.writestr("../evil.txt", b"x")

    errors = course_package.validate_package(package)
    assert errors


def test_reject_executable_asset(tmp_path):
    manifest = course_package.build_manifest(course.COURSE_STARTER)
    with pytest.raises(course_package.CoursePackageError):
        course_package.write_package(
            manifest,
            tmp_path / "bad.learncad",
            {"evil.py": b"print('no')\n"},
        )


def test_reject_checksum_mismatch(tmp_path):
    manifest = course_package.build_manifest(course.COURSE_STARTER)
    manifest["assets"] = [{"path": "note.txt", "sha256": "0" * 64, "size": 2}]
    package = tmp_path / "bad.learncad"
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        archive.writestr("note.txt", b"ok")

    errors = course_package.validate_package(package)
    assert any("checksum mismatch" in error for error in errors)


def test_reject_invalid_target():
    manifest = course_package.build_manifest(course.COURSE_STARTER)
    manifest["lessons"][0]["walkthrough"]["steps"][0]["target"] = "not a target"
    errors = course_package.validate_manifest(manifest)
    assert any("target" in error for error in errors)


def test_installed_course_registers_without_replacing_builtins():
    lesson = course.Lesson(
        "extra-lesson",
        "Extra lesson",
        "A test lesson.",
        "A test outcome.",
        course.Walkthrough(
            "extra-walkthrough",
            "Extra walkthrough",
            (course.WalkthroughStep("Click Sketch.", target="main:Sketch"),),
        ),
    )
    extra = course.Course("extra-course", "Extra course", "A test course.", (lesson,))
    try:
        accepted, total = course.register_installed([extra, course.COURSE_STARTER])
        assert (accepted, total) == (1, 2)
        assert course.course_by_id("extra-course") is extra
        assert course.lesson_by_id("extra-lesson") is lesson
        assert course.course_by_id("starter") is course.COURSE_STARTER
        assert len(course.all_lessons()) == len(course.LESSONS) + 1
    finally:
        course.register_installed([])


def test_catalog_roundtrip(tmp_path):
    packages_dir = tmp_path / "packages"
    packages_dir.mkdir()
    package = packages_dir / "starter-1.0.0.learncad"
    course_package.write_package(
        course_package.build_manifest(course.COURSE_STARTER),
        package,
    )

    catalog = course_package.build_catalog([package])
    assert course_package.validate_catalog(catalog) == []

    catalog_path = tmp_path / "catalog.json"
    course_package.write_catalog(catalog_path, catalog)
    data = json.loads(catalog_path.read_text(encoding="utf-8"))
    assert course_package.validate_catalog(data, root=tmp_path) == []
    assert data["courses"][0]["lesson_count"] == 3
