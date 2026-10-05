"""Measure one claimed generated worker on an isolated loopback CI database only."""

import argparse
import json
import re
import sys
import time

from sqlalchemy.engine import make_url

from ringsentinel.platform.settings import Settings


def measure(run_id):
    if sys.platform != "linux":
        raise ValueError("Linux resource counters required")
    url = make_url(Settings().database_url.get_secret_value())
    if (
        url.host != "127.0.0.1"
        or url.username != "riskweave_backup_ci"
        or not re.fullmatch(r"riskweave_drill_[a-f0-9]{32}", url.database or "")
    ):
        raise ValueError("Isolated CI database required")
    import resource

    from ringsentinel.platform.worker import main as worker

    sys.argv = ["worker", run_id]
    start = time.perf_counter()
    worker()
    elapsed = time.perf_counter() - start
    usage = resource.getrusage(resource.RUSAGE_SELF)
    return {
        "worker_main_seconds": elapsed,
        "peak_worker_rss_bytes": usage.ru_maxrss * 1024,
        "worker_user_cpu_seconds": usage.ru_utime,
        "worker_system_cpu_seconds": usage.ru_stime,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(measure(args.run_id)))
    except Exception:
        print(json.dumps({"status": "unavailable", "code": "WORKER_CAPACITY_CONTROL_FAILED"}))
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
