/** Validate the fields the UI consumes. Unknown fields remain forward-compatible. */
export const object = (v: unknown): v is Record<string, unknown> =>
  v !== null && typeof v === 'object' && !Array.isArray(v);
export const strings = (v: unknown): v is string[] =>
  Array.isArray(v) && v.every((x) => typeof x === 'string');
const str = (v: unknown) => typeof v === 'string';
const num = (v: unknown) => typeof v === 'number' && Number.isFinite(v);
const status = (v: unknown) =>
  ['created', 'uploading', 'queued', 'running', 'completed', 'failed'].includes(
    String(v),
  );
export const list = (validate: (v: unknown) => boolean) => (v: unknown) =>
  Array.isArray(v) && v.every(validate);
export const validSession = (v: unknown) =>
  object(v) &&
  str(v.user_id) &&
  ((v.authentication_mode === 'development' && v.production_authentication === false) ||
    (v.authentication_mode === 'jwt' && v.production_authentication === true));
export const validInvestigation = (v: unknown) =>
  object(v) &&
  str(v.id) &&
  str(v.name) &&
  status(v.status) &&
  str(v.created_at) &&
  str(v.updated_at);
export const validArtifact = (v: unknown) =>
  object(v) &&
  str(v.id) &&
  str(v.investigation_id) &&
  str(v.original_name) &&
  num(v.size_bytes) &&
  str(v.checksum);
export const validRun = (v: unknown) =>
  object(v) &&
  str(v.id) &&
  str(v.investigation_id) &&
  str(v.artifact_id) &&
  status(v.status) &&
  str(v.created_at) &&
  object(v.version_metadata) &&
  Object.values(v.version_metadata).every(str) &&
  nullable(v.started_at, str) &&
  nullable(v.completed_at, str) &&
  nullable(v.error_code, str) &&
  nullable(v.error_message_safe, str) &&
  nullable(v.result_checksum, str) &&
  object(v.configuration_snapshot);
export const validCandidate = (v: unknown) =>
  object(v) &&
  str(v.candidate_id) &&
  num(v.risk_score) &&
  num(v.estimated_exposure_minor) &&
  strings(v.member_entity_ids) &&
  strings(v.related_event_ids) &&
  object(v.evidence) &&
  Object.values(v.evidence).every(num);
const fields = (v: unknown, text: string[], numbers: string[] = []) =>
  object(v) &&
  text.every((key) => str(v[key])) &&
  numbers.every((key) => num(v[key]));
const nullable = (v: unknown, check: (v: unknown) => boolean) =>
  v === null || check(v);
const shared = (v: unknown) =>
  fields(v, ['entity_id'], ['customer_count', 'event_count']) &&
  object(v) &&
  strings(v.customer_ids);
export function validQueries(v: unknown): boolean {
  if (!object(v)) return false;
  return (
    validCandidate(v.get_candidate_ring) &&
    list((x) => fields(x, ['entity_id', 'entity_type', 'created_at']))(
      v.get_ring_members,
    ) &&
    [
      'get_shared_devices',
      'get_shared_ips',
      'get_shared_cards',
      'get_shared_addresses',
    ].every((key) => list(shared)(v[key])) &&
    list(
      (x) =>
        fields(x, ['bank_account_id'], ['merchant_count', 'event_count']) &&
        object(x) &&
        strings(x.merchant_ids),
    )(v.get_shared_payout_accounts) &&
    list(
      (x) =>
        fields(
          x,
          ['merchant_id', 'payout_account_id'],
          ['customer_count', 'event_count'],
        ) &&
        object(x) &&
        strings(x.customer_ids),
    )(v.get_merchant_relationships) &&
    list(
      (x) =>
        fields(
          x,
          [
            'event_id',
            'event_type',
            'transaction_id',
            'timestamp',
            'status',
            'customer_id',
            'merchant_id',
          ],
          ['amount_minor'],
        ) &&
        object(x) &&
        nullable(x.risk_score, num),
    )(v.get_transaction_timeline) &&
    fields(
      v.calculate_exposure,
      ['candidate_id', 'definition'],
      ['estimated_exposure_minor'],
    ) &&
    fields(
      v.get_refund_patterns,
      [],
      ['refund_count', 'refund_amount_minor'],
    ) &&
    object(v.get_refund_patterns) &&
    list(
      (x) =>
        fields(x, ['refund_event_id', 'timestamp'], ['amount_minor']) &&
        object(x) &&
        nullable(x.original_transaction_id, str) &&
        nullable(x.refund_fraction, num) &&
        nullable(x.delay_hours, num),
    )(v.get_refund_patterns.refunds) &&
    list((x) =>
      fields(
        x,
        ['hour'],
        [
          'event_count',
          'payment_count',
          'refund_count',
          'amount_minor',
          'unique_customers',
        ],
      ),
    )(v.get_temporal_activity) &&
    list((x) =>
      fields(
        x,
        ['customer_id', 'first_event_at', 'last_event_at'],
        [
          'event_count',
          'payment_count',
          'refund_count',
          'total_amount_minor',
          'mean_amount_minor',
          'merchant_count',
          'device_count',
          'ip_count',
        ],
      ),
    )(v.compare_member_behavior)
  );
}
export const validResult = (v: unknown) =>
  object(v) &&
  v.schema_version === '1' &&
  num(v.threshold) &&
  num(v.event_count) &&
  num(v.entity_count) &&
  str(v.model_scope) &&
  Array.isArray(v.rings) &&
  v.rings.every(
    (r) =>
      object(r) &&
      validCandidate(r.candidate) &&
      object(r.candidate) &&
      str(r.candidate.first_suspicious_timestamp) &&
      strings(r.candidate.suspicious_relationships) &&
      validQueries(r.queries),
  );
