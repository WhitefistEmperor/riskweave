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
              {records.map((record, index) => (
                <TableRow key={index}>
                  {keys.map((key) => (
                    <TableCell key={key} title={JSON.stringify(record[key])}>
                      {scalar(record[key], key)}
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
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
              <p title={String(item)}>{scalar(item, key)}</p>
            )}
          </div>
        ))}
      </div>
    );
  return <p>{scalar(value)}</p>;
}
