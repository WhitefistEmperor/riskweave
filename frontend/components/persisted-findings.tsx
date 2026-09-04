'use client';
import { useEffect, useMemo, useState } from 'react';
import { ArrowUpRight, Network, ListChecks, MessageSquare } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import { Investigator } from '@/components/investigator';
import { EvidenceValue } from '@/components/evidence-value';
import { evidenceGroups, evidenceLabel, queryValue } from '@/lib/evidence';
import { money, shortId } from '@/lib/api';
import type { AnalysisResult } from '@/lib/platform-api';

export function PersistedFindings({
  result,
  runId,
}: {
  result: AnalysisResult;
  runId: string;
}) {
  const ranked = useMemo(
    () =>
      [...result.rings].sort(
        (a, b) =>
          b.candidate.risk_score - a.candidate.risk_score ||
          a.candidate.candidate_id.localeCompare(b.candidate.candidate_id),
      ),
    [result],
  );
  const [ringId, setRingId] = useState('');
  const [view, setView] = useState('evidence');
  const [page, setPage] = useState(0);
  useEffect(() => {
    const sync = () => {
      const url = new URL(window.location.href);
      const selected =
        url.searchParams.get('ring') ?? ranked[0]?.candidate.candidate_id ?? '';
      setRingId(selected);
      setView(url.searchParams.get('view') ?? 'evidence');
      // Canonical address of this completed run, including selection. No local-storage database.
      if (!url.searchParams.has('run')) url.searchParams.set('run', runId);
      window.history.replaceState(null, '', url);
    };
    sync();
    window.addEventListener('popstate', sync);
    window.addEventListener('ringsentinel:navigation', sync);
    return () => {
      window.removeEventListener('popstate', sync);
      window.removeEventListener('ringsentinel:navigation', sync);
    };
  }, [runId, ranked]);
  function navigate(id: string, tab = view) {
    const url = new URL(window.location.href);
    url.searchParams.set('run', runId);
    url.searchParams.set('ring', id);
    url.searchParams.set('view', tab);
    window.history.pushState(null, '', url);
    setRingId(id);
    setView(tab);
  }
  const selected = ranked.find(
    (item) => item.candidate.candidate_id === ringId,
  );
  return (
    <div className="findings-workspace">
      <div className="findings-summary">
        <div>
          <h2>Persisted findings</h2>
          <p className="muted">
            Ranked for review, not confirmed fraud. Start with a candidate, then
            inspect its connections.
          </p>
        </div>
        <div className="summary-values">
          <div>
            <strong>{result.rings.length}</strong>
            <span>Candidate rings</span>
          </div>
          <div>
            <strong>{result.event_count.toLocaleString()}</strong>
            <span>Events analyzed</span>
          </div>
          <div>
            <strong>{result.entity_count.toLocaleString()}</strong>
            <span>Entities in dataset</span>
          </div>
          <div>
            <strong>{result.threshold.toFixed(2)}</strong>
            <span>Detection threshold</span>
          </div>
        </div>
      </div>
      {!ranked.length ? (
        <Card className="panel workspace-empty">
          <Network size={30} />
          <h3>No candidate rings</h3>
          <p>
            No candidate rings were detected. This is not proof of legitimacy.
          </p>
          <p className="muted text-xs">
            All {result.event_count.toLocaleString()} submitted events were
            analyzed. There is no ring evidence to investigate for this run.
          </p>
        </Card>
      ) : (
        <>
          <Card className="panel">
            <div className="section-heading">
              <h3>Candidate review queue</h3>
              <span className="muted text-xs">
                Highest model score first · score is not a probability
              </span>
            </div>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Candidate</TableHead>
                  <TableHead>Model score</TableHead>
                  <TableHead>Customers</TableHead>
                  <TableHead>Events</TableHead>
                  <TableHead>Observed sharing</TableHead>
                  <TableHead>Estimated exposure</TableHead>
                  <TableHead>
                    <span className="sr-only">Inspect</span>
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {ranked
                  .slice(page * 8, page * 8 + 8)
                  .map(({ candidate, queries }, index) => (
                    <TableRow
                      key={candidate.candidate_id}
                      data-selected={
                        candidate.candidate_id === ringId || undefined
                      }
                    >
                      <TableCell>
                        <button
                          className="candidate-link"
                          onClick={() => navigate(candidate.candidate_id)}
                          aria-label={`Inspect candidate ${shortId(candidate.candidate_id)}`}
                        >
                          <span className="rank-number">
                            {String(page * 8 + index + 1).padStart(2, '0')}
                          </span>
                          <span>{shortId(candidate.candidate_id)}</span>
                        </button>
                      </TableCell>
                      <TableCell>
                        <span className="score-value">
                          {candidate.risk_score.toFixed(3)}
                        </span>
                      </TableCell>
                      <TableCell>
                        {queries.compare_member_behavior.length}
                      </TableCell>
                      <TableCell>
                        {candidate.related_event_ids.length}
                      </TableCell>
                      <TableCell className="sharing-summary">
                        {[
                          ['Devices', queries.get_shared_devices.length],
                          ['IPs', queries.get_shared_ips.length],
                          ['Cards', queries.get_shared_cards.length],
                          [
                            'Payouts',
                            queries.get_shared_payout_accounts.length,
                          ],
                          ['Addresses', queries.get_shared_addresses.length],
                        ]
                          .filter(([, count]) => Number(count) > 0)
                          .map(
                            ([label, count]) =>
                              `${count} ${String(label).toLowerCase()}`,
                          )
                          .join(' · ') || 'No shared resources reported'}
                      </TableCell>
                      <TableCell className="whitespace-nowrap">
                        {money(candidate.estimated_exposure_minor)}
                      </TableCell>
                      <TableCell>
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          aria-label={`Open ring ${shortId(candidate.candidate_id)}`}
                          onClick={() => navigate(candidate.candidate_id)}
                        >
                          <ArrowUpRight size={16} />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
              </TableBody>
            </Table>
            <div className="list-pagination">
              <span>
                {page * 8 + 1}–{Math.min(page * 8 + 8, ranked.length)} of{' '}
                {ranked.length} candidates
              </span>
              <Button
                size="sm"
                variant="outline"
                disabled={!page}
                onClick={() => setPage((n) => n - 1)}
              >
                Previous candidates
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={(page + 1) * 8 >= ranked.length}
                onClick={() => setPage((n) => n + 1)}
              >
                Next candidates
              </Button>
            </div>
          </Card>
          {!selected && (
            <Card className="panel p-5" role="alert">
              <h3>Candidate not available in this run</h3>
              <p className="muted">
                The saved URL does not identify a candidate in these results.
                Select a candidate from the review queue.
              </p>
            </Card>
          )}
          {selected && (
            <section
              className="candidate-workspace"
              aria-label="Selected candidate"
            >
              <div className="candidate-heading">
                <div>
                  <span className="product-kicker">RING EXPLORER</span>
                  <h2>Candidate {shortId(selected.candidate.candidate_id)}</h2>
                  <p className="muted">
                    {selected.queries.compare_member_behavior.length} customers
                    · {selected.candidate.related_event_ids.length} related
                    events · {selected.candidate.member_entity_ids.length}{' '}
                    member entities
                  </p>
                </div>
                <div className="exposure-caption">
                  <span>Estimated exposure</span>
                  <strong>
                    {money(selected.candidate.estimated_exposure_minor)}
                  </strong>
                  <small>Candidate-associated value · not confirmed loss</small>
                </div>
              </div>
              <p className="scope-note">
                Retrospective analysis of the uploaded dataset. Model score{' '}
                {selected.candidate.risk_score.toFixed(3)} is uncalibrated, not
                a fraud probability. Shared infrastructure can be legitimate.
              </p>
              <Tabs
                value={view}
                onValueChange={(value) => navigate(ringId, String(value))}
                className="candidate-tabs"
              >
                <TabsList variant="line">
                  <TabsTrigger value="evidence">
                    <ListChecks size={16} />
                    Evidence
                  </TabsTrigger>
                  <TabsTrigger value="investigator">
                    <MessageSquare size={16} />
                    Investigator
                  </TabsTrigger>
                </TabsList>
                <TabsContent value="evidence">
                  <div className="grouped-evidence">
                    {evidenceGroups.map((group) => (
                      <Card className="panel" key={group.title}>
                        <div className="section-heading">
                          <div>
                            <h3>{group.title}</h3>
                            <p className="muted text-xs">{group.description}</p>
                          </div>
                        </div>
                        <Accordion multiple>
                          {group.keys.map((key) => (
                            <AccordionItem key={key} value={key}>
                              <AccordionTrigger>
                                {evidenceLabel(key)}
                              </AccordionTrigger>
                              <AccordionContent>
                                <EvidenceValue
                                  value={queryValue(selected.queries, key)}
                                />
                              </AccordionContent>
                            </AccordionItem>
                          ))}
                        </Accordion>
                      </Card>
                    ))}
                  </div>
                </TabsContent>
                <TabsContent value="investigator">
                  <Investigator
                    key={`${runId}-${ringId}`}
                    runId={runId}
                    candidateId={ringId}
                  />
                </TabsContent>
              </Tabs>
            </section>
          )}
        </>
      )}
      <p className="model-scope">
        {result.model_scope}. Evidence is limited to this run; no ground-truth
        labels are used to explain a finding.
      </p>
    </div>
  );
}
