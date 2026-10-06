import { parseExactJson, validMinorAmount } from '@/lib/exact-money';
import type { MinorAmount } from '@/lib/exact-money';
import { apiRequest, ApiError } from '@/lib/client';
import {
  object,
  validCandidate,
  validQueries,
  validResult,
} from '@/lib/response-validation';
import type {
  AnalysisRun,
  AnalysisResult,
  PersistedCandidate,
} from '@/lib/platform-api';
import type { EvidenceQueries } from '@/lib/evidence';

const candidateValid = (value: unknown) =>
  validCandidate(value) &&
  object(value) &&
  typeof value.first_suspicious_timestamp === 'string' &&
  Array.isArray(value.suspicious_relationships) &&
  value.suspicious_relationships.every((item) => typeof item === 'string');
const chunkBytes = 2_000_000;
const sha = (value: unknown): value is string =>
  typeof value === 'string' && /^[a-f0-9]{64}$/.test(value);
const integer = (value: unknown): value is number =>
  typeof value === 'number' && Number.isSafeInteger(value);
export const scopedRun = (run: AnalysisRun) => sha(run.result_checksum);
const failed = (): never => {
  throw new ApiError(
    'Evidence integrity could not be verified. Reload or contact the operator.',
    200,
    'MALFORMED_RESPONSE',
    crypto.randomUUID(),
  );
};
const checksum = async (bytes: Uint8Array<ArrayBuffer>) =>
  Array.from(
    new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)),
    (value) => value.toString(16).padStart(2, '0'),
  ).join('');

export type CandidatePage = {
  schema_version: '1';
  run_id: string;
  result_sha256: string;
  offset: number;
  limit: number;
  total: number;
  next_offset: number | null;
  items: PersistedCandidate[];
};
async function loadLegacyCandidatePage(
  run: AnalysisRun,
  offset: number,
  limit: number,
  signal: AbortSignal,
): Promise<CandidatePage> {
  return apiRequest<CandidatePage>(
    `/v1/runs/${encodeURIComponent(run.id)}/candidate-page?offset=${offset}&limit=${limit}`,
    { signal },
    (value) => {
      if (
        !object(value) ||
        value.schema_version !== '1' ||
        value.run_id !== run.id ||
        !sha(value.result_sha256) ||
        value.result_sha256 !== run.result_checksum ||
        value.offset !== offset ||
        value.limit !== limit ||
        !integer(value.total) ||
        value.total < 0 ||
        !Array.isArray(value.items) ||
        value.items.length !==
          Math.min(limit, Math.max(value.total - offset, 0)) ||
        !value.items.every(candidateValid)
      )
        return false;
      const ids = value.items.map(
        (candidate) => (candidate as PersistedCandidate).candidate_id,
      );
      return (
        new Set(ids).size === ids.length &&
        value.next_offset ===
          (offset + ids.length < value.total ? offset + ids.length : null)
      );
    },
  );
}

export type QueueSummary = {
  candidate_id: string;
  risk_score: number;
  estimated_exposure_minor: MinorAmount;
  member_count: number;
  event_count: number;
};
export type QueuePage = Omit<CandidatePage, 'items'> & {
  items: QueueSummary[];
};
export async function loadCandidatePage(
  run: AnalysisRun,
  offset: number,
  limit: number,
  signal: AbortSignal,
): Promise<QueuePage> {
  try {
    return await apiRequest<QueuePage>(
      `/v1/runs/${encodeURIComponent(run.id)}/queue-page?offset=${offset}&limit=${limit}`,
      { signal },
      (value) => {
        if (
          !object(value) ||
          value.schema_version !== '1' ||
          value.run_id !== run.id ||
          !sha(value.result_sha256) ||
          value.result_sha256 !== run.result_checksum ||
          value.offset !== offset ||
          value.limit !== limit ||
          !integer(value.total) ||
          value.total < 0 ||
          !Array.isArray(value.items) ||
          value.items.length !==
            Math.min(limit, Math.max(value.total - offset, 0))
        )
          return false;
        if (
          !value.items.every(
            (item) =>
              object(item) &&
              typeof item.candidate_id === 'string' &&
              item.candidate_id.length > 0 &&
              item.candidate_id.length <= 100 &&
              typeof item.risk_score === 'number' &&
              Number.isFinite(item.risk_score) &&
              item.risk_score >= 0 &&
              item.risk_score <= 1 &&
              validMinorAmount(item.estimated_exposure_minor) &&
              integer(item.member_count) &&
              item.member_count >= 0 &&
              item.member_count <= 500_000_000 &&
              integer(item.event_count) &&
              item.event_count >= 0 &&
              item.event_count <= 500_000_000,
          )
        )
          return false;
        const ids = value.items.map(
          (item) => (item as QueueSummary).candidate_id,
        );
        return (
          new Set(ids).size === ids.length &&
          value.next_offset ===
            (offset + ids.length < value.total ? offset + ids.length : null)
        );
      },
    );
  } catch (error) {
    if (!(error instanceof ApiError) || error.status !== 404) throw error;
    const page = await loadLegacyCandidatePage(run, offset, limit, signal);
    return {
      ...page,
      items: page.items.map((item) => ({
        candidate_id: item.candidate_id,
        risk_score: item.risk_score,
        estimated_exposure_minor: item.estimated_exposure_minor,
        member_count: item.member_entity_ids.length,
        event_count: item.related_event_ids.length,
      })),
    };
  }
}

export async function loadOverview(
  run: AnalysisRun,
  signal?: AbortSignal,
): Promise<AnalysisResult> {
  const overview = await apiRequest<
    AnalysisResult & { candidate_count: number }
  >(
    `/v1/runs/${encodeURIComponent(run.id)}/overview`,
    { signal },
    (value) =>
      object(value) &&
      value.run_id === run.id &&
      sha(value.result_sha256) &&
      value.result_sha256 === run.result_checksum &&
      integer(value.candidate_count) &&
      value.candidate_count >= 0 &&
      integer(value.event_count) &&
      value.event_count >= 0 &&
      integer(value.entity_count) &&
      value.entity_count >= 0 &&
      validResult({ ...value, rings: [] }),
  );
  return {
    ...overview,
    rings: [],
    remote_candidate_count: overview.candidate_count,
  } as AnalysisResult;
}

type Manifest = {
  schema_version: '1';
  run_id: string;
  candidate_id: string;
  section: string;
  result_sha256: string;
  sha256: string;
  size_bytes: number;
  chunk_count: number;
  chunk_bytes: number;
};
type Chunk = {
  schema_version: '1';
  run_id: string;
  candidate_id: string;
  section: string;
  result_sha256: string;
  section_sha256: string;
  index: number;
  size_bytes: number;
  sha256: string;
  data: string;
};
export async function loadSection(
  run: AnalysisRun,
  candidateId: string,
  section: 'candidate' | 'evidence',
  signal: AbortSignal,
  progress?: (received: number, total: number) => void,
): Promise<PersistedCandidate | EvidenceQueries> {
  const path = `/v1/runs/${encodeURIComponent(run.id)}/rings/${encodeURIComponent(candidateId)}/sections/${section}`;
  const manifest = await apiRequest<Manifest>(
    `${path}/manifest`,
    { signal },
    (value) =>
      object(value) &&
      value.schema_version === '1' &&
      value.run_id === run.id &&
      value.candidate_id === candidateId &&
      value.section === section &&
      value.result_sha256 === run.result_checksum &&
      sha(run.result_checksum) &&
      sha(value.sha256) &&
      value.encoding === 'base64' &&
      value.content_type === 'application/json' &&
      integer(value.size_bytes) &&
      value.size_bytes > 0 &&
      value.size_bytes <= 500_000_000 &&
      value.chunk_bytes === chunkBytes &&
      integer(value.chunk_count) &&
      value.chunk_count === Math.ceil(value.size_bytes / chunkBytes),
  );
  signal.throwIfAborted();
  const bytes = new Uint8Array(manifest.size_bytes);
  progress?.(0, manifest.size_bytes);
  for (let index = 0; index < manifest.chunk_count; index++) {
    signal.throwIfAborted();
    const expected = Math.min(
      chunkBytes,
      manifest.size_bytes - index * chunkBytes,
    );
    const chunk = await apiRequest<Chunk>(
      `${path}/chunks/${index}`,
      { signal },
      (value) =>
        object(value) &&
        value.schema_version === '1' &&
        value.run_id === run.id &&
        value.candidate_id === candidateId &&
        value.section === section &&
        value.result_sha256 === run.result_checksum &&
        value.section_sha256 === manifest.sha256 &&
        value.index === index &&
        value.size_bytes === expected &&
        sha(value.sha256) &&
        typeof value.data === 'string' &&
        value.data.length === 4 * Math.ceil(expected / 3) &&
        /^[A-Za-z0-9+/]*={0,2}$/.test(value.data),
    );
    let part: Uint8Array<ArrayBuffer>;
    try {
      const decoded = atob(chunk.data);
      if (btoa(decoded) !== chunk.data) return failed();
      part = Uint8Array.from(decoded, (char) => char.charCodeAt(0));
    } catch {
      return failed();
    }
    if (part.length !== expected || (await checksum(part)) !== chunk.sha256)
      return failed();
    signal.throwIfAborted();
    bytes.set(part, index * chunkBytes);
    progress?.(index * chunkBytes + expected, manifest.size_bytes);
  }
  if ((await checksum(bytes)) !== manifest.sha256) return failed();
  signal.throwIfAborted();
  let value: unknown;
  try {
    value = parseExactJson(
      new TextDecoder('utf-8', { fatal: true }).decode(bytes),
    );
  } catch {
    return failed();
  }
  if (section === 'candidate') {
    if (
      !candidateValid(value) ||
      !object(value) ||
      value.candidate_id !== candidateId
    )
      return failed();
    return value as PersistedCandidate;
  }
  if (
    !validQueries(value) ||
    !object(value) ||
    !object(value.get_candidate_ring) ||
    value.get_candidate_ring.candidate_id !== candidateId ||
    !object(value.calculate_exposure) ||
    value.calculate_exposure.candidate_id !== candidateId
  )
    return failed();
  return value as EvidenceQueries;
}
