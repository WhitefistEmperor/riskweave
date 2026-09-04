'use client';

import { useState } from 'react';
import { useInvestigation } from '@/hooks/use-investigation';
import { ProductShell as Workspace } from '@/components/product-shell';
import { Failure } from '@/components/workspace-states';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import { Investigator } from '@/components/investigator';
import { EvidenceValue, humanize } from '@/components/evidence-value';
import { money, shortId } from '@/lib/api';



export { InvestigationList } from '@/components/investigation-list';

export function InvestigationDetail({
  investigationId,
  initialRunId,
}: {
  investigationId: string;
  initialRunId?: string;
}) {
  const state = useInvestigation(investigationId, initialRunId);
  const { record, artifacts, artifactId, setArtifactId, runs, runId, run, result, error, busy, activeRun, selectRun, start } = state;
  const [ringId, setRingId] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const upload = () => file ? state.upload(file) : Promise.resolve();
  const selected = result?.rings.find(
    (item) => item.candidate.candidate_id === ringId,
  ) ?? result?.rings[0];
  return (
    <Workspace>
      <h1>{record?.name ?? 'Investigation'}</h1>
      <Failure error={error} />
      {Boolean(error) && runId && (
        <Button
          variant="outline"
          onClick={state.retry}
        >
          Resume status checks
        </Button>
      )}
      {!record && !error && <output>Loading investigation…</output>}
      {record && (
        <>
          <Card className="panel p-5 space-y-4">
            <h2>Input dataset</h2>
            <p className="muted text-sm">
              DatasetBundle JSON only. Uploads are validated and checksummed; an
              identical upload reuses its artifact.
            </p>
            <label htmlFor="dataset-file">Dataset file</label>
            <Input
              id="dataset-file"
              type="file"
              accept=".json,application/json"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
              disabled={!!busy || activeRun}
            />
            <Button
              onClick={() => void upload()}
              disabled={!file || !!busy || activeRun}
            >
              Upload dataset
            </Button>
            {artifacts.length > 0 && (
              <>
                <label id="artifact-label" htmlFor="artifact-select">
                  Analysis input
                </label>
                <Select
                  value={artifactId}
                  onValueChange={(value) => setArtifactId(String(value ?? ''))}
                  disabled={!!busy || activeRun}
                >
                  <SelectTrigger
                    id="artifact-select"
                    aria-labelledby="artifact-label"
                  >
                    <SelectValue>
                      {
                        artifacts.find((value) => value.id === artifactId)
                          ?.original_name
                      }
                    </SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    {artifacts.map((item) => (
                      <SelectItem value={item.id} key={item.id}>
                        {item.original_name} ·{' '}
                        {item.size_bytes.toLocaleString()} bytes
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Button
                  onClick={() => void start()}
                  disabled={!artifactId || !!busy || activeRun}
                >
                  {busy ? 'Working…' : 'Start analysis'}
                </Button>
              </>
            )}
          </Card>
          <Card className="panel p-5 space-y-3">
            <h2>Analysis runs</h2>
            {runs.length === 0 && !run && (
              <p className="muted">No analysis runs yet.</p>
            )}
            <div className="flex flex-wrap gap-2">
              {runs.map((item) => (
                <Button
                  variant={runId === item.id ? 'default' : 'outline'}
                  key={item.id}
                  onClick={() => selectRun(item.id)}
                >
                  {shortId(item.id)} · {item.status}
                </Button>
              ))}
            </div>
            {runId && !run && !error && <output>Loading run…</output>}
            {run && (
              <div className="space-y-2">
                <output>
                  Analysis status: <strong>{run.status}</strong>
                </output>
                {run.status === 'queued' && (
                  <p className="muted">
                    Waiting for the local analysis worker.
                  </p>
                )}
                {run.status === 'running' && (
                  <p className="muted">
                    Analysis is running. This page polls persisted status; you
                    can return later.
                  </p>
                )}
                {run.status === 'failed' && (
                  <p className="amber" role="alert">
                    {run.error_message_safe} ({run.error_code})
                  </p>
                )}
                <p className="muted text-sm">
                  Run {run.id} · App {run.version_metadata.application} ·{' '}
                  {run.version_metadata.detector}
                </p>
                {run.result_checksum && (
                  <p className="muted text-sm break-all">
                    Result SHA256: {run.result_checksum}
                  </p>
                )}
              </div>
            )}
          </Card>
          {result && (
            <Card className="panel p-5 space-y-4">
              <h2>Persisted findings</h2>
              <p>
                {result.event_count.toLocaleString()} events ·{' '}
                {result.entity_count.toLocaleString()} entities ·{' '}
                {result.rings.length} candidate rings
              </p>
              <p className="muted">
                {result.model_scope}. Threshold {result.threshold.toFixed(2)}.
              </p>
              {result.rings.length === 0 && (
                <p>
                  No candidate rings were detected. This is not proof of
                  legitimacy.
                </p>
              )}
              <div className="flex flex-wrap gap-2">
                {result.rings.map(({ candidate }) => (
                  <Button
                    variant={
                      candidate.candidate_id === ringId ? 'default' : 'outline'
                    }
                    key={candidate.candidate_id}
                    onClick={() => setRingId(candidate.candidate_id)}
                  >
                    {shortId(candidate.candidate_id)} ·{' '}
                    {money(candidate.estimated_exposure_minor)}
                  </Button>
                ))}
              </div>
              {selected && (
                <Accordion multiple>
                  {Object.entries(selected.queries).map(([query, value]) => (
                    <AccordionItem key={query} value={query}>
                      <AccordionTrigger>{humanize(query)}</AccordionTrigger>
                      <AccordionContent>
                        <EvidenceValue value={value} />
                      </AccordionContent>
                    </AccordionItem>
                  ))}
                </Accordion>
              )}
            </Card>
          )}
          {selected && run && (
            <Investigator
              key={`${run.id}-${ringId}`}
              runId={run.id}
              candidateId={selected.candidate.candidate_id}
            />
          )}
        </>
      )}
    </Workspace>
  );
}
