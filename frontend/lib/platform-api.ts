import { apiRequest } from '@/lib/client';
import type { JsonValue } from '@/lib/api';
import type { EvidenceQueries } from '@/lib/evidence';
import {
  list,
  validSession,
  validInvestigation,
  validArtifact,
  validRun,
  validResult,
} from '@/lib/response-validation';

export type RunStatus =
  | 'created'
  | 'uploading'
  | 'queued'
  | 'running'
  | 'completed'
  | 'failed';
export type Session = {
  user_id: string;
  authentication_mode: 'development';
  production_authentication: false;
};
export type InvestigationRecord = {
  id: string;
  name: string;
  owner_id: string;
  status: RunStatus;
  created_at: string;
  updated_at: string;
};
export type ArtifactRecord = {
  id: string;
  investigation_id: string;
  original_name: string;
  size_bytes: number;
  checksum: string;
  content_type: string;
};
export type AnalysisRun = {
  id: string;
  investigation_id: string;
  artifact_id: string;
  status: RunStatus;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  error_code: string | null;
  error_message_safe: string | null;
  version_metadata: Record<string, string>;
  configuration_snapshot: Record<string, JsonValue>;
  result_checksum: string | null;
};
export type PersistedCandidate = {
  candidate_id: string;
  risk_score: number;
  estimated_exposure_minor: number;
  member_entity_ids: string[];
  related_event_ids: string[];
  evidence: Record<string, number>;
  first_suspicious_timestamp: string;
  suspicious_relationships: string[];
};
export type AnalysisResult = {
  schema_version: '1';
  threshold: number;
  event_count: number;
  entity_count: number;
  model_scope: string;
  rings: {
    candidate: PersistedCandidate;
    queries: EvidenceQueries;
  }[];
};
const id = encodeURIComponent;
const json = (body: unknown) => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
});
export const platformApi = {
  session: () => apiRequest<Session>('/v1/session', {}, validSession),
  investigations: (signal?: AbortSignal) =>
    apiRequest<InvestigationRecord[]>(
      '/v1/investigations',
      { signal },
      list(validInvestigation),
    ),
  create: (name: string) =>
    apiRequest<InvestigationRecord>(
      '/v1/investigations',
      json({ name }),
      validInvestigation,
    ),
  investigation: (value: string, signal?: AbortSignal) =>
    apiRequest<InvestigationRecord>(
      `/v1/investigations/${id(value)}`,
      { signal },
      validInvestigation,
    ),
  artifacts: (value: string, signal?: AbortSignal) =>
    apiRequest<ArtifactRecord[]>(
      `/v1/investigations/${id(value)}/artifacts`,
      { signal },
      list(validArtifact),
    ),
  upload: (value: string, file: File) =>
    apiRequest<ArtifactRecord>(
      `/v1/investigations/${id(value)}/artifacts`,
      {
        method: 'POST',
        body: file,
        // HTTP header values cannot carry arbitrary Unicode. This is display metadata only.
        headers: {
          'Content-Type': 'application/json',
          'X-Filename': file.name.replace(/[^\x20-\x7e]/g, '_'),
        },
      },
      validArtifact,
    ),
  runs: (value: string, signal?: AbortSignal) =>
    apiRequest<AnalysisRun[]>(
      `/v1/investigations/${id(value)}/runs`,
      { signal },
      list(validRun),
    ),
  start: (value: string, artifactId: string, key: string) =>
    apiRequest<AnalysisRun>(
      `/v1/investigations/${id(value)}/runs`,
      {
        ...json({ artifact_id: artifactId }),
        headers: { 'Content-Type': 'application/json', 'Idempotency-Key': key },
      },
      validRun,
    ),
  run: (value: string, signal?: AbortSignal) =>
    apiRequest<AnalysisRun>(`/v1/runs/${id(value)}`, { signal }, validRun),
  results: (value: string, signal?: AbortSignal) =>
    apiRequest<AnalysisResult>(
      `/v1/runs/${id(value)}/results`,
      { signal },
      validResult,
    ),
};

/** Poll persisted state only. Never retry a POST or start a second analysis implicitly. */
export async function pollRun(
  value: string,
  onUpdate: (run: AnalysisRun) => void,
  signal: AbortSignal,
) {
  while (!signal.aborted) {
    const run = await platformApi.run(value, signal);
    if (signal.aborted) return;
    onUpdate(run);
    if (run.status === 'completed' || run.status === 'failed') return run;
    await new Promise<void>((resolve) => {
      const done = () => {
        clearTimeout(timer);
        signal.removeEventListener('abort', done);
        resolve();
      };
      const timer = setTimeout(done, 1000);
      signal.addEventListener('abort', done, { once: true });
      if (signal.aborted) done();
    });
  }
}
