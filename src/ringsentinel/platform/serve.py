"""Container startup with an immutable, build-generated model manifest."""

import json
import os
from pathlib import Path


def configure_model_manifest():
    manifest = os.environ.get("RINGSENTINEL_MODEL_ARTIFACT_MANIFEST")
    if manifest:
        metadata = json.loads(Path(manifest).read_text())
        os.environ.setdefault(
            "RINGSENTINEL_MODEL_ARTIFACT_PATH", str(Path(manifest).parent / "network-hgb.joblib")
        )
        os.environ.setdefault("RINGSENTINEL_MODEL_ARTIFACT_SHA256", metadata["sha256"])


def main():
    configure_model_manifest()

    import uvicorn

    from ringsentinel.platform.settings import Settings

    settings = Settings()
    uvicorn.run(
        "ringsentinel.api.app:app",
        host=settings.api_host,
        port=settings.api_port,
        workers=1,
        timeout_keep_alive=5,
        timeout_graceful_shutdown=20,
        access_log=False,
    )


if __name__ == "__main__":
    main()
