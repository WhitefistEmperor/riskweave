# Investigator trust boundary

Analyst question → deterministic allowlisted query routing → RingEvidenceService
→ computed fact templates → provider selects/orders fact IDs → cited response.

The investigator never scores events, changes thresholds, classifies fraud, reads
ground-truth labels, or recommends automatic blocking. It receives the same
observed-prefix evidence as the Explorer. Unknown questions explicitly report
that no answer is inferred. Empty sharing queries report missing evidence.
Hourly counts are not presented as proof of synchronization; largest sharing count
is not described as causal model importance.

Default: `DeterministicProvider`, no credentials or external calls. For optional
LLM assistance, explicitly set `RINGSENTINEL_LLM_PROVIDER=openai`, `OPENAI_API_KEY`,
and optionally `RINGSENTINEL_OPENAI_MODEL` in the backend environment. See
`.env.example`; this application does not auto-load `.env` files. Never put keys
in frontend variables. Only the question and computed fact catalog go to OpenAI,
with `store=false`, a 20-second timeout, and a strict fact-ID JSON schema.

The provider design intentionally uses **extractive summarization**, not open-ended
generated prose. OpenAI selects and orders up to ten computed observations. The
server rejects unknown, duplicate, empty, malformed, or excessive fact selections.
Only server-rendered fact text can reach the UI. Failures fall back to deterministic
output with a visible warning; raw provider errors are never returned.

Each statement includes a stable per-response fact ID, evidence-query name, and
result path. The response includes the full source query outputs. This makes every
factual sentence traceable. The deterministic router is deliberately bounded and
not a general conversational reasoning agent. Cross-community intent cannot be
inferred from a candidate query: use the separate measured Hard negatives screen.

Implementation follows the official OpenAI [Structured Outputs guide](https://developers.openai.com/api/docs/guides/structured-outputs).
The optional HTTP contract is tested with a stub transport. No paid live-provider
verification is claimed when credentials are not configured; the no-key path is
tested through the real API and browser.
