# Hosting on Vercel with Supabase

Vercel hosts the console and the API (see [Vercel deployment](vercel-deployment.md)).
Supabase supplies the two things Vercel does not: the PostgreSQL database and the
analyst identity provider (Supabase Auth's OAuth 2.1 / OpenID Connect server).
Both run on free plans. Nothing here is verified against a live project yet; the
checks at the end are the release gate.

Placeholders: `<ref>` is the Supabase project reference, `<region>` its pooler
region, `<console>` and `<api>` the two Vercel deployment hostnames.

## 1. Supabase project

1. Create a project (free plan; pick the region closest to your Vercel functions,
   e.g. `ap-south-1` for India). Save the database password in a password manager.
2. **Lock down the Data API** — RiskWeave tables must not be reachable with the
   public key. Project Settings → Data API → turn it off. Step 2 also runs
   [`deploy/supabase/riskweave_lockdown.sql`](../deploy/supabase/riskweave_lockdown.sql)
   as defence in depth.

## 2. Database

Supabase's direct host (`db.<ref>.supabase.co`) is IPv6-only and Vercel cannot
reach it, so use the pooler. RiskWeave detects `*.pooler.supabase.com` and adjusts:
no client-side pool, statement/lock timeouts applied per transaction, and (port
6543) no server-side prepared statements.

| Use | Connection string (Connect → ORMs / connection string) |
| --- | --- |
| API at runtime (transaction pooler) | `postgresql+psycopg://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres?sslmode=require` |
| Migrations, backup, maintenance (session pooler) | same host, port `5432` |

Run migrations from your machine with the **session** pooler, then lock down:

```sh
RINGSENTINEL_DATABASE_URL='<session pooler URL>' uv run --locked ringsentinel-migrate
```

Then paste `deploy/supabase/riskweave_lockdown.sql` into the SQL editor and run it;
its final query must return no rows. Repeat both after any future migration.

Local execution mode, backups and other commands that hold the single-executor
lock refuse the transaction pooler with a clear error; point them at port 5432.
The free database is 500 MB, so set `RINGSENTINEL_STORAGE_LIMIT_BYTES` below that
(e.g. `400000000`). Free projects pause after a week without activity.

## 3. Analyst sign-in (Supabase Auth)

1. **Signing key.** Authentication → JWT Keys (signing keys): create a new
   **RSA (RS256)** key and rotate to it. The API accepts only RS256.
2. **Token lifetime.** Authentication → Sessions/JWT expiry: `900` seconds,
   matching the API's default `RINGSENTINEL_AUTH_MAX_TOKEN_SECONDS`. (Or raise that
   API setting to at most `3600`.)
3. **No open sign-up.** Authentication → Providers → Email: keep email/password,
   turn off "Allow new users to sign up". Create analysts under Authentication →
   Users → Add user.
4. **OAuth server.** Authentication → OAuth Server: enable it and set the
   authorization path to `/oauth/consent`. Authentication → URL Configuration:
   Site URL `https://<console>`.
5. **Register the console** as an OAuth client: type **public** (PKCE, no secret),
   redirect URI exactly `https://<console>/auth/callback`. Copy the client ID.
6. **Token hook.** Edit [`deploy/supabase/riskweave_access_token_hook.sql`](../deploy/supabase/riskweave_access_token_hook.sql),
   replace `REPLACE_WITH_RISKWEAVE_CLIENT_ID`, run it in the SQL editor, then select
   it under Authentication → Hooks → Customize Access Token (JWT) Claims. It adds
   `aud=riskweave-api`, `scope=ringsentinel:analyst` and `nbf` only for that client
   and only for users marked as analysts:

   ```sql
   update auth.users
      set raw_app_meta_data = raw_app_meta_data || '{"riskweave_analyst": true}'
    where email = 'analyst@example.com';
   ```

Users without the flag can sign in to Supabase but the API rejects their tokens.

## 4. Vercel API project (repository root)

Configure as in [Vercel deployment](vercel-deployment.md), with:

| Variable | Value |
| --- | --- |
| `RINGSENTINEL_ENVIRONMENT` | `production` |
| `RINGSENTINEL_EXECUTION_MODE` | `request` |
| `RINGSENTINEL_STORAGE_BACKEND` | `database` |
| `RINGSENTINEL_BACKGROUND_DISPATCH` | `vercel_workflow` |
| `RINGSENTINEL_STORAGE_ROOT` | `/tmp/riskweave` |
| `RINGSENTINEL_DATABASE_URL` | transaction pooler URL (port 6543) |
| `RINGSENTINEL_STORAGE_LIMIT_BYTES` | `400000000` |
| `RINGSENTINEL_AUTH_MODE` | `jwt` |
| `RINGSENTINEL_AUTH_ISSUER` | `https://<ref>.supabase.co/auth/v1` |
| `RINGSENTINEL_AUTH_JWKS_URL` | `https://<ref>.supabase.co/auth/v1/.well-known/jwks.json` |
| `RINGSENTINEL_AUTH_AUDIENCE` | `riskweave-api` |
| `RINGSENTINEL_FRONTEND_ORIGINS` | `["https://<console>"]` |
| `RINGSENTINEL_TRUSTED_HOSTS` | `["<api>", "<console>"]` |
| `RINGSENTINEL_DEMO_ENABLED` | `false` |
| `RINGSENTINEL_DISPATCH_CRON_SECRET`, `CRON_SECRET` | the same random value, 32+ characters |

The evidence cache defaults to per-instance memory; no Redis is required.

## 5. Vercel console project (`frontend`)

| Variable | Value |
| --- | --- |
| `RINGSENTINEL_ENVIRONMENT` | `production` |
| `RINGSENTINEL_API_PROXY_TARGET` | `https://<api>` |
| `NEXT_PUBLIC_RISKWEAVE_OIDC_AUTHORITY` | `https://<ref>.supabase.co/auth/v1` |
| `NEXT_PUBLIC_RISKWEAVE_OIDC_CLIENT_ID` | the client ID from step 3.5 |
| `NEXT_PUBLIC_RISKWEAVE_OIDC_SCOPE` | `openid profile email` (Supabase has no custom scopes) |
| `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | the project's publishable key (public by design) |

The console's `/oauth/consent` page signs the analyst in with Supabase, shows the
consent prompt, and only ever returns an authorization code to this console's own
`/auth/callback`. Public variables are build-time: redeploy after changing them.

## 6. Release checks (not yet done)

On the deployed URLs: sign in as a flagged analyst; confirm an unflagged user is
rejected by the API; upload, analyse, open evidence and ask the investigator;
reload; confirm a second analyst cannot see the first analyst's case; delete a
case; confirm `https://<ref>.supabase.co/rest/v1/investigations` with the
publishable key returns no data. Record results in `docs/RELEASE_GATES.md`.
