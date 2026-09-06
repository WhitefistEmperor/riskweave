# RiskWeave documentation

RiskWeave is the current public product name. Historical phase reports, audit records,
license attribution, and benchmark artifacts retain RingSentinel where appropriate.
The internal `ringsentinel` package, commands, environment variables, and API paths are unchanged.

## Start here

- [Local setup and troubleshooting](quick-start.md)
- [Submission screenshots](assets/screenshots/README.md)
- [Published demo video](https://youtu.be/CaeExe9ePls)
- [Three-minute demo script](demo-script.md)
- [Submission verification](submission-validation.md)
- [GitHub description, topics, and remaining manual steps](submission-metadata.md)

## Understand the system

- [Architecture overview](architecture.md) and [persisted production foundation](PRODUCTION_ARCHITECTURE.md)
- [Data model and DatasetBundle](data-model.md)
- [Evidence UI semantics](evidence-ui.md) and [investigator design](investigator-design.md)
- [Benchmark methodology](benchmark-methodology.md) and [measured Phase 3 results](../results/phase3/phase3_summary.md)
- [Offline backup/restore](backup-restore.md)

## Verification and development history

The phase reports are dated historical records, not current deployment approval.
Start with [Phase 5C final verification and remaining gates](phase5c-final.md).

- [Phase 1](phase-1-report.md), [Phase 4](phase4-report.md), [Phase 5A](phase5a-verification.md)
- [Phase 5B frontend](phase5b-frontend.md) and [audit](phase5b-audit.md)
- [Phase 5C hardening](phase5c-hardening.md) and [dependency audits](dependency-audit.md)
- [Container verification plan](phase5c-container-verification.md): outstanding, not deployed
- [Original replay demo](demo-flow.md) and [original Phase 4 gallery](screenshots/)
- [Persistence architecture decision](adr/0001-persisted-analysis-foundation.md)
