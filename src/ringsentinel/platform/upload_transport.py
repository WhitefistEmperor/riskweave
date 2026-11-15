"""Resumable, owner-scoped uploads that commit one validated artifact atomically."""

import hashlib
from datetime import UTC, timedelta

from sqlalchemy import delete, func, select, update

from ringsentinel.data.ingestion import parse_input
from ringsentinel.platform.database_storage import DatabaseStorageBackend
from ringsentinel.platform.errors import ProductError
from ringsentinel.platform.models import (
    Artifact,
    Investigation,
    Status,
    StoredBlob,
    UploadPart,
    UploadSession,
    utcnow,
)

CHUNK_BYTES = 2_000_000


class UploadTransport:
    def __init__(self, service):
        self.service = service

    def _supported(self):
        if not isinstance(self.service.storage, DatabaseStorageBackend):
            raise ProductError("UPLOAD_TRANSPORT_UNAVAILABLE")

    @staticmethod
    def _view(session, upload):
        indexes = list(
            session.scalars(
                select(UploadPart.part_index)
                .where(UploadPart.upload_id == upload.id)
                .order_by(UploadPart.part_index)
            )
        )
        return {
            "id": upload.id,
            "investigation_id": upload.investigation_id,
            "name": upload.name,
            "status": upload.status,
            "size_bytes": upload.size_bytes,
            "checksum": upload.checksum,
            "chunk_bytes": CHUNK_BYTES,
            "chunk_count": upload.chunk_count,
            "received": indexes,
            "artifact_id": upload.artifact_id,
        }

    def _owned(self, session, principal, investigation_id, upload_id):
        self.service._owned(session, principal, investigation_id)
        upload = session.get(UploadSession, upload_id)
        if upload is None or upload.investigation_id != investigation_id:
            raise ProductError("NOT_FOUND")
        return upload

    @staticmethod
    def _release(session, upload, status):
        session.execute(delete(UploadPart).where(UploadPart.upload_id == upload.id))
        session.execute(
            update(Investigation)
            .where(
                Investigation.id == upload.investigation_id,
                Investigation.status == Status.UPLOADING,
            )
            .values(status=upload.previous_status, updated_at=utcnow())
        )
        upload.status, upload.active_slot = status, None

    def _expire_in(self, session, *, principal=None, investigation_id=None, limit=100):
        query = select(UploadSession).where(
            UploadSession.status == "pending", UploadSession.expires_at <= utcnow()
        )
        if principal is not None:
            query = query.join(Investigation).where(Investigation.owner_id == principal.user_id)
        if investigation_id is not None:
            query = query.where(UploadSession.investigation_id == investigation_id)
        expired = list(session.scalars(query.order_by(UploadSession.expires_at).limit(limit)))
        for upload in expired:
            self._release(session, upload, "expired")
        return len(expired)

    def expire(self, *, principal=None, investigation_id=None, limit=100):
        self._supported()
        with self.service._write() as session:
            return self._expire_in(
                session, principal=principal, investigation_id=investigation_id, limit=limit
            )

    def begin(self, principal, investigation_id, *, name, size_bytes, checksum, key):
        self._supported()
        if (
            any(not char.isprintable() for char in name)
            or any(char in name for char in ("/", "\\", ":"))
            or name in {".", ".."}
        ):
            raise ProductError("INVALID_DATASET")
        if size_bytes > self.service.settings.upload_limit_bytes:
            raise ProductError("UPLOAD_TOO_LARGE")
        count = (size_bytes + CHUNK_BYTES - 1) // CHUNK_BYTES
        with self.service._write() as session:
            item = self.service._owned(session, principal, investigation_id)
            self._expire_in(session, principal=principal, investigation_id=investigation_id)
            existing = session.scalar(
                select(UploadSession).where(
                    UploadSession.investigation_id == investigation_id,
                    UploadSession.idempotency_key == key,
                )
            )
            if existing:
                if (
                    existing.name != name
                    or existing.size_bytes != size_bytes
                    or existing.checksum != checksum
                ):
                    raise ProductError("CONFLICT")
                if existing.status == "expired" or existing.status == "aborted":
                    raise ProductError("CONFLICT")
                return self._view(session, existing)
            pending = session.scalar(
                select(UploadSession).where(
                    UploadSession.investigation_id == investigation_id,
                    UploadSession.status == "pending",
                )
            )
            if pending:
                if (
                    pending.name == name
                    and pending.size_bytes == size_bytes
                    and pending.checksum == checksum
                ):
                    return self._view(session, pending)
                raise ProductError("CONFLICT")
            previous = item.status
            self.service._quota(
                session, UploadSession, self.service.settings.max_upload_sessions_total
            )
            self.service._quota(
                session,
                UploadSession,
                self.service.settings.max_upload_sessions_per_investigation,
                UploadSession.investigation_id == investigation_id,
            )
            self.service._lock_idle(session, investigation_id, Status.UPLOADING)
            upload = UploadSession(
                investigation_id=investigation_id,
                idempotency_key=key,
                name=name,
                size_bytes=size_bytes,
                checksum=checksum,
                chunk_count=count,
                status="pending",
                active_slot=investigation_id,
                previous_status=previous,
                expires_at=utcnow() + timedelta(hours=24),
            )
            session.add(upload)
            session.flush()
            return self._view(session, upload)

    def pending(self, principal, investigation_id):
        # Reading pending uploads also recovers expired reservations. Local file
        # storage has no staging sessions, but still authorizes the case first.
        self.service.get(principal, investigation_id)
        if (
            isinstance(self.service.storage, DatabaseStorageBackend)
            and self.service.settings.execution_mode != "request"
        ):
            self.expire(principal=principal, investigation_id=investigation_id)
        with self.service.database.session() as session:
            self.service._owned(session, principal, investigation_id)
            return [
                self._view(session, upload)
                for upload in session.scalars(
                    select(UploadSession).where(
                        UploadSession.investigation_id == investigation_id,
                        UploadSession.status == "pending",
                    )
                )
            ]

    def receive(self, principal, investigation_id, upload_id, index, content, checksum):
        self._supported()
        with self.service._write() as session:
            upload = self._owned(session, principal, investigation_id, upload_id)
            if upload.status == "completed":
                return self._view(session, upload)
            if upload.status != "pending" or upload.expires_at.replace(tzinfo=UTC) <= utcnow():
                raise ProductError("CONFLICT")
            if type(index) is not int or not 0 <= index < upload.chunk_count:
                raise ProductError("NOT_FOUND")
            expected = min(CHUNK_BYTES, upload.size_bytes - index * CHUNK_BYTES)
            if len(content) != expected or hashlib.sha256(content).hexdigest() != checksum:
                raise ProductError("INVALID_DATASET")
            previous = session.get(UploadPart, (upload_id, index))
            if previous:
                if previous.checksum != checksum or previous.content != content:
                    raise ProductError("CONFLICT")
                return self._view(session, upload)
            used = session.scalar(select(func.coalesce(func.sum(StoredBlob.size_bytes), 0)))
            used += session.scalar(select(func.coalesce(func.sum(UploadPart.size_bytes), 0)))
            if used + len(content) > self.service.settings.storage_limit_bytes:
                raise ProductError("QUOTA_EXCEEDED")
            session.add(
                UploadPart(
                    upload_id=upload_id,
                    part_index=index,
                    content=content,
                    size_bytes=len(content),
                    checksum=checksum,
                )
            )
            session.flush()
            return self._view(session, upload)

    def complete(self, principal, investigation_id, upload_id):
        self._supported()
        invalid = False
        with self.service._write() as session:
            upload = self._owned(session, principal, investigation_id, upload_id)
            if upload.status == "completed":
                return session.get(Artifact, upload.artifact_id)
            if upload.status != "pending" or upload.expires_at.replace(tzinfo=UTC) <= utcnow():
                raise ProductError("CONFLICT")
            parts = list(
                session.scalars(
                    select(UploadPart)
                    .where(UploadPart.upload_id == upload_id)
                    .order_by(UploadPart.part_index)
                )
            )
            if len(parts) != upload.chunk_count or any(
                part.part_index != index for index, part in enumerate(parts)
            ):
                raise ProductError("CONFLICT")
            content = b"".join(part.content for part in parts)
            if (
                len(content) != upload.size_bytes
                or hashlib.sha256(content).hexdigest() != upload.checksum
            ):
                invalid = True
            else:
                try:
                    bundle = parse_input(content)
                    if not bundle.events:
                        invalid = True
                except (ValueError, KeyError, TypeError, IndexError):
                    invalid = True
            if invalid:
                self._release(session, upload, "aborted")
            else:
                # Release staged bytes before admission: this replaces, rather than doubles,
                # the storage budget inside the same database transaction.
                session.execute(delete(UploadPart).where(UploadPart.upload_id == upload_id))
                artifact, _ = self.service.attach_validated_in(
                    session,
                    principal,
                    investigation_id,
                    content,
                    upload.name,
                    bundle,
                    upload.checksum,
                    reserved_upload=upload,
                )
                session.flush()
                upload.artifact_id, upload.status, upload.active_slot = (
                    artifact.id,
                    "completed",
                    None,
                )
        if invalid:
            raise ProductError("INVALID_DATASET")
        return artifact

    def cancel(self, principal, investigation_id, upload_id):
        self._supported()
        with self.service._write() as session:
            upload = self._owned(session, principal, investigation_id, upload_id)
            if upload.status == "pending":
                self._release(session, upload, "aborted")
            elif upload.status == "completed":
                raise ProductError("CONFLICT")
            return {"id": upload.id, "status": upload.status}
