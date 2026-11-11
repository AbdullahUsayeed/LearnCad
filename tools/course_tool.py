#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileNotice: Part of the CADet addon.
"""Pack, validate, and catalog LearnCad course packages.

Examples:
    python3 tools/course_tool.py build
    python3 tools/course_tool.py validate site/courses/packages/*.learncad
    python3 tools/course_tool.py check site/courses/catalog.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from freecad.CADet import course_package


def build_site(source_dir: Path, out_dir: Path, package_base: str) -> int:
    if not source_dir.is_dir():
        print(f"course source directory does not exist: {source_dir}", file=sys.stderr)
        return 1
    packages_dir = out_dir / "packages"
    packages_dir.mkdir(parents=True, exist_ok=True)
    for old in packages_dir.glob(f"*{course_package.PACKAGE_SUFFIX}"):
        old.unlink()

    paths = []
    for folder in sorted(item for item in source_dir.iterdir() if item.is_dir()):
        if not (folder / course_package.MANIFEST_NAME).is_file():
            continue
        temporary = packages_dir / (folder.name + course_package.PACKAGE_SUFFIX)
        manifest = course_package.pack_directory(folder, temporary)
        final = packages_dir / (
            f"{manifest['id']}-{manifest['version']}{course_package.PACKAGE_SUFFIX}"
        )
        if final != temporary:
            os.replace(temporary, final)
        paths.append(final)
        print(f"packed {final}")

    if not paths:
        print(f"no course folders found in {source_dir}", file=sys.stderr)
        return 1
    catalog = course_package.build_catalog(paths, package_base=package_base)
    catalog_path = out_dir / "catalog.json"
    course_package.write_catalog(catalog_path, catalog)
    print(f"wrote {catalog_path} with {len(catalog['courses'])} courses")
    return 0


def validate_packages(paths: list[Path]) -> int:
    failed = False
    for path in paths:
        errors = course_package.validate_package(path)
        if errors:
            failed = True
            print(f"FAIL {path}")
            for error in errors:
                print(f"  - {error}")
        else:
            manifest = course_package.read_manifest(path)
            print(f"OK   {path}  {manifest['id']} {manifest['version']}")
    return 1 if failed else 0


def pack(source: Path, output: Path) -> int:
    manifest = course_package.pack_directory(source, output)
    print(f"packed {output}  {manifest['id']} {manifest['version']}")
    return 0


def build_catalog(packages_dir: Path, out: Path, package_base: str) -> int:
    packages = sorted(packages_dir.glob(f"*{course_package.PACKAGE_SUFFIX}"))
    if not packages:
        print(f"no packages found in {packages_dir}", file=sys.stderr)
        return 1
    catalog = course_package.build_catalog(packages, package_base=package_base)
    course_package.write_catalog(out, catalog)
    print(f"wrote {out} with {len(catalog['courses'])} courses")
    return 0


def check_catalog(catalog_path: Path, root: Path | None) -> int:
    try:
        data = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"FAIL {catalog_path}: {exc}", file=sys.stderr)
        return 1
    errors = course_package.validate_catalog(
        data,
        root=root if root is not None else catalog_path.parent,
    )
    if errors:
        print(f"FAIL {catalog_path}")
        for error in errors:
            print(f"  - {error}")
        return 1
    print(f"OK   {catalog_path}  ({len(data['courses'])} courses)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    build_parser = sub.add_parser("build", help="pack courses/ and rebuild the site catalog")
    build_parser.add_argument("--source", type=Path, default=ROOT / "courses")
    build_parser.add_argument("--out", type=Path, default=ROOT / "site" / "courses")
    build_parser.add_argument("--package-base", default="packages/")

    validate_parser = sub.add_parser("validate", help="validate one or more packages")
    validate_parser.add_argument("packages", nargs="+", type=Path)

    pack_parser = sub.add_parser("pack", help="pack a directory containing manifest.json")
    pack_parser.add_argument("source", type=Path)
    pack_parser.add_argument("output", type=Path)

    catalog_parser = sub.add_parser("catalog", help="build a catalog from a package directory")
    catalog_parser.add_argument("packages_dir", type=Path)
    catalog_parser.add_argument("--out", type=Path, required=True)
    catalog_parser.add_argument("--package-base", default="packages/")

    check_parser = sub.add_parser("check", help="validate a catalog and its packages")
    check_parser.add_argument("catalog", type=Path)
    check_parser.add_argument("--root", type=Path)

    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            return build_site(args.source, args.out, args.package_base)
        if args.command == "validate":
            return validate_packages(args.packages)
        if args.command == "pack":
            return pack(args.source, args.output)
        if args.command == "catalog":
            return build_catalog(args.packages_dir, args.out, args.package_base)
        if args.command == "check":
            return check_catalog(args.catalog, args.root)
    except course_package.CoursePackageError as exc:
        print("FAIL", file=sys.stderr)
        for error in exc.errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
