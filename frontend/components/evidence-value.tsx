'use client';
import { useState } from 'react';
import { Button } from '@/components/ui/button';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { type JsonValue, money, shortId } from '@/lib/api';

export const humanize = (key: string) => key.replaceAll('_', ' ');
const fullValue = (value: JsonValue) =>
  typeof value === 'string' ? value : JSON.stringify(value);
function scalar(value: JsonValue, key = ''): string {
  if (value === null) return 'Not available';
  if (typeof value === 'number')
    return key.endsWith('_minor')
      ? money(value)
      : Number.isInteger(value)
        ? value.toLocaleString()
        : value.toFixed(3);
  if (Array.isArray(value))
    return value.map((item) => scalar(item, key)).join(', ');
  if (typeof value === 'object') return JSON.stringify(value);
  if (key.endsWith('_id') || key.endsWith('_ids'))
    return shortId(String(value));
  return String(value);
}
export function EvidenceValue({ value }: { value: JsonValue }) {
  const [page, setPage] = useState(0);
  if (Array.isArray(value)) {
    if (!value.length)
      return (
        <p className="empty-evidence">
          No matching evidence in this snapshot. Absence is not proof of
          legitimacy.
        </p>
      );
    const records = value.filter(
      (item): item is Record<string, JsonValue> =>
        item !== null && typeof item === 'object' && !Array.isArray(item),
    );
    if (records.length === value.length) {
      const keys = Object.keys(records[0]);
      return (
        <div className="evidence-table">
          <Table>
            <TableHeader>
              <TableRow>
                {keys.map((key) => (
                  <TableHead key={key}>
                    {humanize(key.replace('_minor', ' (INR)'))}
                  </TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {records.slice(page * 25, page * 25 + 25).map((record, index) => (
                <TableRow key={index}>
                  {keys.map((key) => (
                    <TableCell key={key} title={JSON.stringify(record[key])}>
                      {key.endsWith('_id') || key.endsWith('_ids') ? (
                        <details className="evidence-id">
                          <summary>{scalar(record[key], key)}</summary>
                          <span>
                            {Array.isArray(record[key])
                              ? record[key].map(fullValue).join(', ')
                              : fullValue(record[key])}
                          </span>
                        </details>
                      ) : (
                        scalar(record[key], key)
                      )}
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {records.length > 25 && (
            <div className="list-pagination">
              <span>
                {page * 25 + 1}–{Math.min(page * 25 + 25, records.length)} of{' '}
                {records.length} rows
              </span>
              <Button
                size="sm"
                variant="outline"
                disabled={!page}
                onClick={() => setPage((n) => n - 1)}
              >
                Previous rows
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={(page + 1) * 25 >= records.length}
                onClick={() => setPage((n) => n + 1)}
              >
                Next rows
              </Button>
            </div>
          )}
        </div>
      );
    }
    return <p className="break-words">{scalar(value)}</p>;
  }
  if (value !== null && typeof value === 'object')
    return (
      <div className="evidence-object">
        {Object.entries(value).map(([key, item]) => (
          <div key={key}>
            <h4>{humanize(key.replace('_minor', ' (INR)'))}</h4>
            {typeof item === 'object' && item !== null ? (
              <EvidenceValue value={item} />
            ) : (
              <p title={String(item)}>
                {key.endsWith('_id')
                  ? String(item ?? 'Not available')
                  : scalar(item, key)}
              </p>
            )}
          </div>
        ))}
      </div>
    );
  return <p>{scalar(value)}</p>;
}
