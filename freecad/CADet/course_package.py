# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileNotice: Part of the CADet addon.
"""Read, validate, pack, and install ``.learncad`` course packages.

Packages are data-only zip files. They contain a root ``manifest.json`` and
optional preview or checkpoint assets. No Python, macros, or executables are
allowed, and every asset must be listed with its SHA256 hash.

This module is pure Python. It does not import FreeCAD or Qt, so the workbench,
the command-line tool, and CI can all use it.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from . import course as course_module
from .guide import Walkthrough, WalkthroughStep


SCHEMA = "learncad.course/1"
CATALOG_SCHEMA = "learncad.catalog/1"
PACKAGE_SUFFIX = ".learncad"
MANIFEST_NAME = "manifest.json"
DEFAULT_LICENSE = "CC-BY-SA-4.0"

MAX_PACKAGE_BYTES = 64 * 1024 * 1024
MAX_TOTAL_UNCOMPRESSED = 128 * 1024 * 1024
MAX_FILE_BYTES = 32 * 1024 * 1024
MAX_FILES = 512
MAX_MANIFEST_BYTES = 1024 * 1024

DIFFICULTIES = {"beginner", "intermediate", "advanced"}
WHEN_VALUES = {"", "sketch", "not_sketch"}
ALLOWED_ASSET_SUFFIXES = {
    ".fcstd",
    ".stl",
    ".step",
    ".stp",
    ".obj",
    ".3mf",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".svg",
    ".md",
    ".txt",
}

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
_TARGET_RE = re.compile(r"^[a-z][a-z0-9_-]*:[A-Za-z0-9_.-]+$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class CoursePackageError(ValueError):
    """A course package or manifest failed validation."""

    def __init__(self, errors: Iterable[str]):
        self.errors = list(errors)
        super().__init__("; ".join(self.errors))


def _check_id(value: Any, field: str, errors: list[str]) -> None:
    if not isinstance(value, str) or not _ID_RE.fullmatch(value):
        errors.append(f"{field} must be lowercase letters, digits, dots, dashes, or underscores")


def _check_text(
    value: Any,
    field: str,
    errors: list[str],
    *,
    limit: int = 2000,
    required: bool = True,
) -> bool:
    if not isinstance(value, str):
        errors.append(f"{field} must be a string")
        return False
    if value != value.strip():
        errors.append(f"{field} must not start or end with whitespace")
    if required and not value.strip():
        errors.append(f"{field} must not be empty")
    if len(value) > limit:
        errors.append(f"{field} must be at most {limit} characters")
    return bool(value.strip())


def _safe_relpath(name: Any) -> str | None:
    if not isinstance(name, str) or not name or len(name) > 240:
        return None
    if name != name.strip() or name.startswith("/") or "\\" in name or ":" in name:
        return None
    path = PurePosixPath(name)
    if path.is_absolute() or not path.parts:
        return None
    if any(part in ("", ".", "..") or part.startswith(".") for part in path.parts):
        return None
    return path.as_posix()


def _safe_asset_path(name: Any) -> str | None:
    safe = _safe_relpath(name)
    if safe is None:
        return None
    if PurePosixPath(safe).suffix.lower() not in ALLOWED_ASSET_SUFFIXES:
        return None
    return safe


def validate_manifest(data: Any) -> list[str]:
    """Return every schema error in a course manifest."""
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["manifest must be a JSON object"]

    if data.get("schema") != SCHEMA:
        errors.append(f"schema must be {SCHEMA!r}")

    _check_id(data.get("id"), "id", errors)

    version = data.get("version")
    if not isinstance(version, str) or not _VERSION_RE.fullmatch(version):
        errors.append("version must be a semantic version such as 1.0.0")

    for field in ("title", "summary", "author", "license", "freecad_min", "learncad_min"):
        _check_text(data.get(field), field, errors, limit=500)

    difficulty = data.get("difficulty", "beginner")
    if difficulty not in DIFFICULTIES:
        errors.append(f"difficulty must be one of {sorted(DIFFICULTIES)}")

    goal = data.get("goal", "")
    if goal:
        _check_text(goal, "goal", errors, limit=500, required=False)

    tags = data.get("tags", [])
    if not isinstance(tags, list):
        errors.append("tags must be a list")
        tags = []
    if len(tags) > 12:
        errors.append("tags may contain at most 12 items")
    for index, tag in enumerate(tags):
        _check_text(tag, f"tags[{index}]", errors, limit=32)

    lessons = data.get("lessons")
    if not isinstance(lessons, list) or not lessons:
        errors.append("lessons must be a non-empty list")
        lessons = []
    if len(lessons) > 100:
        errors.append("lessons may contain at most 100 items")

    seen_lessons: set[str] = set()
    seen_walkthroughs: set[str] = set()
    for index, lesson in enumerate(lessons):
        prefix = f"lessons[{index}]"
        if not isinstance(lesson, dict):
            errors.append(f"{prefix} must be an object")
            continue
        lesson_id = lesson.get("id")
        _check_id(lesson_id, f"{prefix}.id", errors)
        if isinstance(lesson_id, str):
            if lesson_id in seen_lessons:
                errors.append(f"{prefix}.id is duplicated")
            seen_lessons.add(lesson_id)
        for field in ("title", "summary", "outcome"):
            _check_text(lesson.get(field), f"{prefix}.{field}", errors, limit=1000)

        walkthrough = lesson.get("walkthrough")
        if not isinstance(walkthrough, dict):
            errors.append(f"{prefix}.walkthrough must be an object")
            continue
        walkthrough_id = walkthrough.get("id")
        _check_id(walkthrough_id, f"{prefix}.walkthrough.id", errors)
        if isinstance(walkthrough_id, str):
            if walkthrough_id in seen_walkthroughs:
                errors.append(f"{prefix}.walkthrough.id is duplicated")
            seen_walkthroughs.add(walkthrough_id)
        _check_text(walkthrough.get("title"), f"{prefix}.walkthrough.title", errors, limit=1000)

        steps = walkthrough.get("steps")
        if not isinstance(steps, list) or not steps:
            errors.append(f"{prefix}.walkthrough.steps must be a non-empty list")
            steps = []
        if len(steps) > 500:
            errors.append(f"{prefix}.walkthrough.steps may contain at most 500 items")
        for step_index, step in enumerate(steps):
            step_prefix = f"{prefix}.walkthrough.steps[{step_index}]"
            if not isinstance(step, dict):
                errors.append(f"{step_prefix} must be an object")
                continue
            _check_text(step.get("text"), f"{step_prefix}.text", errors, limit=2000)
            target = step.get("target", "")
            if target and (not isinstance(target, str) or not _TARGET_RE.fullmatch(target)):
                errors.append(f"{step_prefix}.target must look like main:Pad or sketch:Rect")
            when = step.get("when", "")
            if when not in WHEN_VALUES:
                errors.append(f"{step_prefix}.when must be empty, 'sketch', or 'not_sketch'")
            wait_for_sketch = step.get("wait_for_sketch", False)
            if not isinstance(wait_for_sketch, bool):
                errors.append(f"{step_prefix}.wait_for_sketch must be a boolean")

    assets = data.get("assets", [])
    if not isinstance(assets, list):
        errors.append("assets must be a list")
        assets = []
    if len(assets) > MAX_FILES:
        errors.append(f"assets may contain at most {MAX_FILES} items")
    seen_assets: set[str] = set()
    for index, asset in enumerate(assets):
        prefix = f"assets[{index}]"
        if not isinstance(asset, dict):
            errors.append(f"{prefix} must be an object")
            continue
        path = asset.get("path")
        safe = _safe_asset_path(path)
        if safe is None or safe != path:
            errors.append(f"{prefix}.path must be a safe relative asset path")
        elif safe in seen_assets:
            errors.append(f"{prefix}.path is duplicated")
        else:
            seen_assets.add(safe)
        sha256 = asset.get("sha256")
        if not isinstance(sha256, str) or not _SHA256_RE.fullmatch(sha256):
            errors.append(f"{prefix}.sha256 must be a lowercase SHA256 hex digest")
        size = asset.get("size")
        if size is not None and (
            not isinstance(size, int) or size < 0 or size > MAX_FILE_BYTES
        ):
            errors.append(f"{prefix}.size must be a non-negative integer within the limit")

    preview = data.get("preview")
    if preview:
        if not isinstance(preview, str) or preview not in seen_assets:
            errors.append("preview must name a listed asset")

    return errors


def build_manifest(
    course: course_module.Course,
    *,
    version: str = "1.0.0",
    author: str = "LearnCad",
    license: str = DEFAULT_LICENSE,
    difficulty: str = "beginner",
    tags: Iterable[str] = (),
    goal: str = "",
) -> dict[str, Any]:
    """Build a manifest from an in-memory course."""
    manifest: dict[str, Any] = {
        "schema": SCHEMA,
        "id": course.id,
        "version": version,
        "title": course.title,
        "summary": course.summary,
        "author": author,
        "license": license,
        "difficulty": difficulty,
        "tags": list(tags),
        "goal": goal,
        "freecad_min": "1.1.0",
        "learncad_min": "0.6.5",
        "lessons": [],
        "assets": [],
    }
    for lesson in course.lessons:
        manifest["lessons"].append(
            {
                "id": lesson.id,
                "title": lesson.title,
                "summary": lesson.summary,
                "outcome": lesson.outcome,
                "walkthrough": {
                    "id": lesson.walkthrough.id,
                    "title": lesson.walkthrough.title,
                    "steps": [
                        {
                            "text": step.text,
                            "target": step.target,
                            "when": step.when,
                            "wait_for_sketch": step.wait_for_sketch,
                        }
                        for step in lesson.walkthrough.steps
                    ],
                },
            }
        )
    errors = validate_manifest(manifest)
    if errors:
        raise CoursePackageError(errors)
    return manifest


def course_from_manifest(manifest: dict[str, Any]) -> course_module.Course:
    """Rebuild an in-memory course from a validated manifest."""
    errors = validate_manifest(manifest)
    if errors:
        raise CoursePackageError(errors)
    lessons = []
    for item in manifest["lessons"]:
        walkthrough = item["walkthrough"]
        steps = tuple(
            WalkthroughStep(
                text=step["text"],
                target=step.get("target", ""),
                when=step.get("when", ""),
                wait_for_sketch=bool(step.get("wait_for_sketch", False)),
            )
            for step in walkthrough["steps"]
        )
        lessons.append(
            course_module.Lesson(
                id=item["id"],
                title=item["title"],
                summary=item["summary"],
                outcome=item["outcome"],
                walkthrough=Walkthrough(
                    id=walkthrough["id"],
                    title=walkthrough["title"],
                    steps=steps,
                ),
            )
        )
    return course_module.Course(
        id=manifest["id"],
        title=manifest["title"],
        summary=manifest["summary"],
        lessons=tuple(lessons),
    )


def _json_bytes(data: Any) -> bytes:
    return (
        json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False).encode("utf-8")
        + b"\n"
    )


def _write_zip(path: Path, files: dict[str, bytes]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, files[name])


def write_package(
    manifest: dict[str, Any],
    output: str | os.PathLike[str],
    assets: dict[str, bytes] | None = None,
) -> dict[str, Any]:
    """Write a package and return the normalized manifest."""
    payload_assets = dict(assets or {})
    data = dict(manifest)
    entries = []
    total = 0
    for name, blob in sorted(payload_assets.items()):
        safe = _safe_asset_path(name)
        if safe is None or safe != name:
            raise CoursePackageError([f"asset path is not allowed: {name!r}"])
        if not isinstance(blob, (bytes, bytearray)):
            raise CoursePackageError([f"asset {name!r} must be bytes"])
        blob = bytes(blob)
        if len(blob) > MAX_FILE_BYTES:
            raise CoursePackageError([f"asset {name!r} is larger than the file limit"])
        total += len(blob)
        if total > MAX_TOTAL_UNCOMPRESSED:
            raise CoursePackageError(["assets expand beyond the size limit"])
        entries.append(
            {
                "path": safe,
                "sha256": hashlib.sha256(blob).hexdigest(),
                "size": len(blob),
            }
        )
    data["assets"] = entries
    errors = validate_manifest(data)
    if errors:
        raise CoursePackageError(errors)
    files = {MANIFEST_NAME: _json_bytes(data)}
    files.update({name: bytes(blob) for name, blob in payload_assets.items()})
    _write_zip(Path(output), files)
    return data


def pack_directory(source: str | os.PathLike[str], output: str | os.PathLike[str]) -> dict[str, Any]:
    """Pack a directory containing ``manifest.json`` and its assets."""
    root = Path(source)
    manifest_path = root / MANIFEST_NAME
    if not manifest_path.is_file():
        raise CoursePackageError([f"{manifest_path} does not exist"])
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CoursePackageError([f"cannot read manifest: {exc}"]) from exc
    errors = validate_manifest(manifest)
    if errors:
        raise CoursePackageError(errors)

    assets: dict[str, bytes] = {}
    total = 0
    for file_path in sorted(root.rglob("*")):
        if not file_path.is_file():
            continue
        relative = file_path.relative_to(root).as_posix()
        if relative == MANIFEST_NAME:
            continue
        safe = _safe_asset_path(relative)
        if safe is None:
            raise CoursePackageError([f"file is not allowed in a package: {relative!r}"])
        size = file_path.stat().st_size
        if size > MAX_FILE_BYTES:
            raise CoursePackageError([f"file is larger than the file limit: {relative!r}"])
        total += size
        if total > MAX_TOTAL_UNCOMPRESSED:
            raise CoursePackageError(["assets expand beyond the size limit"])
        assets[safe] = file_path.read_bytes()
    return write_package(manifest, output, assets)


def _is_symlink(info: zipfile.ZipInfo) -> bool:
    return ((info.external_attr >> 16) & 0o170000) == 0o120000


def _read_package(package_path: str | os.PathLike[str]) -> tuple[dict[str, Any], dict[str, bytes]]:
    path = Path(package_path)
    try:
        package_size = path.stat().st_size
    except OSError as exc:
        raise CoursePackageError([f"cannot read {path}: {exc}"]) from exc
    if package_size > MAX_PACKAGE_BYTES:
        raise CoursePackageError(["package is larger than the size limit"])

    errors: list[str] = []
    files: dict[str, bytes] = {}
    seen: set[str] = set()
    total = 0
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            if len(infos) > MAX_FILES:
                raise CoursePackageError([f"package has more than {MAX_FILES} entries"])
            for info in infos:
                if info.is_dir():
                    continue
                name = info.filename
                if name != MANIFEST_NAME:
                    safe = _safe_asset_path(name)
                    if safe is None:
                        errors.append(f"file is not allowed in a package: {name!r}")
                        continue
                    name = safe
                if name.lower() in seen:
                    errors.append(f"duplicate package entry: {name!r}")
                    continue
                seen.add(name.lower())
                if _is_symlink(info):
                    errors.append(f"symlinks are not allowed: {name!r}")
                    continue
                if info.file_size > MAX_FILE_BYTES:
                    errors.append(f"file is larger than the file limit: {name!r}")
                    continue
                total += info.file_size
                if total > MAX_TOTAL_UNCOMPRESSED:
                    errors.append("package expands beyond the size limit")
                    break
                try:
                    files[name] = archive.read(info)
                except (OSError, zipfile.BadZipFile) as exc:
                    errors.append(f"cannot read {name!r}: {exc}")
    except zipfile.BadZipFile as exc:
        raise CoursePackageError(["not a valid .learncad zip package"]) from exc

    manifest_bytes = files.get(MANIFEST_NAME)
    if manifest_bytes is None:
        errors.append(f"package is missing {MANIFEST_NAME}")
        raise CoursePackageError(errors)
    if len(manifest_bytes) > MAX_MANIFEST_BYTES:
        raise CoursePackageError(["manifest is larger than the size limit"])
    try:
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CoursePackageError([f"manifest is not valid JSON: {exc}"]) from exc

    errors.extend(validate_manifest(manifest))
    listed: dict[str, dict[str, Any]] = {}
    if isinstance(manifest, dict) and isinstance(manifest.get("assets"), list):
        for asset in manifest["assets"]:
            if isinstance(asset, dict) and isinstance(asset.get("path"), str):
                listed[asset["path"]] = asset
    actual = set(files) - {MANIFEST_NAME}
    for name in sorted(actual - set(listed)):
        errors.append(f"unlisted package file: {name!r}")
    for name in sorted(set(listed) - actual):
        errors.append(f"missing package asset: {name!r}")
    for name in sorted(actual & set(listed)):
        asset = listed[name]
        digest = hashlib.sha256(files[name]).hexdigest()
        if asset.get("sha256") != digest:
            errors.append(f"checksum mismatch for {name!r}")
        if asset.get("size") is not None and asset.get("size") != len(files[name]):
            errors.append(f"size mismatch for {name!r}")

    if errors:
        raise CoursePackageError(errors)
    return manifest, files


def read_manifest(package_path: str | os.PathLike[str]) -> dict[str, Any]:
    """Validate a package and return its manifest."""
    manifest, _files = _read_package(package_path)
    return manifest


def validate_package(package_path: str | os.PathLike[str]) -> list[str]:
    """Return validation errors for a package, or an empty list."""
    try:
        _read_package(package_path)
    except CoursePackageError as exc:
        return exc.errors
    return []


def install_package(
    package_path: str | os.PathLike[str],
    courses_dir: str | os.PathLike[str],
) -> dict[str, Any]:
    """Validate and install a package into a courses directory."""
    manifest, files = _read_package(package_path)
    root = Path(courses_dir)
    root.mkdir(parents=True, exist_ok=True)
    target = root / manifest["id"]
    temp = Path(tempfile.mkdtemp(prefix=".learncad-", dir=str(root)))
    try:
        for name, blob in files.items():
            destination = temp / PurePosixPath(name)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(blob)
        if target.is_symlink() or target.is_file():
            target.unlink()
        elif target.is_dir():
            shutil.rmtree(target)
        os.replace(temp, target)
    finally:
        if temp.exists():
            shutil.rmtree(temp, ignore_errors=True)
    return manifest


def load_installed(courses_dir: str | os.PathLike[str]) -> list[course_module.Course]:
    """Load every valid installed package, skipping broken ones."""
    root = Path(courses_dir)
    if not root.is_dir():
        return []
    courses: list[course_module.Course] = []
    for directory in sorted(root.iterdir()):
        if not directory.is_dir() or directory.name.startswith("."):
            continue
        manifest_path = directory / MANIFEST_NAME
        if not manifest_path.is_file():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            courses.append(course_from_manifest(manifest))
        except (OSError, json.JSONDecodeError, CoursePackageError):
            continue
    return courses


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _catalog_entry(
    manifest: dict[str, Any],
    package_path: Path,
    package_base: str,
) -> dict[str, Any]:
    return {
        "id": manifest["id"],
        "version": manifest["version"],
        "title": manifest["title"],
        "summary": manifest["summary"],
        "author": manifest["author"],
        "license": manifest["license"],
        "difficulty": manifest["difficulty"],
        "goal": manifest.get("goal", ""),
        "tags": list(manifest.get("tags", [])),
        "lesson_count": len(manifest["lessons"]),
        "freecad_min": manifest["freecad_min"],
        "learncad_min": manifest["learncad_min"],
        "package": package_base + package_path.name,
        "sha256": _sha256_file(package_path),
        "size": package_path.stat().st_size,
    }


def build_catalog(
    packages: Iterable[str | os.PathLike[str]],
    *,
    package_base: str = "packages/",
) -> dict[str, Any]:
    """Build a catalog from package files."""
    base = package_base or ""
    if base and not base.endswith("/"):
        base += "/"
    entries = []
    seen: set[str] = set()
    for item in sorted(Path(package) for package in packages):
        manifest = read_manifest(item)
        if manifest["id"] in seen:
            raise CoursePackageError([f"duplicate course id in catalog: {manifest['id']!r}"])
        seen.add(manifest["id"])
        entries.append(_catalog_entry(manifest, item, base))
    return {"schema": CATALOG_SCHEMA, "courses": entries}


def validate_catalog(
    data: Any,
    *,
    root: str | os.PathLike[str] | None = None,
) -> list[str]:
    """Validate a catalog, and optionally its package files and checksums."""
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["catalog must be a JSON object"]
    if data.get("schema") != CATALOG_SCHEMA:
        errors.append(f"schema must be {CATALOG_SCHEMA!r}")
    courses = data.get("courses")
    if not isinstance(courses, list):
        return errors + ["courses must be a list"]

    seen: set[str] = set()
    base = Path(root) if root is not None else None
    for index, entry in enumerate(courses):
        prefix = f"courses[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{prefix} must be an object")
            continue
        for field in ("id", "version", "title", "summary", "author", "license", "package"):
            _check_text(entry.get(field), f"{prefix}.{field}", errors, limit=500)
        course_id = entry.get("id")
        if isinstance(course_id, str):
            if course_id in seen:
                errors.append(f"{prefix}.id is duplicated")
            seen.add(course_id)
        if entry.get("difficulty") not in DIFFICULTIES:
            errors.append(f"{prefix}.difficulty is invalid")
        tags = entry.get("tags", [])
        if not isinstance(tags, list):
            errors.append(f"{prefix}.tags must be a list")
        if not isinstance(entry.get("lesson_count"), int) or entry.get("lesson_count", 0) < 1:
            errors.append(f"{prefix}.lesson_count must be a positive integer")
        package = entry.get("package")
        safe = _safe_relpath(package)
        if safe is None or safe != package or not safe.endswith(PACKAGE_SUFFIX):
            errors.append(f"{prefix}.package must be a safe relative .learncad path")
        sha256 = entry.get("sha256")
        if not isinstance(sha256, str) or not _SHA256_RE.fullmatch(sha256):
            errors.append(f"{prefix}.sha256 must be a lowercase SHA256 hex digest")
        size = entry.get("size")
        if not isinstance(size, int) or size < 0:
            errors.append(f"{prefix}.size must be a non-negative integer")
        if base is not None and safe == package:
            package_path = base / PurePosixPath(safe)
            if not package_path.is_file():
                errors.append(f"{prefix}.package does not exist: {safe}")
            else:
                if _sha256_file(package_path) != sha256:
                    errors.append(f"{prefix}.sha256 does not match {safe}")
                if package_path.stat().st_size != size:
                    errors.append(f"{prefix}.size does not match {safe}")
    return errors


def write_catalog(path: str | os.PathLike[str], catalog: dict[str, Any]) -> None:
    errors = validate_catalog(catalog)
    if errors:
        raise CoursePackageError(errors)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(catalog, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
