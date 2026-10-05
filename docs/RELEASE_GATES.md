# RiskWeave release acceptance, 5 October 2026

The goal remains a complete deployed product with a validated model. Passing the
repository checks or the local controls does not satisfy that goal. This audit
uses source 799e75b (all six push/PR checks green after one push browser retry), the actual account-access response and
the measured local worker baseline; consult the handoff for newer exact commits.

| Requirement | Evidence now | What still proves completion |
|---|---|---|
| Private investigation workflow | 287 Python/69 browser checks, persisted reviews, two-owner isolation and erasure, actual PostgreSQL/container workflows | Repeat on exact hosted HTTPS source with real identity and browser-close/reload |
| Real-data ingestion | Strict unlabeled JSON, explicit CSV mappings, identity/refund/currency checks, source hashes and synthetic feature-preservation proof | Review actual authorized provider export semantics, missing features and identity/history completeness |
| Model validity | Frozen pinned synthetic-trained detector; temporal labels, validation-only thresholds, missing-label coverage and descriptive feature shift tooling | Authorized observed temporal holdouts, label maturation, calibration, subgroup/error analysis, shift/operating limits and independent approval |
| Free hosting | Vercel target selected; production entry/build/Workflow source and CI packaging checks | Re-authentication: target workspace still returns 403; verify free account allowances, actual projects/deployment, TLS/database/identity |
| Runtime capacity | One Windows worker sample at each of three generated sizes; largest 10,207 events/8.23 MB input, 277.7 MB peak working set | Deployed cold/warm runs, parent/DB/browser overhead, repetitions/percentiles, concurrent and dense cases, largest response paths, duration/memory/bundle/billing |
| Durable jobs | Actual SDK/PostgreSQL local delivery, leases, retry/deadline/model fencing, bounded reconciliation and erasure checks | Generated hosted queue authentication, cron, browser-independent delivery and interruption/recovery on real provider |
| Operations and recovery | Private aggregate operator CLI, explicit retention/erasure, manual snapshots, standard age envelopes with actual local encrypted restores, and PostgreSQL 17 restore in both storage modes | External uptime/queue/error monitoring, authorized alert destinations, scheduled encrypted backups, hosted restore/rollback and RPO/RTO ownership |
| Source requirements | Repository and user instructions inspected | Instinct source link remains unread: prior phone/auth/terms gate; current fetch inaccessible. Do not invent its contents |

## Next actions

1. Restore Vercel connector access to `sahilsinghkushwah10thb-9948s-projects`
   (`team_TB2LpxHcKF1dYrc4LdY7O9Fu`) and repository access through supported login.
   An instruction to deploy does not itself supply account credentials. Preserve
   unrelated projects; never bypass the rejected login popup or substitute old main.
2. Follow `vercel-deployment.md` using the tested branch, verified free allowances,
   private TLS PostgreSQL, explicit migration 0010, live OIDC and managed Workflow.
   Do not invent a deployed URL or claim provider durability from embedded tests.
3. Provide authorized private payment exports and independently resolved fraud labels,
   with actual meaning/resolution time and agreed error/review costs. Analyst
   dispositions are not confirmed-fraud labels. Run reviewed mappings and the frozen
   temporal workflow; never turn synthetic controls into observed accuracy claims.
4. Establish actual data policy: retention/holds, snapshot/export erasure, alert
   ownership and backup/recovery targets. Choose deployment bounds from measured
   workloads rather than byte budgets or this sparse local benchmark alone.
5. Verify every remaining gate and update this file/handoff with exact evidence.
   Keep useful code work moving while access/data are pending, without substituting
   more synthetic tests for the missing deployment and observed validation.

See `CLAUDE_HANDOFF.md` for state/continuation instructions and
`capacity-baseline.md` for method, hashes, reproducibility and measurement limits.

## Targeted-read gap and remaining contracts

Audit of source e2926f4 confirms that `src/ringsentinel/api/platform_api.py`
loads the entire immutable result for ring listing, individual candidates, evidence
and investigator questions. `ReviewService._candidate` in
`src/ringsentinel/platform/reviews.py` does the same for review reads and writes.
The 2 MB whole-results response guard and indexed fragment delivery do not cover
these paths. This is an application implementation gap, independent of account access.

Next implementation must preserve the full analyst workflow for large results:
add an owner-authorized immutable candidate/evidence index built atomically with
successful result persistence, use targeted verified reads for candidate evidence
and investigator queries, and check candidate membership for reviews without
loading the entire result. Preserve the original result bytes/checksum and legacy
runs through explicit verified maintenance or compatible fallback. Candidate
pagination and individual evidence response sizes still require explicit contracts.
Do not replace these workflows with a blanket result-size rejection.

Proof must include both storage modes, large generated results with full-object
reads disabled, another owner's denial, missing/corrupt index rejection, failed
persistence rollback, legacy maintenance, deletion and actual PostgreSQL restore.
Retain the limitation until these paths are implemented and verified; a passing
small-case suite alone does not close it.

Source 6f8c578 implements atomic section indexing, verified owner-scoped targeted
candidate/query/currency reads, review membership, compatible legacy fallback and
explicit legacy maintenance. All six corrected-source CI checks passed: 279 Python and 69 browser
tests, containers and encrypted PostgreSQL restores in both storage modes. See targeted-result-sections.md. Original bytes/hashes stay unchanged.
The remaining gap is candidate pagination, evidence fragment responses, selected
section/browser memory and actual hosted capacity. Retain the historical audit
above as its trigger; it describes e2926f4, not the new targeted implementation.

Source 799e75b adds candidate pages and individual candidate/evidence fragments,
with source-fragment verification and an ordinal range index (migration 0010).
All six checks passed: 287 Python/69 browser tests and actual PostgreSQL restore.
One push browser keyboard test needed a retry; preserve its timing signal. Browser adoption, cancellation/final
integrity handling and real provider measurements remain required; existing direct
selected-section paths and large individual summaries still need capacity review.
