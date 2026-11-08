"""Bounded fragment transport of a candidate summary or query evidence section."""

import base64
import hashlib
import re

from ringsentinel.platform import result_sections
from ringsentinel.platform.errors import ProductError
from ringsentinel.platform.result_fragments import CHUNK_BYTES, metadata, read_part


class SectionTransport:
    def __init__(self, service):
        self.service = service

    def _prepare(self, principal, run_id, candidate_id, kind):
        run = result_sections.authorized(self.service, principal, run_id)
        if kind not in ("candidate", "evidence"):
            raise ProductError("NOT_FOUND")
        if run.candidate_index is None:
            content = result_sections.encode(
                result_sections.value(self.service, principal, run_id, candidate_id, kind)
            )
            return run, None, content
        # Membership is checked against the atomically committed index, without
        # loading a potentially huge candidate merely to serve its fragments.
        if result_sections.row_for(self.service, run, "candidate", candidate_id) is None:
            raise ProductError("NOT_FOUND")
        row = result_sections.row_for(self.service, run, kind, candidate_id)
        if (
            row is None
            or type(row.byte_offset) is not int
            or row.byte_offset < 0
            or type(row.size_bytes) is not int
            or row.size_bytes <= 0
            or run.result_size_bytes is None
            or row.byte_offset + row.size_bytes > run.result_size_bytes
            or not re.fullmatch(r"[a-f0-9]{64}", row.checksum)
        ):
            raise ProductError("INTERNAL_ERROR")
        return run, row, None

    def _part(self, run, row, index):
        start = row.byte_offset + index * CHUNK_BYTES
        stop = min(row.byte_offset + row.size_bytes, start + CHUNK_BYTES)
        rows = metadata(self.service, run)
        pieces = []
        # Verify each containing source fragment before emitting a subsection.
        for part_index in range(start // CHUNK_BYTES, (stop - 1) // CHUNK_BYTES + 1):
            part = read_part(self.service, run, rows[part_index])
            origin = part_index * CHUNK_BYTES
            pieces.append(part[max(start - origin, 0) : min(stop - origin, len(part))])
        content = b"".join(pieces)
        if len(content) != stop - start:
            raise ProductError("INTERNAL_ERROR")
        return content

    def manifest(self, principal, run_id, candidate_id, kind):
        run, row, content = self._prepare(principal, run_id, candidate_id, kind)
        if row is None:
            size, digest = len(content), hashlib.sha256(content).hexdigest()
        else:
            self._part(run, row, 0)
            size, digest = row.size_bytes, row.checksum
        return {
            "schema_version": "1",
            "run_id": run.id,
            "candidate_id": candidate_id,
            "section": kind,
            "result_sha256": run.result_checksum,
            "sha256": digest,
            "encoding": "base64",
            "content_type": "application/json",
            "size_bytes": size,
            "chunk_bytes": CHUNK_BYTES,
            "chunk_count": (size + CHUNK_BYTES - 1) // CHUNK_BYTES,
        }

    def chunk(self, principal, run_id, candidate_id, kind, index):
        run, row, content = self._prepare(principal, run_id, candidate_id, kind)
        size = row.size_bytes if row is not None else len(content)
        if type(index) is not int or not 0 <= index < (size + CHUNK_BYTES - 1) // CHUNK_BYTES:
            raise ProductError("NOT_FOUND")
        if row is not None:
            part = self._part(run, row, index)
            digest = row.checksum
        else:
            part = content[index * CHUNK_BYTES : (index + 1) * CHUNK_BYTES]
            digest = hashlib.sha256(content).hexdigest()
        return {
            "schema_version": "1",
            "run_id": run.id,
            "candidate_id": candidate_id,
            "section": kind,
            "index": index,
            "size_bytes": len(part),
            "result_sha256": run.result_checksum,
            "section_sha256": digest,
            "sha256": hashlib.sha256(part).hexdigest(),
            "data": base64.b64encode(part).decode("ascii"),
        }
