import type { Page } from '@playwright/test';
import type {
  AnalysisResult,
  AnalysisRun,
  InvestigationRecord,
} from '../lib/platform-api';

// Transport fixtures exercise rare UI states only. They are not benchmark data/results.
export const investigationId = '00000000-0000-4000-8000-000000000010';
export const runId = '00000000-0000-4000-8000-000000000020';
export const artifactId = '00000000-0000-4000-8000-000000000030';
export const record: InvestigationRecord = {
  id: investigationId,
  name: 'State verification fixture',
  owner_id: 'local-analyst',
  status: 'completed',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-02T00:00:00Z',
};
export const run: AnalysisRun = {
  id: runId,
  investigation_id: investigationId,
  artifact_id: artifactId,
  status: 'completed',
  created_at: '2026-01-01T00:00:00Z',
  started_at: '2026-01-01T00:00:01Z',
  completed_at: '2026-01-01T00:00:02Z',
  error_code: null,
  error_message_safe: null,
  version_metadata: { application: 'fixture', detector: 'fixture' },
  configuration_snapshot: {},
  result_checksum: 'fixture-not-a-real-checksum',
};
export const result: AnalysisResult = {
  schema_version: '1',
  threshold: 0.71,
  event_count: 0,
  entity_count: 0,
  model_scope: 'UI state fixture only—not a benchmark',
  rings: [],
};
const candidate = {
  candidate_id: 'ui-fixture-candidate',
  risk_score: 0.8,
  first_suspicious_timestamp: '2026-01-01T00:00:00Z',
  estimated_exposure_minor: 10000,
  suspicious_relationships: [],
  evidence: {},
  member_entity_ids: ['ui-customer'],
  related_event_ids: ['ui-event'],
};
export const candidateResult: AnalysisResult = {
  ...result,
  event_count: 1,
  entity_count: 1,
  rings: [
    {
      candidate,
      queries: {
        get_candidate_ring: candidate,
        get_ring_members: [
          {
            entity_id: 'ui-customer',
            entity_type: 'CUSTOMER',
            created_at: '2025-01-01T00:00:00Z',
          },
        ],
        get_shared_devices: [],
        get_shared_ips: [],
        get_shared_cards: [],
        get_shared_addresses: [],
        get_shared_payout_accounts: [],
        get_merchant_relationships: [],
        get_transaction_timeline: [],
        get_temporal_activity: [],
        compare_member_behavior: [],
        get_refund_patterns: {
          refund_count: 0,
          refund_amount_minor: 0,
          refunds: [],
        },
        calculate_exposure: {
          candidate_id: candidate.candidate_id,
          estimated_exposure_minor: 10000,
          definition: 'UI fixture only.',
        },
      },
    },
  ],
};
export const artifact = {
  id: artifactId,
  investigation_id: investigationId,
  original_name: 'fixture.json',
  size_bytes: 100,
  checksum: 'fixture-not-a-real-checksum',
  content_type: 'application/json',
};
export const workspaceUrl = `/investigations/${investigationId}?run=${runId}`;
export async function installWorkspace(page: Page, currentRun = run) {
  await page.route('**/api/v1/**', (route) => {
    const path = new URL(route.request().url()).pathname;
    const data = path.endsWith('/session')
      ? {
          user_id: 'local-analyst',
          authentication_mode: 'development',
          production_authentication: false,
        }
      : path.endsWith('/artifacts')
        ? [artifact]
        : path.endsWith('/results')
          ? result
          : path.endsWith(`/runs/${runId}`)
            ? currentRun
            : path.endsWith('/runs')
              ? [currentRun]
              : path.endsWith('/investigations')
                ? [record]
                : record;
    return route.fulfill({ json: data });
  });
}
