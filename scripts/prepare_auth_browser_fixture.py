"""Create a new isolated frontend copy for OIDC session browser controls only."""

import os
import shutil
import sys
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    if len(sys.argv) != 2:
        raise ValueError("A new workspace fixture path is required")
    destination = Path(sys.argv[1]).resolve()
    if not destination.is_relative_to(root / "work") or destination.exists():
        raise ValueError("Fixture must be a new directory under ignored work/")
    source = root / "frontend"
    shutil.copytree(
        source,
        destination,
        ignore=shutil.ignore_patterns(
            "node_modules", ".next", ".env*", "test-results", "playwright-report", "*.tsbuildinfo"
        ),
    )
    # Internal dependency paths also work with Turbopack's filesystem root.
    # Reuse immutable installed package bytes; caches and project outputs are separate.
    shutil.copytree(
        source / "node_modules",
        destination / "node_modules",
        copy_function=os.link,
        symlinks=True,
        ignore=shutil.ignore_patterns(".cache"),
    )


if __name__ == "__main__":
    main()
