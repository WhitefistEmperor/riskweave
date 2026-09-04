/** Validate the fields the UI consumes. Unknown fields remain forward-compatible. */
export const object = (v: unknown): v is Record<string, unknown> => v !== null && typeof v === 'object' && !Array.isArray(v);
export const strings = (v: unknown): v is string[] => Array.isArray(v) && v.every(x => typeof x === 'string');
const str = (v: unknown) => typeof v === 'string';
const num = (v: unknown) => typeof v === 'number' && Number.isFinite(v);
const status = (v: unknown) => ['created', 'uploading', 'queued', 'running', 'completed', 'failed'].includes(String(v));
export const list = (validate: (v: unknown) => boolean) => (v: unknown) => Array.isArray(v) && v.every(validate);
export const validSession = (v: unknown) => object(v) && str(v.user_id) && v.authentication_mode === 'development' && v.production_authentication === false;
export const validInvestigation = (v: unknown) => object(v) && str(v.id) && str(v.name) && status(v.status) && str(v.created_at) && str(v.updated_at);
export const validArtifact = (v: unknown) => object(v) && str(v.id) && str(v.investigation_id) && str(v.original_name) && num(v.size_bytes) && str(v.checksum);
export const validRun = (v: unknown) => object(v) && str(v.id) && str(v.investigation_id) && str(v.artifact_id) && status(v.status) && str(v.created_at) && object(v.version_metadata) && object(v.configuration_snapshot);
export const validCandidate = (v: unknown) => object(v) && str(v.candidate_id) && num(v.risk_score) && num(v.estimated_exposure_minor) && strings(v.member_entity_ids) && strings(v.related_event_ids) && object(v.evidence) && Object.values(v.evidence).every(num);
export const validResult = (v: unknown) => object(v) && v.schema_version === '1' && num(v.threshold) && num(v.event_count) && num(v.entity_count) && str(v.model_scope) && Array.isArray(v.rings) && v.rings.every(r => object(r) && validCandidate(r.candidate) && object(r.queries));
