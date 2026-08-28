#!/usr/bin/env python3
"""Build script: compute content hashes for static assets and generate manifest.json."""

import hashlib
import json
import os
import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"
MANIFEST_PATH = STATIC_DIR / "manifest.json"

# Assets to hash (relative to static/)
ASSET_GLOBS = [
    "css/*.css",
    "css/pages/*.css",
    "js/*.js",
    "js/pages/*.js",
    "js/*.js",
]


def hash_file(path: Path) -> str:
    """Return first 8 chars of SHA256 hash of file content."""
    data = path.read_bytes()
    return hashlib.sha256(data).hexdigest()[:8]


def get_hashed_name(path: Path) -> str:
    """Return filename with hash inserted before extension: style.css -> style.a1b2c3d4.css"""
    h = hash_file(path)
    stem = path.stem
    suffix = path.suffix
    return f"{stem}.{h}{suffix}"


def main():
    manifest = {}
    errors = 0

    for glob_pattern in ASSET_GLOBS:
        for src_path in STATIC_DIR.glob(glob_pattern):
            if not src_path.is_file():
                continue
            # Skip already-hashed files (avoid double-hashing)
            if re.match(r".*\.[a-f0-9]{8}\.(css|js)$", src_path.name):
                continue

            rel = src_path.relative_to(STATIC_DIR)
            hashed_name = get_hashed_name(src_path)
            hashed_rel = src_path.with_name(hashed_name).relative_to(STATIC_DIR)

            # Copy to hashed name (preserve original for dev)
            dst_path = STATIC_DIR / hashed_rel
            try:
                dst_path.write_bytes(src_path.read_bytes())
            except Exception as e:
                print(f"ERROR copying {src_path}: {e}", file=sys.stderr)
                errors += 1
                continue

            manifest[str(rel)] = str(hashed_rel)
            print(f"  {rel} -> {hashed_rel}")

    # Write manifest
    try:
        MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, sort_keys=True))
        print(f"\nManifest written to {MANIFEST_PATH} ({len(manifest)} entries)")
    except Exception as e:
        print(f"ERROR writing manifest: {e}", file=sys.stderr)
        errors += 1

    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()