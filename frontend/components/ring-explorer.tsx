'use client';

import { useEffect, useState } from 'react';
import { Investigator } from '@/components/investigator';
import { ArrowLeft, CircleHelp } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import { RingGraph } from '@/components/ring-graph';
import { EvidenceValue, humanize } from '@/components/evidence-value';
import { apiGet, dateTime, money, shortId, type RingSnapshot } from '@/lib/api';

export function RingExplorer({
  eventCount,
  initialCandidate,
  onBack,
}: {
  eventCount?: number;
  initialCandidate?: string;
  onBack: () => void;
}) {
  const [snapshot, setSnapshot] = useState<RingSnapshot | null>(null);
  const [selectedId, setSelectedId] = useState(initialCandidate ?? '');
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    const query = new URLSearchParams();
    if (eventCount !== undefined) query.set('event_count', String(eventCount));
    if (selectedId) query.set('candidate_id', selectedId);
    apiGet<RingSnapshot>(`/snapshot?${query.toString()}`)
      .then((value) => {
        if (active) {
          setSnapshot(value);
          setError('');
        }
      })
      .catch((reason: unknown) => {
        if (active) setError(String(reason));
      });
    return () => {
      active = false;
    };
  }, [eventCount, selectedId]);
  if (error)
    return (
      <Card className="panel p-5">
        <h2>Snapshot unavailable</h2>
        <p>{error}</p>
        <Button onClick={onBack}>Back to overview</Button>
      </Card>
    );
  if (!snapshot) return <Skeleton className="h-96 w-full" />;
  const detail = snapshot.selected;
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">EVIDENCE WORKSPACE</p>
          <h1>Ring Explorer</h1>
          <p className="muted">
            {snapshot.scope === 'observed_prefix'
              ? 'Replay snapshot · no later events included'
              : 'Completed ecosystem · not the live replay'}{' '}
            · as of {dateTime(snapshot.as_of)} UTC
          </p>
        </div>
        <Button variant="outline" onClick={onBack}>
          <ArrowLeft size={15} /> Overview
        </Button>
      </div>
      <div className="explorer-selection">
        <Select
          value={detail?.candidate.candidate_id ?? ''}
          onValueChange={(id) => {
            if (id) setSelectedId(id);
          }}
        >
          <SelectTrigger aria-label="Select candidate ring" className="w-80">
            <SelectValue placeholder="Select candidate" />
          </SelectTrigger>
          <SelectContent>
            {snapshot.candidates.map((candidate) => (
              <SelectItem
                key={candidate.candidate_id}
                value={candidate.candidate_id}
              >
                Candidate {shortId(candidate.candidate_id)} · score{' '}
                {candidate.risk_score.toFixed(3)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <span className="muted">
          {snapshot.candidates.length} candidates ·{' '}
          {snapshot.observed_event_count.toLocaleString()} observed events
        </span>
      </div>
      {!detail ? (
        <Card className="panel p-5">
          No candidates in this observed prefix.
        </Card>
      ) : (
        <div key={detail.candidate.candidate_id}>
          <div className="metrics-grid">
            <Stat
              label="Uncalibrated risk score"
              value={detail.candidate.risk_score.toFixed(3)}
            />
            <Stat
              label="Member entities"
              value={String(detail.candidate.evidence.member_entities)}
            />
            <Stat
              label="Related events"
              value={String(detail.candidate.evidence.events)}
            />
            <Stat
              label="Estimated exposure"
              value={money(detail.candidate.estimated_exposure_minor)}
            />
          </div>
          <Tabs defaultValue="network">
            <TabsList className="mb-5">
              <TabsTrigger value="network">Network & evidence</TabsTrigger>
              <TabsTrigger value="timeline">Activity timeline</TabsTrigger>
              <TabsTrigger value="investigator">Investigator</TabsTrigger>
            </TabsList>
            <TabsContent value="network">
              <div className="explorer-grid">
                <Card className="panel">
                  <div className="panel-heading">
                    <div>
                      <p className="eyebrow">CONNECTED EVENT GRAPH</p>
                      <h2>Follow the shared infrastructure</h2>
                    </div>
                    <span className="status-chip amber">Review hypothesis</span>
                  </div>
                  <RingGraph graph={detail.graph} />
                </Card>
                <div className="space-y-5">
                  <Card className="panel p-5">
                    <p className="eyebrow">DETECTION CONTEXT</p>
                    <h2>Evidence, not a verdict</h2>
                    <p className="muted text-sm mt-3">
                      First suspicious event
                      <br />
                      <span className="text-foreground">
                        {dateTime(detail.candidate.first_suspicious_timestamp)}{' '}
                        UTC
                      </span>
                    </p>
                    <p className="muted text-sm mt-3">
                      First connected precursor
                      <br />
                      <span className="text-foreground">
                        {dateTime(
                          String(
                            detail.candidate
                              .first_connected_precursor_timestamp,
                          ),
                        )}{' '}
                        UTC
                      </span>
                    </p>
                    <EvidenceValue
                      value={
                        detail.candidate.suspicious_relationships as string[]
                      }
                    />
                    <p className="trust-note mt-4">
                      <CircleHelp size={16} />
                      Shared infrastructure can be legitimate. This model
                      combines transaction, temporal, and network features;
                      analyst verification is required.
                    </p>
                  </Card>
                  <Card className="panel p-5">
                    <h2>Exposure definition</h2>
                    <EvidenceValue value={detail.evidence.exposure} />
                    <p className="muted text-sm mt-3">
                      Not expected loss. Synthetic expected-loss rates, where
                      used in ground truth, are assumptions rather than
                      calibrated probabilities.
                    </p>
                  </Card>
                </div>
              </div>
              <Card className="panel mt-5">
                <div className="panel-heading">
                  <h2>Computed evidence</h2>
                  <span className="muted text-sm">
                    Exact query outputs · IDs abbreviated; hover for full values
                  </span>
                </div>
                <Accordion multiple className="px-5">
                  {Object.entries(detail.evidence)
                    .filter(([key]) => key !== 'candidate')
                    .map(([key, value]) => (
                      <AccordionItem key={key} value={key}>
                        <AccordionTrigger>{humanize(key)}</AccordionTrigger>
                        <AccordionContent>
                          <EvidenceValue value={value} />
                        </AccordionContent>
                      </AccordionItem>
                    ))}
                </Accordion>
              </Card>
            </TabsContent>
            <TabsContent value="timeline">
              <Card className="panel">
                <div className="panel-heading">
                  <h2>Observed event chronology</h2>
                  <span className="status-chip">
                    UTC · demo truth labeled separately
                  </span>
                </div>
                <ol className="timeline">
                  {detail.timeline.events.map((event, index) => (
                    <li
                      key={`${event.timestamp}-${index}`}
                      className={event.ground_truth_only ? 'truth-stage' : ''}
                    >
                      <div className="timeline-time">
                        {dateTime(event.timestamp)}
                        <small>
                          {event.ground_truth_only
                            ? 'DEMO GROUND TRUTH'
                            : event.kind.replaceAll('_', ' ')}
                        </small>
                      </div>
                      <div>
                        <strong>{event.title}</strong>
                        <p className="muted">{event.detail}</p>
                        {event.risk_score !== null && (
                          <span className="mono">
                            Event risk {event.risk_score.toFixed(3)}
                          </span>
                        )}
                      </div>
                    </li>
                  ))}
                </ol>
              </Card>
            </TabsContent>
            <TabsContent value="investigator">
              <Investigator
                candidateId={detail.candidate.candidate_id}
                eventCount={eventCount}
              />
            </TabsContent>
          </Tabs>
        </div>
      )}
    </>
  );
}
function Stat({ label, value }: { label: string; value: string }) {
  return (
    <Card className="metric-card">
      <span>{label}</span>
      <strong>{value}</strong>
    </Card>
  );
}
