export type Metric = { mean: number; std: number };
export type Metrics = Record<string, Metric>;
export type Benchmark = {
  synthetic_benchmark: boolean;
  seeds: number[];
  transactions_per_seed: number;
  models: Record<string, Metrics>;
  ablations: Record<string, Metrics>;
  exposure: Record<string, unknown>;
  limitations: string[];
};
export type Overview = {
  demo_seed: number;
  monitored_entities: number;
  monitored_events: number;
  candidate_rings: number;
  suspicious_entities: number;
  estimated_exposure_minor: number;
  detection_delay_minutes: number;
};
export type CandidateState = {
  candidate_id: string;
  risk_score: number;
  customers: number;
  events: number;
  estimated_exposure_minor: number;
};
export type SimulationEvent = {
  event_id: string;
  timestamp: string;
  event_type: string;
  amount_minor: number;
  customer_id: string;
  merchant_id: string;
  device_id: string;
  ip_id: string;
  risk_score: number;
  threshold_crossed: boolean;
  observed_event_count: number;
  candidate_state: CandidateState | null;
  accumulated_relationships: {
    customers: number;
    devices: number;
    ips: number;
  };
};
export type Simulation = {
  demo_seed: number;
  threshold: number;
  ecosystem_event_count: number;
  window_start_index: number;
  attack_start_timestamp: string;
  first_alert_timestamp: string;
  earlier_isolated_alert_timestamp: string;
  detection_delay_minutes: number;
  candidate_id: string;
  events: SimulationEvent[];
};
export type Candidate = {
  candidate_id: string;
  risk_score: number;
  estimated_exposure_minor: number;
  member_entity_ids: string[];
  related_event_ids: string[];
  evidence: Record<string, number>;
  first_seen_timestamp: string;
  first_suspicious_timestamp: string;
  last_seen_timestamp: string;
  [key: string]: unknown;
};
export type ConsoleData = {
  overview: Overview;
  benchmark: Benchmark;
  simulation: Simulation;
  candidates: Candidate[];
};

export type GraphNode = {
  id: string;
  type: string;
  shared_infrastructure: boolean;
};
export type GraphData = {
  nodes: GraphNode[];
  edges: {
    source: string;
    target: string;
    relationship: string;
    event_count: number;
    suspicious: boolean;
  }[];
};
export type TimelineEvent = {
  timestamp: string;
  kind: string;
  title: string;
  detail: string;
  risk_score: number | null;
  event_id: string | null;
  ground_truth_only: boolean;
};
export type JsonValue =
  | string
  | number
  | boolean
  | null
  | JsonValue[]
  | { [key: string]: JsonValue };
export type RingSnapshot = {
  scope: string;
  observed_event_count: number;
  as_of: string;
  candidates: Candidate[];
  selected: {
    candidate: Candidate;
    members: { entity_id: string; entity_type: string; created_at: string }[];
    graph: GraphData;
    timeline: { events: TimelineEvent[] };
    evidence: Record<string, JsonValue>;
  } | null;
};
export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`/api${path}`);
  if (!response.ok)
    throw new Error(`Request failed (${response.status}): ${path}`);
  return response.json() as Promise<T>;
}
export async function loadConsoleData(): Promise<ConsoleData> {
  // Warm the single local runtime before issuing concurrent queries.
  const overview = await apiGet<Overview>('/overview');
  const [benchmark, simulation, candidates] = await Promise.all([
    apiGet<Benchmark>('/benchmark'),
    apiGet<Simulation>('/simulation'),
    apiGet<Candidate[]>('/candidates'),
  ]);
  return { overview, benchmark, simulation, candidates };
}
export const money = (minor: number) =>
  new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(minor / 100);
export const clock = (value: string) =>
  new Date(value).toLocaleTimeString('en-GB', {
    timeZone: 'UTC',
    hour12: false,
  });
export const dateTime = (value: string) =>
  new Date(value).toLocaleString('en-GB', { timeZone: 'UTC', hour12: false });
export const shortId = (value: string) => value.slice(-6).toUpperCase();
