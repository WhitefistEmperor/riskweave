"""Bounded, authenticated transport of complete immutable evidence bytes."""

import base64
import hashlib

from ringsentinel.platform.errors import ProductError

CHUNK_BYTES = 2_000_000


class ResultTransport:
    def __init__(self, service):
        self.service = service

    def manifest(self, principal, run_id: str):
        content = self.service.result_content(principal, run_id)
        run = self.service.run(principal, run_id)
        return {
            "schema_version": "1",
            "run_id": run_id,
            "investigation_id": run.investigation_id,
            "encoding": "base64",
            "content_type": "application/json",
            "size_bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
            "chunk_bytes": CHUNK_BYTES,
            "chunk_count": (len(content) + CHUNK_BYTES - 1) // CHUNK_BYTES,
        }

    def chunk(self, principal, run_id: str, index: int):
        # Authorize on every read, including invalid/missing indices.
        content = self.service.result_content(principal, run_id)
        count = (len(content) + CHUNK_BYTES - 1) // CHUNK_BYTES
        if type(index) is not int or not 0 <= index < count:
            raise ProductError("NOT_FOUND")
        part = content[index * CHUNK_BYTES : (index + 1) * CHUNK_BYTES]
        return {
            "schema_version": "1",
            "run_id": run_id,
            "index": index,
            "size_bytes": len(part),
            "result_sha256": hashlib.sha256(content).hexdigest(),
            "sha256": hashlib.sha256(part).hexdigest(),
            "data": base64.b64encode(part).decode("ascii"),
        }
