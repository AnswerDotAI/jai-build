#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE_FILE = ROOT / "release.json"
CONFIGURE_RE = re.compile(r"^AC_INIT\(\[jai\], \[([^]]+)\]")
UPSTREAM_RE = re.compile(
    r"^(?P<release>\d+(?:\.\d+){0,2})(?:(?:[-._]?)(?P<label>a|alpha|b|beta|c|rc|pre|preview)(?P<number>\d*))?$",
    re.IGNORECASE,
)
PRE_LABELS = {
    "a": "a",
    "alpha": "a",
    "b": "b",
    "beta": "b",
    "c": "rc",
    "pre": "rc",
    "preview": "rc",
    "rc": "rc",
}


def read_release_metadata() -> dict[str, object]:
    try:
        data = json.loads(RELEASE_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"Missing release metadata file: {RELEASE_FILE}") from exc

    upstream_version = str(data.get("upstream_version", "")).strip()
    source_ref = str(data.get("source_ref", "")).strip()
    packaging_revision = data.get("packaging_revision")

    if not upstream_version:
        raise SystemExit(f"{RELEASE_FILE} is missing 'upstream_version'")
    if not source_ref:
        raise SystemExit(f"{RELEASE_FILE} is missing 'source_ref'")
    if not isinstance(packaging_revision, int) or packaging_revision < 0:
        raise SystemExit(f"{RELEASE_FILE} must define a non-negative integer 'packaging_revision'")

    return {
        "upstream_version": upstream_version,
        "source_ref": source_ref,
        "packaging_revision": packaging_revision,
    }


def write_release_metadata(metadata: dict[str, object]) -> None:
    RELEASE_FILE.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")


def upstream_version() -> str:
    return str(read_release_metadata()["upstream_version"])


def source_ref() -> str:
    return str(read_release_metadata()["source_ref"])


def packaging_revision() -> int:
    return int(read_release_metadata()["packaging_revision"])


def normalize_upstream_version(version: str) -> str:
    value = version.strip()
    match = UPSTREAM_RE.fullmatch(value)
    if not match:
        raise SystemExit(
            f"Unsupported upstream version format {value!r}. "
            "Update tools/version.py to teach it how to normalize this version."
        )

    normalized = match.group("release")
    label = match.group("label")
    if not label:
        return normalized

    serial = match.group("number") or "0"
    return f"{normalized}{PRE_LABELS[label.lower()]}{serial}"


def package_version() -> str:
    base = normalize_upstream_version(upstream_version())
    revision = packaging_revision()
    if revision == 0:
        return base
    return f"{base}.post{revision}"


def tag_name() -> str:
    return f"v{package_version()}"


def version_from_configure(source_dir: str | Path) -> str:
    configure_ac = Path(source_dir) / "configure.ac"
    try:
        lines = configure_ac.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError as exc:
        raise SystemExit(f"Missing upstream configure.ac: {configure_ac}") from exc

    for line in lines:
        match = CONFIGURE_RE.match(line)
        if match:
            return match.group(1)

    raise SystemExit(f"Unable to parse upstream version from {configure_ac}")


def check_source_version(source_dir: str | Path) -> str:
    actual = version_from_configure(source_dir)
    expected = upstream_version()
    if actual != expected:
        raise SystemExit(
            "Upstream version mismatch: "
            f"release.json expects {expected!r}, but {Path(source_dir) / 'configure.ac'} contains {actual!r}."
        )
    return actual


def update_release_metadata(
    *,
    new_upstream_version: str | None,
    new_source_ref: str | None,
    new_packaging_revision: int | None,
    increment_packaging_revision: bool,
) -> dict[str, object]:
    metadata = read_release_metadata()

    if new_upstream_version is not None:
        normalized = new_upstream_version.strip()
        if not normalized:
            raise SystemExit("Upstream version cannot be empty")
        normalize_upstream_version(normalized)
        metadata["upstream_version"] = normalized
        if new_packaging_revision is None and not increment_packaging_revision:
            metadata["packaging_revision"] = 0

    if new_source_ref is not None:
        normalized = new_source_ref.strip()
        if not normalized:
            raise SystemExit("Source ref cannot be empty")
        metadata["source_ref"] = normalized

    if increment_packaging_revision:
        metadata["packaging_revision"] = int(metadata["packaging_revision"]) + 1

    if new_packaging_revision is not None:
        if new_packaging_revision < 0:
            raise SystemExit("Packaging revision must be non-negative")
        metadata["packaging_revision"] = new_packaging_revision

    write_release_metadata(metadata)
    return metadata


def show_release_metadata() -> str:
    metadata = read_release_metadata()
    lines = [
        f"upstream_version={metadata['upstream_version']}",
        f"source_ref={metadata['source_ref']}",
        f"packaging_revision={metadata['packaging_revision']}",
        f"package_version={package_version()}",
        f"tag={tag_name()}",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Resolve jai-build release versions.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("show", help="Print the resolved release metadata.")
    subparsers.add_parser("package-version", help="Print the Python package version.")
    subparsers.add_parser("upstream-version", help="Print the expected upstream jai version.")
    subparsers.add_parser("source-ref", help="Print the configured upstream source ref.")
    subparsers.add_parser("tag", help="Print the release tag name.")

    check_parser = subparsers.add_parser("check-source", help="Verify the upstream source version.")
    check_parser.add_argument("--source-dir", required=True, help="Path to the jai source tree.")

    set_parser = subparsers.add_parser("set", help="Update release metadata.")
    set_parser.add_argument("--upstream-version", help="New upstream jai version.")
    set_parser.add_argument("--source-ref", help="New upstream git ref to build from.")
    set_parser.add_argument("--packaging-revision", type=int, help="Explicit packaging revision.")
    set_parser.add_argument(
        "--next-packaging-revision",
        action="store_true",
        help="Increment the packaging revision by one.",
    )

    args = parser.parse_args(argv)

    if args.command == "show":
        print(show_release_metadata())
        return 0

    if args.command == "package-version":
        print(package_version())
        return 0

    if args.command == "upstream-version":
        print(upstream_version())
        return 0

    if args.command == "source-ref":
        print(source_ref())
        return 0

    if args.command == "tag":
        print(tag_name())
        return 0

    if args.command == "check-source":
        print(check_source_version(args.source_dir))
        return 0

    if args.command == "set":
        metadata = update_release_metadata(
            new_upstream_version=args.upstream_version,
            new_source_ref=args.source_ref,
            new_packaging_revision=args.packaging_revision,
            increment_packaging_revision=args.next_packaging_revision,
        )
        print(json.dumps(metadata, indent=2))
        return 0

    parser.print_help(sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
