# Analyst review and decision history

Completed findings now include an analyst review panel. An analyst can mark a candidate
Unreviewed, Investigating, Escalated or Dismissed, and add a required review note.
These assessments do not edit model evidence, risk scores or detection results and
are not confirmed fraud labels. They are not used to retrain the model.

Each review is scoped to `(run_id, candidate_id)`. Reusing a candidate ID in a later
analysis starts a new review. All access follows the existing investigation ownership
boundary. Another owner sees 404; the API does not reveal whether the finding exists.

## API and persistence

`GET /api/v1/runs/{run_id}/rings/{candidate_id}/review` returns the current disposition,
revision and ordered history. An untouched candidate has revision 0 and empty history.
Reading it creates no record.

`POST` to the same endpoint requires `Idempotency-Key` and this JSON:

```json
{"disposition":"investigating","note":"Review the observed shared devices.","expected_version":0}
```

The expected revision is checked under the database write lock. A stale revision
returns 409. Repeating the same submission key and content returns the saved review
without appending another history entry; reusing a key with different content returns
409. Version update and audit append commit in one transaction. Notes contain up to
2,000 characters; blank notes and unsupported control characters are rejected.
The default per-candidate limit is 200 audit entries, configurable using
`RINGSENTINEL_MAX_REVIEW_EVENTS_PER_CANDIDATE`. A retry of an already saved submission
does not consume this quota.

History records the analyst's authenticated opaque ID, previous and new status,
revision, note and UTC timestamp. The application exposes no editing or deletion
endpoint for audit entries. This is an append-only application history, not a
cryptographically tamper-proof ledger: database administrators still control the
underlying data. Retention/deletion policy remains deployment work. Avoid unnecessary
personal information in notes.

## Existing databases

Migration `0002` adds `candidate_reviews` and `review_audit`; migration `0001` remains
unchanged. Stop the application, run `uv run --locked ringsentinel-migrate`, and
restart. Readiness rejects the old revision or missing review tables. The migration
preserves existing investigations and run artifacts. Normal offline database backups
include review and audit rows; restore tests verify history and ownership survive.

## Browser recovery

A lost connection preserves the note and retries the original submission key.
A 409 preserves the draft and disables saving until the analyst reloads current
history. Reloading retains the draft, so the analyst can compare the latest decision
before explicitly resubmitting. The browser validates that a review response belongs
to the requested run and candidate before showing history. Notes render as text.

The real browser workflow verifies save, reload and history persistence. Transport
fixtures separately exercise connection loss, stale revisions and mismatched scopes.
