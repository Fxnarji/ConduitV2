"""
Central definition of file patterns that Conduit ignores.

Add entries here to keep them out of both the UI file list and the
project's .gitignore. Suffix matching is case-insensitive.
"""

# File suffixes hidden in the UI and added to .gitignore
IGNORED_SUFFIXES: frozenset[str] = frozenset({
    # Blender backups
    ".blend1", ".blend2", ".blend3", ".blend4",
    # Substance Painter / Designer backups
    ".spp_backup",
    # Generic backups / temp files
    ".bak", ".tmp", ".temp",
    # OS artefacts
    ".ds_store",
})

# Exact filenames hidden in the UI and added to .gitignore
IGNORED_NAMES: frozenset[str] = frozenset({
    "Thumbs.db",
    ".DS_Store",
    "desktop.ini",
})

# Lines written verbatim into .gitignore on project creation
GITIGNORE_PATTERNS: list[str] = [
    "_cache/",
    "*.pyc",
    # Blender
    "*.blend1",
    "*.blend2",
    "*.blend3",
    "*.blend4",
    # Substance
    "*.spp_backup",
    # Generic
    "*.bak",
    "*.tmp",
    "*.temp",
    # OS
    "Thumbs.db",
    ".DS_Store",
    "desktop.ini",
]


def is_ignored(name: str) -> bool:
    """Return True if a filename should be hidden from the UI."""
    from pathlib import Path
    p = Path(name)
    return (
        p.suffix.lower() in IGNORED_SUFFIXES
        or p.name in IGNORED_NAMES
    )
