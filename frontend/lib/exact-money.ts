import { isLosslessNumber, LosslessNumber, parse } from 'lossless-json';

/** New APIs use decimal strings; safe legacy JSON integers remain compatible. */
export type MinorAmount = string | number;
export const validMinorAmount = (value: unknown): value is MinorAmount =>
  (typeof value === 'string' && /^(0|[1-9][0-9]*)$/.test(value)) ||
  (typeof value === 'number' && Number.isSafeInteger(value) && value >= 0);

/** Preserve unsafe integer tokens before validation, including immutable old results. */
export function parseExactJson(text: string): unknown {
  return parse(
    text,
    (key, value) => {
      if (!isLosslessNumber(value)) return value;
      const token = value.value;
      // Money must retain its source token even if a fractional value rounds to
      // an integer. Contract validation then rejects noncanonical amounts.
      if (
        [
          'amount_minor',
          'estimated_exposure_minor',
          'refund_amount_minor',
          'total_amount_minor',
        ].includes(key)
      )
        return token;
      const number = Number(token);
      return /^-?[0-9]+$/.test(token) && !Number.isSafeInteger(number)
        ? token
        : number;
    },
    {
      parseNumber: (token) => new LosslessNumber(token),
    },
  );
}
