import { apiRequest, ApiError } from '@/lib/client';
import { object, validResult } from '@/lib/response-validation';
import type { AnalysisRun, AnalysisResult } from '@/lib/platform-api';

const chunkBytes = 2_000_000;
const maxBytes = 500_000_000;
const sha = (v: unknown): v is string =>
  typeof v === 'string' && /^[a-f0-9]{64}$/.test(v);
const integer = (v: unknown): v is number =>
  typeof v === 'number' && Number.isSafeInteger(v);
type Manifest = {
  schema_version: '1';
  run_id: string;
  investigation_id: string;
  encoding: 'base64';
  content_type: 'application/json';
  size_bytes: number;
  sha256: string;
  chunk_bytes: number;
  chunk_count: number;
};
type Chunk = {
  schema_version: '1';
  run_id: string;
  index: number;
  size_bytes: number;
  result_sha256: string;
  sha256: string;
  data: string;
};

export function validManifest(v: unknown, run: AnalysisRun): boolean {
  return (
    object(v) &&
    v.schema_version === '1' &&
    v.run_id === run.id &&
    v.investigation_id === run.investigation_id &&
    v.encoding === 'base64' &&
    v.content_type === 'application/json' &&
    integer(v.size_bytes) &&
    v.size_bytes > 0 &&
    v.size_bytes <= maxBytes &&
    sha(v.sha256) &&
    sha(run.result_checksum) &&
    v.sha256 === run.result_checksum &&
    v.chunk_bytes === chunkBytes &&
    integer(v.chunk_count) &&
    v.chunk_count === Math.ceil(v.size_bytes / chunkBytes)
  );
}

function validChunk(v: unknown, manifest: Manifest, index: number): boolean {
  const expectedBytes = Math.min(
    chunkBytes,
    manifest.size_bytes - index * chunkBytes,
  );
  return (
    object(v) &&
    v.schema_version === '1' &&
    v.run_id === manifest.run_id &&
    v.index === index &&
    v.size_bytes === expectedBytes &&
    v.result_sha256 === manifest.sha256 &&
    sha(v.sha256) &&
    typeof v.data === 'string' &&
    v.data.length === 4 * Math.ceil(expectedBytes / 3) &&
    /^[A-Za-z0-9+/]*={0,2}$/.test(v.data)
  );
}

async function checksum(bytes: Uint8Array<ArrayBuffer>): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', bytes);
  return Array.from(new Uint8Array(digest), (value) =>
    value.toString(16).padStart(2, '0'),
  ).join('');
}

function unreadable(): never {
  throw new ApiError(
    'The API returned an unreadable response. Reload or contact the operator with this request ID.',
    200,
    'MALFORMED_RESPONSE',
    crypto.randomUUID(),
  );
}

/** Verify every fragment and the saved whole-result digest before decoding evidence. */
export async function loadChunkedResult(
  run: AnalysisRun,
  signal?: AbortSignal,
): Promise<AnalysisResult> {
  const path = `/v1/runs/${encodeURIComponent(run.id)}/results`;
  const manifest = await apiRequest<Manifest>(
    `${path}/manifest`,
    { signal },
    (v) => validManifest(v, run),
  );
  const bytes = new Uint8Array(manifest.size_bytes);
  for (let index = 0; index < manifest.chunk_count; index++) {
    signal?.throwIfAborted();
    const chunk = await apiRequest<Chunk>(
      `${path}/chunks/${index}`,
      { signal },
      (v) => validChunk(v, manifest, index),
    );
    let part: Uint8Array<ArrayBuffer>;
    try {
      const decoded = atob(chunk.data);
      part = Uint8Array.from(decoded, (char) => char.charCodeAt(0));
    } catch {
      return unreadable();
    }
    if (
      part.byteLength !== chunk.size_bytes ||
      (await checksum(part)) !== chunk.sha256
    )
      return unreadable();
    signal?.throwIfAborted();
    bytes.set(part, index * chunkBytes);
  }
  if ((await checksum(bytes)) !== manifest.sha256) return unreadable();
  signal?.throwIfAborted();
  let value: unknown;
  try {
    value = JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(bytes));
  } catch {
    return unreadable();
  }
  if (!validResult(value)) return unreadable();
  return value as AnalysisResult;
}
