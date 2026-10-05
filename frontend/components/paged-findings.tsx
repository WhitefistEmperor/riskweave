'use client';
import { useEffect, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import {
  Table,
  TableHeader,
  TableBody,
  TableHead,
  TableCell,
  TableRow,
} from '@/components/ui/table';
import { Failure, LoadingState } from '@/components/workspace-states';
import { PersistedFindings } from '@/components/persisted-findings';
import {
  loadCandidatePage,
  loadSection,
  type CandidatePage,
} from '@/lib/section-transport';
import { ApiError } from '@/lib/client';
import { money, shortId } from '@/lib/api';
import type {
  AnalysisResult,
  AnalysisRun,
  PersistedCandidate,
} from '@/lib/platform-api';
import type { EvidenceQueries } from '@/lib/evidence';

export function PagedFindings({
  result,
  run,
}: {
  result: AnalysisResult;
  run: AnalysisRun;
}) {
  const total = result.remote_candidate_count ?? 0;
  const [offset, setOffset] = useState(0);
  const [page, setPage] = useState<CandidatePage | null>(null);
  const [pageError, setPageError] = useState<unknown>(null);
  const [selection, setSelection] = useState('');
  const [detail, setDetail] = useState<{
    candidate: PersistedCandidate;
    queries: EvidenceQueries;
  } | null>(null);
  const [detailError, setDetailError] = useState<unknown>(null);
  const [progress, setProgress] = useState<{
    received: number;
    total: number;
  } | null>(null);
  const [attempt, setAttempt] = useState(0);
  const focusAfterLoad = useRef(false);
  const runId = run.id;
  const activePage = page?.offset === offset ? page : null;
  const activeDetail =
    detail?.candidate.candidate_id === selection ? detail : null;
  useEffect(() => {
    const controller = new AbortController();
    queueMicrotask(() => {
      if (!controller.signal.aborted) {
        setPageError(null);
      }
    });
    loadCandidatePage(run, offset, 8, controller.signal)
      .then((value) => {
        if (controller.signal.aborted) return;
        if (value.total !== total)
          throw new ApiError(
            'Candidate count did not match this run.',
            200,
            'MALFORMED_RESPONSE',
            crypto.randomUUID(),
          );
        setPage(value);
      })
      .catch((error) => {
        if (!controller.signal.aborted) setPageError(error);
      });
    return () => controller.abort();
  }, [run, offset, total, attempt]);
  useEffect(() => {
    const sync = () => {
      const url = new URL(window.location.href);
      setSelection(
        url.searchParams.get('ring') ?? page?.items[0]?.candidate_id ?? '',
      );
    };
    sync();
    window.addEventListener('popstate', sync);
    window.addEventListener('ringsentinel:navigation', sync);
    return () => {
      window.removeEventListener('popstate', sync);
      window.removeEventListener('ringsentinel:navigation', sync);
    };
  }, [page]);
  useEffect(() => {
    // Clear status from the previous request in the async lifecycle; old evidence is scoped out at render.
    if (!selection) return;
    const controller = new AbortController();
    queueMicrotask(() => {
      if (!controller.signal.aborted) {
        setDetailError(null);
        setProgress(null);
      }
    });
    Promise.all([
      loadSection(run, selection, 'candidate', controller.signal),
      loadSection(
        run,
        selection,
        'evidence',
        controller.signal,
        (received, size) => {
          if (!controller.signal.aborted)
            setProgress({ received, total: size });
        },
      ),
    ])
      .then(([candidate, queries]) => {
        if (!controller.signal.aborted)
          setDetail({
            candidate: candidate as PersistedCandidate,
            queries: queries as EvidenceQueries,
          });
      })
      .catch((error) => {
        if (!controller.signal.aborted) {
          setDetailError(error);
          controller.abort();
        }
      });
    return () => controller.abort();
  }, [run, selection, attempt]);
  useEffect(() => {
    if (detail && focusAfterLoad.current) {
      focusAfterLoad.current = false;
      document
        .querySelector<HTMLElement>('.candidate-workspace')
        ?.focus({ preventScroll: true });
      document
        .querySelector('.candidate-workspace')
        ?.scrollIntoView({ block: 'start' });
    }
  }, [detail]);
  function open(id: string) {
    const url = new URL(window.location.href);
    url.searchParams.set('run', runId);
    url.searchParams.set('ring', id);
    window.history.pushState(null, '', url);
    focusAfterLoad.current = true;
    setSelection(id);
    if (id === selection)
      document.querySelector<HTMLElement>('.candidate-workspace')?.focus();
  }
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
            <strong>{total}</strong>
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
      {!total ? (
        <Card className="panel workspace-empty">
          <h3>No candidate rings</h3>
          <p>
            No candidate rings were detected. This is not proof of legitimacy.
          </p>
        </Card>
      ) : (
        <>
          <Card className="panel">
            <div className="section-heading">
              <h3>Candidate review queue</h3>
              <span className="muted text-xs">
                Saved candidate order · score is not a probability
              </span>
            </div>
            {pageError ? (
              <Failure
                error={pageError}
                retry={() => setAttempt((value) => value + 1)}
              />
            ) : !activePage ? (
              <LoadingState label="Loading candidate page…" />
            ) : (
              <>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Candidate</TableHead>
                      <TableHead>Model score</TableHead>
                      <TableHead>Members</TableHead>
                      <TableHead>Events</TableHead>
                      <TableHead>Estimated exposure</TableHead>
                      <TableHead>Inspect</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {activePage.items.map((candidate, index) => (
                      <TableRow
                        key={candidate.candidate_id}
                        data-selected={
                          candidate.candidate_id === selection || undefined
                        }
                      >
                        <TableCell>
                          <button
                            className="candidate-link"
                            onClick={() => open(candidate.candidate_id)}
                            aria-label={`Inspect candidate ${shortId(candidate.candidate_id)}`}
                          >
                            <span className="rank-number">
                              {String(offset + index + 1).padStart(2, '0')}
                            </span>{' '}
                            {shortId(candidate.candidate_id)}
                          </button>
                        </TableCell>
                        <TableCell>{candidate.risk_score.toFixed(3)}</TableCell>
                        <TableCell>
                          {candidate.member_entity_ids.length}
                        </TableCell>
                        <TableCell>
                          {candidate.related_event_ids.length}
                        </TableCell>
                        <TableCell>
                          {money(
                            candidate.estimated_exposure_minor,
                            result.currency,
                          )}
                        </TableCell>
                        <TableCell>
                          <Button
                            variant="ghost"
                            size="sm"
                            aria-label={`Open ring ${shortId(candidate.candidate_id)}`}
                            onClick={() => open(candidate.candidate_id)}
                          >
                            Open
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
                <div className="list-pagination">
                  <span>
                    {activePage.items.length ? offset + 1 : 0}–
                    {offset + activePage.items.length} of {total} candidates
                  </span>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={!offset}
                    onClick={() => setOffset((value) => Math.max(0, value - 8))}
                  >
                    Previous candidates
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={activePage.next_offset === null}
                    onClick={() => setOffset(activePage.next_offset ?? offset)}
                  >
                    Next candidates
                  </Button>
                </div>
              </>
            )}
          </Card>
          {detailError ? (
            <Failure
              error={detailError}
              retry={() => setAttempt((value) => value + 1)}
            />
          ) : selection && !activeDetail ? (
            <output aria-live="polite">
              <LoadingState label="Loading selected evidence…" />
              {progress && (
                <p className="muted">
                  {progress.received.toLocaleString()} of{' '}
                  {progress.total.toLocaleString()} bytes verified. Evidence
                  appears after the complete integrity check.
                </p>
              )}
            </output>
          ) : activeDetail ? (
            <PersistedFindings
              key={`${runId}:${selection}`}
              result={{ ...result, rings: [activeDetail] }}
              runId={runId}
              detailOnly
            />
          ) : null}
        </>
      )}
      {!activeDetail && (
        <p className="model-scope">
          Amount currency:{' '}
          {result.currency ?? 'unknown; amounts are shown in minor units'}. No
          currency conversion is applied. {result.model_scope}. Evidence is
          limited to this run; no ground-truth labels are used to explain a
          finding.
        </p>
      )}
    </div>
  );
}
