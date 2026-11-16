"""Train the demo runtime once and save it: ``python -m ringsentinel.api.prebuild PATH``.

Used by the Docker build (see ``PREBUILD_RUNTIME`` in the Dockerfile) so a hosted
demo does not have to retrain its model every time it wakes from sleep.
"""

import sys
import time
from pathlib import Path

from ringsentinel.api.runtime import save_prebuilt_runtime


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m ringsentinel.api.prebuild OUTPUT_PATH")
    started = time.perf_counter()
    path = save_prebuilt_runtime(Path(sys.argv[1]))
    megabytes = path.stat().st_size / 1e6
    print(f"saved {path} ({megabytes:.1f} MB) in {time.perf_counter() - started:.0f}s")


if __name__ == "__main__":
    main()
