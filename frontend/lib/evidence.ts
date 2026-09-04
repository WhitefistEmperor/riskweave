import type { JsonValue, GraphNode } from '@/lib/api';
import type { PersistedCandidate } from '@/lib/platform-api';

export type SharedEntity = {
  entity_id: string;
  customer_ids: string[];
  customer_count: number;
  event_count: number;
};
export type SharedPayout = {
  bank_account_id: string;
  merchant_ids: string[];
  merchant_count: number;
  event_count: number;
};
export type MerchantRelationship = {
  merchant_id: string;
  payout_account_id: string;
  customer_ids: string[];
  customer_count: number;
  event_count: number;
};
export type EvidenceEvent = {
  event_id: string;
  event_type: string;
  transaction_id: string;
  timestamp: string;
  amount_minor: number;
  status: string;
  customer_id: string;
  merchant_id: string;
  risk_score: number | null;
};
export type EvidenceQueries = {
  get_candidate_ring: PersistedCandidate;
  get_ring_members: {
    entity_id: string;
    entity_type: string;
    created_at: string;
  }[];
  get_shared_devices: SharedEntity[];
  get_shared_ips: SharedEntity[];
  get_shared_cards: SharedEntity[];
  get_shared_addresses: SharedEntity[];
  get_shared_payout_accounts: SharedPayout[];
  get_transaction_timeline: EvidenceEvent[];
  get_refund_patterns: {
    refund_count: number;
    refund_amount_minor: number;
    refunds: {
      refund_event_id: string;
      original_transaction_id: string | null;
      timestamp: string;
      amount_minor: number;
      refund_fraction: number | null;
      delay_hours: number | null;
    }[];
  };
  get_merchant_relationships: MerchantRelationship[];
  get_temporal_activity: {
    hour: string;
    event_count: number;
    payment_count: number;
    refund_count: number;
    amount_minor: number;
    unique_customers: number;
  }[];
  calculate_exposure: {
    candidate_id: string;
    estimated_exposure_minor: number;
    definition: string;
  };
  compare_member_behavior: {
    customer_id: string;
    event_count: number;
    payment_count: number;
    refund_count: number;
    total_amount_minor: number;
    mean_amount_minor: number;
    merchant_count: number;
    device_count: number;
    ip_count: number;
    first_event_at: string;
    last_event_at: string;
  }[];
};
export type EvidenceKey = keyof EvidenceQueries;
export const evidenceGroups: {
  title: string;
  description: string;
  keys: EvidenceKey[];
}[] = [
  {
    title: 'Shared infrastructure',
    description:
      'Resources used by multiple observed customers or merchants. Sharing alone is not evidence of fraud.',
    keys: [
      'get_shared_devices',
      'get_shared_ips',
      'get_shared_cards',
      'get_shared_addresses',
      'get_shared_payout_accounts',
    ],
  },
  {
    title: 'Members & commerce',
    description:
      'Recorded members, merchant connections and differences in member activity.',
    keys: [
      'get_ring_members',
      'get_merchant_relationships',
      'compare_member_behavior',
    ],
  },
  {
    title: 'Money & refunds',
    description:
      'Candidate-associated exposure, not a confirmed loss or calibrated expected loss.',
    keys: ['calculate_exposure', 'get_refund_patterns'],
  },
  {
    title: 'Activity & detector output',
    description:
      'The complete retrospective event window and the detector’s recorded output.',
    keys: [
      'get_temporal_activity',
      'get_transaction_timeline',
      'get_candidate_ring',
    ],
  },
];
export const evidenceLabel = (key: string) =>
  ({
    get_shared_ips: 'Shared IP addresses',
    calculate_exposure: 'Exposure accounting',
    compare_member_behavior: 'Member comparison',
    get_candidate_ring: 'Detector output',
  })[key] ??
  key
    .replace(/^get_/, '')
    .replaceAll('_', ' ')
    .replace(/^./, (c) => c.toUpperCase());
export const orderedEvents = (events: EvidenceEvent[]) =>
  [...events].sort(
    (a, b) =>
      a.timestamp.localeCompare(b.timestamp) ||
      a.event_id.localeCompare(b.event_id),
  );
export const queryValue = (
  queries: EvidenceQueries,
  key: EvidenceKey,
): JsonValue => queries[key];

// This is a projection of explicit query records, NOT a new inference/detection graph.
export type EvidenceEdge = {
  id: string;
  source: string;
  target: string;
  relationship: string;
  query: EvidenceKey;
};
export type EvidenceGraph = { nodes: GraphNode[]; edges: EvidenceEdge[] };
export function projectEvidenceGraph(queries: EvidenceQueries): EvidenceGraph {
  const nodes = new Map<string, GraphNode>();
  const edges = new Map<string, EvidenceEdge>();
  for (const member of queries.get_ring_members)
    nodes.set(member.entity_id, {
      id: member.entity_id,
      type: member.entity_type,
      shared_infrastructure: false,
    });
  const add = (id: string, type: string, shared = false) =>
    nodes.set(id, {
      id,
      type,
      shared_infrastructure:
        shared || nodes.get(id)?.shared_infrastructure || false,
    });
  const connect = (
    source: string,
    target: string,
    relationship: string,
    query: EvidenceKey,
  ) => {
    const id = `${source}|${target}|${relationship}`;
    if (!edges.has(id))
      edges.set(id, { id, source, target, relationship, query });
  };
  for (const [key, type] of [
    ['get_shared_devices', 'DEVICE'],
    ['get_shared_ips', 'IP'],
    ['get_shared_cards', 'CARD'],
    ['get_shared_addresses', 'ADDRESS'],
  ] as const) {
    for (const resource of queries[key]) {
      add(resource.entity_id, type, true);
      for (const customer of resource.customer_ids) {
        add(customer, 'CUSTOMER');
        connect(
          customer,
          resource.entity_id,
          `uses ${type.toLowerCase()}`,
          key,
        );
      }
    }
  }
  for (const merchant of queries.get_merchant_relationships) {
    add(merchant.merchant_id, 'MERCHANT');
    add(merchant.payout_account_id, 'BANK_ACCOUNT');
    connect(
      merchant.merchant_id,
      merchant.payout_account_id,
      'pays out to',
      'get_merchant_relationships',
    );
    for (const customer of merchant.customer_ids) {
      add(customer, 'CUSTOMER');
      connect(
        customer,
        merchant.merchant_id,
        'transacts with',
        'get_merchant_relationships',
      );
    }
  }
  for (const payout of queries.get_shared_payout_accounts) {
    add(payout.bank_account_id, 'BANK_ACCOUNT', true);
    for (const merchant of payout.merchant_ids) {
      add(merchant, 'MERCHANT');
      connect(
        merchant,
        payout.bank_account_id,
        'pays out to',
        'get_shared_payout_accounts',
      );
    }
  }
  return {
    nodes: [...nodes.values()].sort(
      (a, b) => a.type.localeCompare(b.type) || a.id.localeCompare(b.id),
    ),
    edges: [...edges.values()].sort((a, b) => a.id.localeCompare(b.id)),
  };
}
