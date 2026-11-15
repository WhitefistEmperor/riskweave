"""Local SDK/ASGI test harness. Never use this embedded queue for a public deployment."""

import argparse
import asyncio
import os
from uuid import uuid4

import uvicorn
from vercel import workflow

from ringsentinel.platform.settings import Settings


async def serve(host, port):
    from ringsentinel.platform.serve import configure_model_manifest

    configure_model_manifest()
    settings = Settings()
    if (
        settings.environment not in {"development", "test"}
        or settings.background_dispatch != "vercel_workflow"
        or os.getenv("WORKFLOW_TARGET_WORLD") != "local"
        or os.getenv("VERCEL_DEPLOYMENT_ID")
    ):
        raise ValueError("This harness requires an explicitly selected local test workflow world")
    # Private cleanup is confined to this pinned-SDK test harness. Product code
    # uses public APIs and rejects the embedded world in production.
    from vercel.workflow._internal import world

    from ringsentinel.platform.workflows import analyze_saved_run

    try:
        # SDK 0.11's embedded queue must own an AnyIO scope in this root task,
        # not in a short-lived FastAPI request. An absent ID runs no inference.
        probe = await workflow.start(analyze_saved_run, run_id=str(uuid4()), ticket=str(uuid4()))
        async with asyncio.timeout(30):
            if await probe.return_value() != "deleted":
                raise RuntimeError("Local SDK initialization did not finish safely")
        from ringsentinel.api.app import create_app

        config = uvicorn.Config(
            create_app(settings=settings), host=host, port=port, access_log=False
        )
        await uvicorn.Server(config).serve()
    finally:
        await world.get_world().aclose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    asyncio.run(serve(args.host, args.port))


if __name__ == "__main__":
    main()
