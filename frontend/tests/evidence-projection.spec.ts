import { test, expect } from '@playwright/test';
import {
  projectEvidenceGraph,
  orderedEvents,
  type EvidenceQueries,
} from '../lib/evidence';
import { validQueries, validResult } from '../lib/response-validation';

test('evidence projection adds only explicit pairs, retains unlinked members, and never invents edge counts', () => {
  const queries = {
    get_ring_members: [
      {
        entity_id: 'isolated',
        entity_type: 'CARD',
        created_at: '2026-01-01T00:00:00Z',
      },
    ],
    get_shared_devices: [
      {
        entity_id: 'device',
        customer_ids: ['b', 'a'],
        customer_count: 2,
        event_count: 100,
      },
    ],
    get_shared_ips: [],
    get_shared_cards: [],
    get_shared_addresses: [],
    get_shared_payout_accounts: [
      {
        bank_account_id: 'bank',
        merchant_ids: ['merchant', 'merchant2'],
        merchant_count: 2,
        event_count: 9,
      },
    ],
    get_merchant_relationships: [
      {
        merchant_id: 'merchant',
        payout_account_id: 'bank',
        customer_ids: ['a'],
        customer_count: 1,
        event_count: 3,
      },
    ],
  } as unknown as EvidenceQueries;
  const graph = projectEvidenceGraph(queries);
  expect(
    graph.edges.map((edge) => [edge.source, edge.target, edge.relationship]),
  ).toEqual([
    ['a', 'device', 'uses device'],
    ['a', 'merchant', 'transacts with'],
    ['b', 'device', 'uses device'],
    ['merchant', 'bank', 'pays out to'],
    ['merchant2', 'bank', 'pays out to'],
  ]);
  expect(graph.nodes.find((node) => node.id === 'isolated')).toBeDefined();
  expect(
    graph.edges.some(
      (edge) => edge.source === 'isolated' || edge.target === 'isolated',
    ),
  ).toBe(false);
  expect(graph.edges.every((edge) => !('event_count' in edge))).toBe(true);
  expect(projectEvidenceGraph(queries)).toEqual(graph);
  expect(
    graph.nodes.find((node) => node.id === 'bank')?.shared_infrastructure,
  ).toBe(true);
});

test('timeline presentation sorts chronologically with deterministic ties and does not mutate events', () => {
  const events = [
    { event_id: 'b', timestamp: '2026-01-02T00:00:00Z' },
    { event_id: 'z', timestamp: '2026-01-01T00:00:00Z' },
    { event_id: 'a', timestamp: '2026-01-01T00:00:00Z' },
  ] as EvidenceQueries['get_transaction_timeline'];
  expect(orderedEvents(events).map((event) => event.event_id)).toEqual([
    'a',
    'z',
    'b',
  ]);
  expect(events[0].event_id).toBe('b');
});

test('malformed evidence contracts fail closed instead of supplying fake empty data', () => {
  expect(validQueries({ get_ring_members: [] })).toBe(false);
  expect(validQueries(null)).toBe(false);
  expect(
    validResult({
      schema_version: '1',
      threshold: 0.71,
      event_count: 1,
      entity_count: 2,
      model_scope: 'fixture',
      rings: [],
    }),
  ).toBe(true);
  expect(
    validResult({
      schema_version: '1',
      threshold: 0.71,
      event_count: 1,
      entity_count: 2,
      model_scope: 'fixture',
      rings: [{}],
    }),
  ).toBe(false);
});
