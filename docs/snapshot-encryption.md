# Offline encrypted snapshot envelopes

Use the existing stopped-writer backup command first. This separate operator tool
wraps a validated snapshot in standard native X25519 age encryption. It does not
change the live database, schedule copies, upload backups or manage keys.

Install trusted age and age-keygen executables from the
[official age release](https://github.com/FiloSottile/age/releases/tag/v1.3.2).
The Windows drill used age 1.3.2; Linux CI verifies the pinned release SHA-256
before installing only its two executables into ignored work/age-ci. Digest checks
are not signature or Sigsum verification. Neither keys nor binaries belong in Git.

Create an identity in a private directory with age-keygen. Store the private key
separately from backup copies and derive its public recipient with age-keygen -y.
The wrapper accepts 1–8 native identities, excluding plugins, SSH and passphrase
identities. Private key contents pass through stdin, never command arguments.
Set restrictive Windows ACLs or Unix permissions on key/output/temp directories;
Python directory modes alone do not enforce Windows ACLs. Use an encrypted local
volume for plaintext snapshots and temporary archives. Closing temporary files
is not guaranteed secure erasure.

```text
uv run --locked python -m ringsentinel.platform.snapshot_encryption seal --source work/backups/snapshot-001 --output work/backups/snapshot-001.age --recipient age1PUBLIC_RECIPIENT --age-binary /trusted/path/age
uv run --locked python -m ringsentinel.platform.snapshot_encryption unseal --source work/backups/snapshot-001.age --output work/backups/decoded-001 --identity /private/path/identity.txt --age-binary /trusted/path/age
```

Replace placeholders with trusted local paths and the actual public recipient.
Existing outputs are refused. Seal validates declared snapshot paths/checksums
and encrypts regular files only. Unseal authenticates the complete ciphertext
before extraction, rejects traversal, links, duplicates and undeclared entries,
and validates snapshot checksums before publishing manifest.json last. Failed
archive checks can leave private .unseal-staging data; a destination without its
root manifest is incomplete and must never be restored. Binary data uses direct
file handles, avoiding shell encoding. Successful output contains only status,
size/checksum or file count; failures return a fixed code.

Limits are 10 GB plaintext archive, one million entries, 64 MB manifest, 64 KB
identity text and a 600-second native process timeout. Ciphertext is capped at
101% of the plaintext archive ceiling. Decryption size is checked after the native
process finishes: provision private temporary disk space accordingly. These are
operator tooling limits, not measured deployment capacity or untrusted-upload
admission. Snapshot creation and extraction require a trusted private filesystem
without concurrent mutation.

Age authenticates encrypted payload integrity, not the sender: anyone knowing a
public recipient can encrypt an archive. Restore only trusted operator snapshots.
Unseal never performs a restore; separately follow [restore order](backup-restore.md)
with stopped writers and a new empty database/storage target. Tests cover actual
encryption, wrong keys, ciphertext corruption, unsafe archives, overwrite refusal
and SQLite restoration in both storage modes. CI additionally encrypts/decrypts
the existing PostgreSQL 17 restore drills, preserving bytes, owner isolation,
review history and multipart result checks.

Scheduled off-host copies, provider access, key custody/rotation, backup retention,
export erasure, alerts, RPO/RTO and hosted recovery remain release gates. Agree
those policies before configuring a real backup destination.
