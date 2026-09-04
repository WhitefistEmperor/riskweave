'use client';
import { AlertCircle, CheckCircle2, Clock3, LoaderCircle, Circle } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { ApiError } from '@/lib/client';

export function StatusBadge({ status }: { status: string }) {
  const Icon = status === 'completed' ? CheckCircle2 : status === 'failed' ? AlertCircle : status === 'queued' ? Clock3 : status === 'running' ? LoaderCircle : Circle;
  return <span className={`run-badge badge-${status}`}><Icon size={13} />{status}</span>;
}
export function LoadingState({ label }: { label: string }) {
  return <div aria-busy="true" aria-label={label} className="loading-state"><p className="muted">{label}</p><Skeleton className="h-12 w-full" /><Skeleton className="h-12 w-full" /><Skeleton className="h-12 w-3/4" /></div>;
}
export function Failure({ error, retry }: { error: unknown; retry?: () => void }) {
  if (!error) return null;
  const api = error instanceof ApiError ? error : null;
  const title = api?.status === 401 ? 'Unauthorized' : api?.status === 404 ? 'Record not available' : api?.code === 'MALFORMED_RESPONSE' ? 'Response could not be read' : api?.status === 413 ? 'Dataset is too large' : api?.code === 'BACKEND_UNAVAILABLE' ? 'Backend unavailable' : 'Request could not be completed';
  const guidance = api?.status === 401 ? 'A valid session is required. Ask the operator to check the development identity configuration; production authentication is not connected.' : api?.status === 404 ? 'The record may no longer exist or may not be accessible to this identity. Return to Investigations to choose an available record.' : api?.status === 413 ? 'Use a smaller DatasetBundle JSON file within the configured upload limit. No analysis was started.' : api?.status === 400 || api?.status === 422 ? 'Check that the file is a valid RingSentinel DatasetBundle JSON export, then upload it again. Arbitrary payment exports are not supported.' : 'Your saved investigation is retained. Check the API connection or share the request ID with the operator.';
  return <Card className="panel p-5 failure-state" role="alert"><div className="flex items-center gap-3"><AlertCircle size={19} /><h2>{title}</h2></div><p>{api ? api.message : error instanceof Error ? error.message : 'Request failed.'}</p><p className="muted">{guidance}</p>{retry && <Button variant="outline" onClick={retry}>Retry loading saved state</Button>}</Card>;
}
