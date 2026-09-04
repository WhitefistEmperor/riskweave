# Phase 5A verification log

Baseline: main, clean, HEAD 722ef7abef6937f3fdf9b34bb13dfa1d0c30709d.
Before source edits: 41 Python tests passed (2 upstream deprecation warnings),
Ruff passed, frontend lint/TypeScript/build passed, wheel and sdist built.
All 5 production-browser tests passed in 1.3 minutes after restarting the old
frontend process to load the newly built chunks. Initial browser attempt failed
on missing stale chunks; no test assertions or product sources were changed.

Frozen Phase 3 JSON SHA256:
42c0234331f2b467ccc296f6579478d2feaf7c71e9c159387b6674a09b27e976.

Docker was not found on PATH during baseline inspection; no container validation
is claimed by this record.

## Resumed milestone 2: storage and analysis lifecycle

Resumed from 40f269f without resets or discarding the seven untracked implementation
files. The original resumed suite passed: 47 Python tests, Ruff clean. Added
regressions for exclusive-write UUID collisions and empty attack-progressions at
the upload boundary (the detector/generator were not modified).

After those fixes, all 10 persistence/lifecycle tests passed in 23.62 seconds and
their Ruff check passed. These include a real detector subprocess completing,
an actual timed-out child observed to exit, real worker failure and interruption,
concurrent-start exclusion, owner isolation, idempotency, checksums, upload limits,
and reopening results through a new database engine. No model outputs were mocked
in the subprocess tests. The scheduler remains deliberately single-process.
