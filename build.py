#!/usr/bin/env python3

import os
import re
from pathlib import Path
import PyInstaller.__main__

# ------------------------------------------------------------------
# Config
# ------------------------------------------------------------------

base_path = Path(__file__).parent
main_file = base_path / "main.py"

ui_path = base_path / "UI"
lib_path = base_path / "lib"
msc_path = base_path / "msc"

# OS-specific separator for PyInstaller --add-data
SEP = ";" if os.name == "nt" else ":"

# ------------------------------------------------------------------
# Get version safely (without executing main.py)
# ------------------------------------------------------------------

with open(main_file, "r", encoding="utf-8") as f:
    content = f.read()

match = re.search(r'version\s*=\s*"([0-9.]+)"', content)
if not match:
    raise RuntimeError("Could not find version string in main.py")

version = match.group(1)

# ------------------------------------------------------------------
# Build
# ------------------------------------------------------------------

print("========================================")
print(f"  Conduit | PyInstaller Build ({version})")
print("========================================\n")

dist_path = base_path / "builddata" / "dist_folder"
build_path = base_path / "builddata" / "build_folder"
spec_path = base_path / "builddata" / "spec_folder"

args = [
    f"--name=Conduit_{version}",
    "--onefile",
    "--windowed",
    f"--distpath={dist_path}",
    f"--workpath={build_path}",
    f"--specpath={spec_path}",
    "--add-data",
    f"{ui_path}{SEP}UI",
    "--add-data",
    f"{lib_path}{SEP}lib",
    "--add-data",
    f"{msc_path}{SEP}msc",
    str(main_file),
]

PyInstaller.__main__.run(args)

# ------------------------------------------------------------------
# Result check
# ------------------------------------------------------------------

is_windows = os.name == "nt"
output_name = f"Conduit_{version}.exe" if is_windows else f"Conduit_{version}"
output_file = dist_path / output_name

print()

if output_file.exists():
    print("========================================")
    print("  Build successful!")
    print(f"  Output: {output_file}")
    print("========================================")
else:
    print("========================================")
    print("  Build may have failed (output not found)")
    print("========================================")

# ------------------------------------------------------------------
# Optional: bump version (DISABLED by default for CI sanity)
# ------------------------------------------------------------------

BUMP_VERSION = False  # <-- turn on only if you really want this

if BUMP_VERSION:
    major, minor, patch = map(int, version.split("."))
    new_version = f"{major}.{minor}.{patch + 1:03}"

    new_content = re.sub(
        r'version\s*=\s*"[0-9.]+"',
        f'version = "{new_version}"',
        content,
    )

    with open(main_file, "w", encoding="utf-8") as f:
        f.write(new_content)

    print(f"\nUpdated version: {version} → {new_version}")
