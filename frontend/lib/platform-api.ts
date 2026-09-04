import { apiRequest } from '@/lib/client';
import type { JsonValue } from '@/lib/api';

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
};
export type AnalysisResult = {
  schema_version: '1';
  threshold: number;
  event_count: number;
  entity_count: number;
  model_scope: string;
  rings: {
    candidate: PersistedCandidate;
    queries: Record<string, JsonValue>;
  }[];
};
const id = encodeURIComponent;
const json = (body: unknown) => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
});
export const platformApi = {
  session: () => apiRequest<Session>('/v1/session'),
  investigations: () => apiRequest<InvestigationRecord[]>('/v1/investigations'),
  create: (name: string) =>
    apiRequest<InvestigationRecord>('/v1/investigations', json({ name })),
  investigation: (value: string) =>
    apiRequest<InvestigationRecord>(`/v1/investigations/${id(value)}`),
  artifacts: (value: string) =>
    apiRequest<ArtifactRecord[]>(`/v1/investigations/${id(value)}/artifacts`),
  upload: (value: string, file: File) =>
    apiRequest<ArtifactRecord>(`/v1/investigations/${id(value)}/artifacts`, {
      method: 'POST',
      body: file,
      // HTTP header values cannot carry arbitrary Unicode. This is display metadata only.
      headers: {
        'Content-Type': 'application/json',
        'X-Filename': file.name.replace(/[^\x20-\x7e]/g, '_'),
      },
    }),
  runs: (value: string) =>
    apiRequest<AnalysisRun[]>(`/v1/investigations/${id(value)}/runs`),
  start: (value: string, artifactId: string, key: string) =>
    apiRequest<AnalysisRun>(`/v1/investigations/${id(value)}/runs`, {
      ...json({ artifact_id: artifactId }),
      headers: { 'Content-Type': 'application/json', 'Idempotency-Key': key },
    }),
  run: (value: string, signal?: AbortSignal) =>
    apiRequest<AnalysisRun>(`/v1/runs/${id(value)}`, { signal }),
  results: (value: string, signal?: AbortSignal) =>
    apiRequest<AnalysisResult>(`/v1/runs/${id(value)}/results`, { signal }),
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
    if (run.status === 'completed' || run.status === 'failed') return;
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
