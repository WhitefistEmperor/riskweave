# Investigation worklist pagination

The console uses `GET /api/v1/investigations/page`, authenticated as the current
analyst. The database applies owner scope before every item and count query.
No client-supplied owner identifier is accepted.

Parameters: `offset` (0 through 100000, default 0), `limit` (1 through 100,
default 10), `search` (at most 120 characters), optional case `status` from the
existing status enum. The console requests ten items. Search trims whitespace,
lowercases the term and matches name or case ID. `%`, `_` and `!` are literal;
SQL binds parameters. SQLite registers a deterministic Unicode lowercase
function; PostgreSQL uses its native lowercase function. Language-specific
collation differences still depend on the production database locale.

The envelope contains `items`, owner `total`, filtered `matched`, `offset` and
`limit`. Ordering is most recent update first, then descending ID for ties.
A request past the end returns no items. Invalid parameters produce the existing
safe 422 contract. Counts and pages describe a changing worklist, not a frozen
snapshot: concurrent updates can move cases between offset pages. Reload to see
current state; exports must not use this API as a snapshot guarantee.

The console debounces reads by 150 ms, cancels superseded requests, hides prior
rows while a new request is pending and validates page metadata and item counts.
Changing filters resets to page one. A page invalidated by deletions moves back
to the last valid page. Successful history reads are cached within the mounted
worklist and invalidated when a refreshed case update timestamp changes; only
visible cases request history. No result/evidence body is loaded.
Navigation reloads the worklist and its cache.

The earlier array endpoint remains for existing API clients and is limited by
configured investigation admission quotas, not this page size. Large legacy
replies remain a capacity gate; new clients should use the paged endpoint.
Production latency, database locale and hosted request allowances must still
be measured. This change does not prove hosted deployment capacity.
