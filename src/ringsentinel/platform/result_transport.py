"""Bounded, authenticated transport of complete immutable evidence bytes."""

import base64
import hashlib

from ringsentinel.platform.errors import ProductError
from ringsentinel.platform.models import Status
from ringsentinel.platform.result_fragments import CHUNK_BYTES, metadata, read_part


class ResultTransport:
    def __init__(self, service):
        self.service = service

    def manifest(self, principal, run_id: str):
        run = self.service.run(principal, run_id)
        if run.status != Status.COMPLETED or not run.result_reference:
            raise ProductError("CONFLICT")
        if run.result_size_bytes is None:
            content = self.service.result_content(principal, run_id)
            size, digest = len(content), hashlib.sha256(content).hexdigest()
        else:
            rows = metadata(self.service, run)
            # Probe the first part; every requested part and the browser's full
            # reconstruction still need independent checksum verification.
            read_part(self.service, run, rows[0])
            size, digest = run.result_size_bytes, run.result_checksum
        return {
            "schema_version": "1",
            "run_id": run_id,
            "investigation_id": run.investigation_id,
            "encoding": "base64",
            "content_type": "application/json",
            "size_bytes": size,
            "sha256": digest,
            "chunk_bytes": CHUNK_BYTES,
            "chunk_count": (size + CHUNK_BYTES - 1) // CHUNK_BYTES,
        }

    def chunk(self, principal, run_id: str, index: int):
        # Authorize on every read, including invalid/missing indices.
        run = self.service.run(principal, run_id)
        if run.status != Status.COMPLETED or not run.result_reference:
            raise ProductError("CONFLICT")
        if run.result_size_bytes is None:
            content = self.service.result_content(principal, run_id)
            count = (len(content) + CHUNK_BYTES - 1) // CHUNK_BYTES
            if type(index) is not int or not 0 <= index < count:
                raise ProductError("NOT_FOUND")
            part = content[index * CHUNK_BYTES : (index + 1) * CHUNK_BYTES]
            digest = hashlib.sha256(content).hexdigest()
        else:
            rows = metadata(self.service, run)
            if type(index) is not int or not 0 <= index < len(rows):
                raise ProductError("NOT_FOUND")
            part = read_part(self.service, run, rows[index])
            digest = run.result_checksum
        return {
            "schema_version": "1",
            "run_id": run_id,
            "index": index,
            "size_bytes": len(part),
            "result_sha256": digest,
            "sha256": hashlib.sha256(part).hexdigest(),
            "data": base64.b64encode(part).decode("ascii"),
        }
