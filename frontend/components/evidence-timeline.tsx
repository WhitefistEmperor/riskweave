'use client';
import { useMemo, useState } from 'react';
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
import { EvidenceValue } from '@/components/evidence-value';
import { orderedEvents, type EvidenceQueries } from '@/lib/evidence';
import { dateTime, money, shortId } from '@/lib/api';

export function EvidenceTimeline({ queries }: { queries: EvidenceQueries }) {
  const events = useMemo(
    () => orderedEvents(queries.get_transaction_timeline),
    [queries],
  );
  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState('');
  const item = events.find((event) => event.event_id === selected);
  return (
    <div className="timeline-workspace">
      <Card className="panel">
        <div className="section-heading">
          <div>
            <h3>Candidate activity</h3>
            <p className="muted text-xs">
              Chronological · All times UTC · {events.length} recorded events
            </p>
          </div>
          <span className="workspace-count">RETROSPECTIVE</span>
        </div>
        <p className="timeline-disclosure">
          These timestamps describe events in the uploaded dataset, not when a
          live system detected them. No early-warning claim is made here.
        </p>
        {!events.length ? (
          <p className="p-5 muted">
            No events were returned for this candidate.
          </p>
        ) : (
          <>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Timestamp (UTC)</TableHead>
                  <TableHead>Event</TableHead>
                  <TableHead>Amount</TableHead>
                  <TableHead>Customer → merchant</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Details</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {events.slice(page * 25, page * 25 + 25).map((event) => (
                  <TableRow
                    key={event.event_id}
                    data-selected={selected === event.event_id || undefined}
                  >
                    <TableCell className="whitespace-nowrap">
                      {dateTime(event.timestamp)}
                    </TableCell>
                    <TableCell>
                      <span
                        className={`event-type event-${event.event_type.toLowerCase()}`}
                      >
                        {event.event_type.toLowerCase()}
                      </span>
                    </TableCell>
                    <TableCell className="whitespace-nowrap">
                      {money(event.amount_minor)}
                    </TableCell>
                    <TableCell className="mono">
                      {shortId(event.customer_id)} →{' '}
                      {shortId(event.merchant_id)}
                    </TableCell>
                    <TableCell>{event.status.toLowerCase()}</TableCell>
                    <TableCell>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setSelected(event.event_id)}
                        aria-label={`Inspect event ${shortId(event.event_id)}`}
                      >
                        {shortId(event.event_id)}
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <div className="list-pagination">
              <span>
                {page * 25 + 1}–{Math.min(page * 25 + 25, events.length)} of{' '}
                {events.length}
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={!page}
                onClick={() => setPage((n) => n - 1)}
              >
                Earlier events
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={(page + 1) * 25 >= events.length}
                onClick={() => setPage((n) => n + 1)}
              >
                Later events
              </Button>
            </div>
          </>
        )}
        {item && (
          <div className="event-detail">
            <h3>Event {shortId(item.event_id)}</h3>
            <EvidenceValue value={item} />
            <p className="muted text-xs">
              Event risk score is a model output, not a fraud probability.
            </p>
          </div>
        )}
      </Card>
      <Card className="panel p-5">
        <h3>Activity by hour</h3>
        <p className="muted text-xs mb-4">
          Computed hourly buckets. Amount totals describe activity, not net
          exposure.
        </p>
        <EvidenceValue value={queries.get_temporal_activity} />
      </Card>
    </div>
  );
}
