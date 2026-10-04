# Vercel deployment

The selected hosting target is Vercel Hobby. Do not upgrade a plan or enable paid
resources as part of this deployment. Hobby is intended for personal,
non-commercial use; confirm a different plan before commercial operation.

The console now uses native Next.js rather than the previous Vinext beta build.
Local development and production-preview commands keep port 5173. The Docker
build sets `RINGSENTINEL_STANDALONE=true` and runs the generated standalone
server; Vercel uses its native Next.js build without that flag.

## Console configuration

Import `WhitefistEmperor/riskweave`, choose the tested
`codex/production-foundation` branch, and set the project root to `frontend`.
Use the Next.js framework preset, `npm ci`, and `npm run build`. Verify the
deployment's actual commit SHA against the passing CI run before release.

Set these environment variables for the intended deployment environment:

| Variable | Value |
| --- | --- |
| `RINGSENTINEL_ENVIRONMENT` | `production` |
| `RINGSENTINEL_API_PROXY_TARGET` | HTTPS origin of the deployed, authenticated API |
| `NEXT_PUBLIC_RISKWEAVE_OIDC_AUTHORITY` | HTTPS issuer configured for the API |
| `NEXT_PUBLIC_RISKWEAVE_OIDC_CLIENT_ID` | Public PKCE client registered at that issuer |
| `RINGSENTINEL_OIDC_CONNECT_ORIGINS` | Optional JSON array of exact HTTPS origins when provider endpoints use another origin; set at build and runtime |

Do not set `NEXT_PUBLIC_RINGSENTINEL_API_BASE_URL` or
`RINGSENTINEL_STANDALONE` in Vercel. Public OIDC variables are build-time values;
changing them requires a rebuild. Register the console's `/auth/callback` URL
and logout origin in the identity provider after obtaining its deployment URL.
Preview deployments need explicitly registered preview callbacks or must remain
unreleased. Never register wildcard production callbacks.

The rewrite preserves same-origin browser requests to `/api/*`. A localhost
proxy destination cannot serve a hosted console. Configure a real API origin
before deploying the analyst workflow.

Console documents render per request with fresh script CSP nonces and private,
no-store caching. The policy permits the app and configured identity connection
origins; inline styles remain allowed for component positioning. Keep the proxy's
CSP header through the hosted gateway, verify live PKCE endpoints against the
allowlist, and account for dynamic rendering in Hobby's request allowance.

## API release gates

The repository now supplies a dedicated `app.py` / `app:app` Vercel entry point,
Python 3.13 selection, FastAPI configuration and a build-time trusted model.
Create a separate backend project rooted at the repository root. Keep the
configured build command `python -m ringsentinel.platform.vercel_build`.
It trains the existing synthetic baseline only during build, validates the
artifact and preserves cached model bytes. Runtime admission rejects corrupt
artifacts, substituted model settings and development configuration. Generated
Workflow steps admit the same release artifact before inference.

Set `RINGSENTINEL_ENVIRONMENT=production`, execution mode `request`, storage
backend `database`, background dispatch `vercel_workflow`, and storage root
`/tmp/riskweave`, plus the explicit PostgreSQL, JWT, trusted hosts, frontend
origins and budget settings described below and in `.env.example`. Enable Vercel
system environment variables. Supply verification-only public JWKS through a
configured file or fixed HTTPS endpoint; see [key rotation](authentication-key-rotation.md).
Never place private signing keys in a release. The entry point
derives model path/checksum from its bundled manifest, so omit model overrides.

The root `vercel.json` sets a 300-second function ceiling and daily recovery
cron. Set Vercel's `CRON_SECRET` and `RINGSENTINEL_DISPATCH_CRON_SECRET` to the
same private random value (at least 32 characters). Neither secret belongs in
the frontend. Private development workspaces and frontend dependencies are
excluded. CI builds the model twice without replacing cached bytes and measures
a conservative production-dependency inventory against a 450 MB budget.
That inventory is not the actual provider-generated function size.

This packaging is implemented but **not verified in a hosted Vercel build**.
The general-purpose API defaults still use a long-lived scheduler and filesystem
objects; deploy only the explicit managed entry point. Optional
[database storage and request execution](request-execution.md) now provide atomic
durable bytes, distributed single-run claims, deadlines and late-worker fencing.
They preserve case data across instances without a lifespan scheduler. This is
a tested foundation; hosted transport capacity, generated function packaging,
managed dispatch and provider dependencies still need verification before release.

A complete Vercel deployment still needs:

1. A provisioned private PostgreSQL database with explicit migrations through
   revision `0007`, TLS, a verified free allowance and an explicit storage budget.
2. Enable database object storage and verify authenticated reads, checksum checks,
   atomic byte admission/deletion and backup/restore against that deployed database.
   Local `/tmp` is suitable only for disposable analysis scratch files.
3. Configure [managed background delivery](background-delivery.md), the SDK registry,
   authenticated generated queue routes and daily recovery cron. Local SDK inference
   and SQL delivery recovery are implemented; verify hosted interruption/recovery.
   Default request mode still relies on browser dispatch. No ASGI lifespan daemon
   is a durable worker.
4. Verify [bounded uploads and result fragments](bounded-transport.md) on the hosted
   gateway against Vercel's 4.5 MB function limit. These retain ownership, validation,
   retries and whole-object checksums; large legacy evidence and investigator replies
   still need capacity review. No large workload is released from local tests alone.
5. Analysis bounded below the Hobby function duration of 300 seconds, allowing
   time to persist results and report failures. Resource/capacity tests must
   also verify the 2 GB memory ceiling and bundle allowance.
6. Inspect the generated API and Workflow function bundles for the build-owned
   model, manifest and dependencies. Verify checksum/compatibility admission and
   cold starts on the actual platform. Never accept executable model artifacts
   from an analyst upload.
7. Real JWT issuer/audience/JWKS/scope configuration, sign-in and cross-owner
   isolation checks, external readiness monitoring and a verified restore path.

Hobby quotas can pause a project instead of providing unlimited capacity. A
free database or storage allowance must be verified in the owning account;
provider integrations are not automatically free just because the console is
on Hobby. No real payment data should be used to test an unverified release.

## Release verification

Run frontend lint, typecheck, production build and all browser workflows.
The Docker CI job separately verifies the standalone image against the real
PostgreSQL-backed API. Once hosted dependencies are available, verify HTTPS,
sign-in, upload, actual model analysis, evidence, analyst review, reload,
owner isolation, deletion and recovery against the deployed commit. A console
URL alone does not establish a working model deployment.

The model is still synthetic-trained and uncalibrated; real-data evaluation and
operating thresholds are separate release gates.

References: [Hobby limits](https://vercel.com/docs/plans/hobby),
[Function limits](https://vercel.com/docs/functions/limitations),
[Next.js standalone output](https://nextjs.org/docs/app/api-reference/config/next-config-js/output).
