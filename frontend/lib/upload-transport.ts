import { apiRequest, ApiError } from '@/lib/client';
import { object, validArtifact } from '@/lib/response-validation';
import type { ArtifactRecord } from '@/lib/platform-api';

const chunkBytes = 2_000_000;
const sha = (v: unknown): v is string =>
  typeof v === 'string' && /^[a-f0-9]{64}$/.test(v);
export type UploadProgress = {
  id: string;
  investigation_id: string;
  name: string;
  status: 'pending' | 'completed';
  size_bytes: number;
  checksum: string;
  chunk_bytes: number;
  chunk_count: number;
  received: number[];
  artifact_id: string | null;
};

async function checksum(bytes: ArrayBuffer): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', bytes);
  return Array.from(new Uint8Array(digest), (value) =>
    value.toString(16).padStart(2, '0'),
  ).join('');
}

export function validUploadProgress(v: unknown): v is UploadProgress {
  if (
    !object(v) ||
    !Number.isSafeInteger(v.size_bytes) ||
    Number(v.size_bytes) < 1 ||
    Number(v.size_bytes) > 100_000_000
  )
    return false;
  return (
    typeof v.investigation_id === 'string' &&
    typeof v.name === 'string' &&
    v.name.length > 0 &&
    v.name.length <= 200 &&
    sha(v.checksum) &&
    validProgress(v, v.investigation_id, Number(v.size_bytes), v.checksum)
  );
}

function validProgress(
  v: unknown,
  investigationId: string,
  size: number,
  hash: string,
): v is UploadProgress {
  return (
    object(v) &&
    typeof v.id === 'string' &&
    /^[a-f0-9-]{36}$/.test(v.id) &&
    v.investigation_id === investigationId &&
    typeof v.name === 'string' &&
    v.name.length > 0 &&
    v.name.length <= 200 &&
    (v.status === 'pending' || v.status === 'completed') &&
    v.size_bytes === size &&
    sha(v.checksum) &&
    v.checksum === hash &&
    v.chunk_bytes === chunkBytes &&
    v.chunk_count === Math.ceil(size / chunkBytes) &&
    Array.isArray(v.received) &&
    v.received.every(
      (index: unknown) =>
        Number.isSafeInteger(index) &&
        Number(index) >= 0 &&
        Number(index) < Number(v.chunk_count),
    ) &&
    new Set(v.received).size === v.received.length &&
    (v.status === 'pending'
      ? v.artifact_id === null
      : typeof v.artifact_id === 'string' &&
        /^[a-f0-9-]{36}$/.test(v.artifact_id))
  );
}

export async function uploadInChunks(
  investigationId: string,
  file: File,
  key: string,
  onProgress?: (progress: UploadProgress) => void,
): Promise<ArtifactRecord> {
  if (file.size > 100_000_000)
    throw new ApiError(
      'The dataset exceeds the configured upload limit.',
      413,
      'UPLOAD_TOO_LARGE',
      crypto.randomUUID(),
    );
  const path = `/v1/investigations/${encodeURIComponent(investigationId)}`;
  const hash = await checksum(await file.arrayBuffer());
  const progress = await apiRequest<UploadProgress>(
    `${path}/uploads`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Idempotency-Key': key },
      body: JSON.stringify({
        name: file.name,
        size_bytes: file.size,
        checksum: hash,
      }),
    },
    (v) => validProgress(v, investigationId, file.size, hash),
  );
  onProgress?.(progress);
  if (progress.status === 'completed') {
    const artifacts = await apiRequest<ArtifactRecord[]>(
      `${path}/artifacts`,
      {},
      (v) => Array.isArray(v) && v.every(validArtifact),
    );
    const existing = artifacts.find(
      (item) =>
        item.id === progress.artifact_id &&
        item.checksum === hash &&
        item.investigation_id === investigationId &&
        item.size_bytes === file.size,
    );
    if (!existing)
      throw new Error(
        'Completed upload artifact could not be verified. Reload this investigation.',
      );
    return existing;
  }
  const received = new Set(progress.received);
  for (let index = 0; index < progress.chunk_count; index++) {
    if (received.has(index)) continue;
    const part = file.slice(index * chunkBytes, (index + 1) * chunkBytes);
    const partHash = await checksum(await part.arrayBuffer());
    const updated = await apiRequest<UploadProgress>(
      `${path}/uploads/${encodeURIComponent(progress.id)}/parts/${index}`,
      {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/octet-stream',
          'X-Chunk-SHA256': partHash,
        },
        body: part,
      },
      (v) =>
        validProgress(v, investigationId, file.size, hash) &&
        (v as UploadProgress).id === progress.id &&
        ((v as UploadProgress).status === 'completed' ||
          (v as UploadProgress).received.includes(index)),
    );
    onProgress?.(updated);
    if (updated.status === 'completed') break;
  }
  return apiRequest<ArtifactRecord>(
    `${path}/uploads/${encodeURIComponent(progress.id)}/complete`,
    {
      method: 'POST',
    },
    (v) =>
      validArtifact(v) &&
      (v as ArtifactRecord).investigation_id === investigationId &&
      (v as ArtifactRecord).size_bytes === file.size &&
      (v as ArtifactRecord).checksum === hash,
  );
}
