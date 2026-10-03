'use client';

import { useEffect, useRef, useState } from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { ApiError } from '@/lib/client';
import {
  platformApi,
  type CandidateReview,
  type ReviewDisposition,
  type ReviewUpdate,
} from '@/lib/platform-api';

const labels: Record<ReviewDisposition, string> = {
  unreviewed: 'Unreviewed',
  investigating: 'Investigating',
  escalated: 'Escalated',
  dismissed: 'Dismissed',
};

export function CandidateReviewPanel({
  runId,
  candidateId,
}: {
  runId: string;
  candidateId: string;
}) {
  const [review, setReview] = useState<CandidateReview | null>(null);
  const [disposition, setDisposition] =
    useState<ReviewDisposition>('unreviewed');
  const [note, setNote] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [conflict, setConflict] = useState(false);
  const pending = useRef<{ key: string; body: ReviewUpdate } | null>(null);
  const active = useRef(true);
  useEffect(() => {
    active.current = true;
    const controller = new AbortController();
    platformApi
      .review(runId, candidateId, controller.signal)
      .then((value) => {
        if (controller.signal.aborted) return;
        setReview(value);
        setDisposition(value.disposition);
      })
      .catch((failure: unknown) => {
        if (!controller.signal.aborted)
          setError(
            failure instanceof Error ? failure.message : 'Review unavailable.',
          );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => {
      active.current = false;
      controller.abort();
    };
  }, [runId, candidateId]);

  async function reload() {
    setLoading(true);
    setError('');
    try {
      const latest = await platformApi.review(runId, candidateId);
      if (!active.current) return;
      setReview(latest);
      if (!review) setDisposition(latest.disposition);
      setConflict(false);
      pending.current = null;
      setNotice(
        'Latest review loaded. Your unsaved note is preserved; compare the history before saving.',
      );
    } catch (failure) {
      if (active.current)
        setError(
          failure instanceof Error ? failure.message : 'Review unavailable.',
        );
    } finally {
      if (active.current) setLoading(false);
    }
  }

  async function save() {
    if (!review || !note.trim() || saving || conflict) return;
    setSaving(true);
    setError('');
    setNotice('');
    pending.current ??= {
      key: crypto.randomUUID(),
      body: {
        disposition,
        note: note.trim(),
        expected_version: review.version,
      },
    };
    try {
      const latest = await platformApi.saveReview(
        runId,
        candidateId,
        pending.current.body,
        pending.current.key,
      );
      if (!active.current) return;
      setReview(latest);
      setDisposition(latest.disposition);
      setNote('');
      pending.current = null;
      setNotice('Review saved to the audit history.');
    } catch (failure) {
      if (!active.current) return;
      if (failure instanceof ApiError && failure.status === 409) {
        setConflict(true);
        pending.current = null;
        setError(
          'This review changed since you opened it. Reload the latest history before saving your note.',
        );
      } else
        setError(
          failure instanceof Error
            ? failure.message
            : 'Review could not be saved.',
        );
    } finally {
      if (active.current) setSaving(false);
    }
  }

  return (
    <Card className="panel p-5" aria-label="Analyst review">
      <h3 className="font-semibold">Analyst review</h3>
      <p className="muted text-sm my-2">
        Record your assessment separately from model evidence. A disposition
        does not establish fraud.
      </p>
      {loading && <p aria-live="polite">Loading review…</p>}
      {review && (
        <p className="text-sm mb-4">
          Saved status: <strong>{labels[review.disposition]}</strong> · Revision{' '}
          {review.version}
        </p>
      )}
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void save();
        }}
        className="grid gap-3"
      >
        <label htmlFor={`review-status-${candidateId}`}>Review status</label>
        <select
          id={`review-status-${candidateId}`}
          className="rounded border p-2"
          value={disposition}
          disabled={loading || saving || !review}
          onChange={(event) => {
            setDisposition(event.target.value as ReviewDisposition);
            pending.current = null;
          }}
        >
          {Object.entries(labels).map(([value, label]) => (
            <option value={value} key={value}>
              {label}
            </option>
          ))}
        </select>
        <label htmlFor={`review-note-${candidateId}`}>Review note</label>
        <Textarea
          id={`review-note-${candidateId}`}
          value={note}
          maxLength={2000}
          required
          disabled={loading || saving || !review}
          placeholder="Record observed evidence, your reasoning, and next steps."
          onChange={(event) => {
            setNote(event.target.value);
            pending.current = null;
          }}
        />
        <p className="muted text-xs">
          {note.length}/2000 characters. Notes are retained in the audit
          history; avoid unnecessary personal data.
        </p>
        <div className="flex flex-wrap gap-2">
          <Button
            type="submit"
            disabled={!review || loading || saving || conflict || !note.trim()}
          >
            {saving ? 'Saving review…' : 'Save review'}
          </Button>
          {error && (
            <Button
              type="button"
              variant="outline"
              disabled={loading || saving}
              onClick={() => void reload()}
            >
              Reload review
            </Button>
          )}
        </div>
      </form>
      {error && (
        <p role="alert" className="mt-3">
          {error}
        </p>
      )}
      {notice && <output className="block mt-3">{notice}</output>}
      <details className="mt-5">
        <summary>Review history ({review?.history.length ?? 0})</summary>
        {review && !review.history.length && (
          <p className="muted mt-2">No analyst decisions recorded.</p>
        )}
        <ol className="grid gap-4 mt-4">
          {review?.history
            .slice()
            .reverse()
            .map((entry) => (
              <li key={entry.id} className="border-t pt-3">
                <p className="text-sm">
                  <strong>
                    Revision {entry.version}: {labels[entry.disposition]}
                  </strong>{' '}
                  · {new Date(entry.created_at).toLocaleString()}
                </p>
                <p className="muted text-xs break-all">
                  Analyst {entry.actor_id} · Previously{' '}
                  {labels[entry.previous_disposition]}
                </p>
                <p className="whitespace-pre-wrap break-words mt-2">
                  {entry.note}
                </p>
              </li>
            ))}
        </ol>
      </details>
    </Card>
  );
}
