# Build once, infer per investigation

Create the exact seed-105 fold detector used by the application:

```sh
uv run --locked python -m ringsentinel.models.artifact --output work/models/network-hgb.joblib
```

The command writes a model and metadata JSON, refuses to replace the model, and
prints its SHA-256. Metadata records training seeds, validation seed, feature order,
threshold, Python/scikit-learn versions and synthetic-only scope. It does not claim
real-payment validation or regenerate historical benchmark reports.

Set both `RINGSENTINEL_MODEL_ARTIFACT_PATH` and
`RINGSENTINEL_MODEL_ARTIFACT_SHA256` to use the model. The API includes the configured
digest in run provenance and explicitly passes the path and digest to the child
worker. Loading checks the bytes before deserialization, then checks the feature
allowlist, threshold, schema and exact scikit-learn version. A mismatch fails the job.

Artifacts use joblib, which can execute code while loading. Only trusted operator-built
artifacts with a digest established through a trusted release process are acceptable.
An attacker-provided digest does not make a model safe. The upload contract does not
accept model files or model paths. Keep model files separate from writable dataset
storage and deploy them in the read-only application image.

The backend Docker build now trains the model once and copies its artifact and
manifest into root-owned `/app/models`. Container startup reads that trusted manifest
to configure the expected digest before loading application settings. API migrations
remain an explicit operation. Model loading adds no online training or paid API call.

Local startup without artifact settings retains the existing runtime-training fallback
for compatibility. Deployments should always use the image artifact. A future
real-data model needs its own training/evaluation/release process and model card;
replacing the synthetic artifact is not itself validation.
