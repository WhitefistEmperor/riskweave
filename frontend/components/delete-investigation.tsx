'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  AlertDialog,
  AlertDialogTrigger,
  AlertDialogContent,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogFooter,
} from '@/components/ui/alert-dialog';
import { ApiError } from '@/lib/client';
import { platformApi, type InvestigationRecord } from '@/lib/platform-api';

export function DeleteInvestigation({
  record,
  disabled,
  onBusy,
}: {
  record: InvestigationRecord;
  disabled: boolean;
  onBusy: (value: boolean) => void;
}) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [conflict, setConflict] = useState(false);
  const inFlight = useRef(false);
  const active = useRef(true);
  useEffect(() => {
    active.current = true;
    return () => {
      active.current = false;
      onBusy(false);
    };
  }, [onBusy]);

  async function remove() {
    if (disabled || conflict || inFlight.current || name !== record.name)
      return;
    inFlight.current = true;
    setBusy(true);
    onBusy(true);
    setError('');
    let completed = false;
    try {
      const result = await platformApi.remove(
        record.id,
        name,
        record.updated_at,
      );
      completed = true;
      if (active.current)
        window.location.assign(
          `/investigations?removed=${result.storage_cleanup}`,
        );
    } catch (failure) {
      if (!active.current) return;
      if (failure instanceof ApiError && failure.status === 409)
        setConflict(true);
      setError(
        failure instanceof ApiError && failure.status === 409
          ? 'The name or investigation state changed. Reload the case before deleting; active analysis must finish first.'
          : failure instanceof ApiError && failure.status === 404
            ? 'This investigation is no longer available. Return to the investigation list to check its state.'
            : failure instanceof Error
              ? failure.message
              : 'Deletion could not be confirmed.',
      );
    } finally {
      inFlight.current = false;
      if (active.current && !completed) {
        setBusy(false);
        onBusy(false);
      }
    }
  }

  return (
    <section className="panel p-5 mt-6" aria-label="Investigation deletion">
      <h2 className="font-semibold mb-2">Delete investigation</h2>
      <p className="muted text-sm mb-3">
        Remove this case, its datasets, results, and analyst review history.
      </p>
      {disabled && (
        <p className="muted text-sm mb-3">
          Finish the current analysis or upload before deleting.
        </p>
      )}
      <AlertDialog
        open={open}
        onOpenChange={(next) => {
          if (busy) return;
          setOpen(next);
          if (!next) {
            setName('');
            if (!conflict) setError('');
          }
        }}
      >
        <AlertDialogTrigger
          render={<Button variant="outline" disabled={disabled} />}
        >
          Delete investigation
        </AlertDialogTrigger>
        <AlertDialogContent>
          <AlertDialogTitle>Delete this investigation?</AlertDialogTitle>
          <AlertDialogDescription>
            This permanently removes the saved case and all its review notes
            from the workspace. Existing exported copies and retained backups
            are handled separately by your operator.
          </AlertDialogDescription>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void remove();
            }}
            className="grid gap-3"
          >
            <label htmlFor={`delete-name-${record.id}`}>
              Type the investigation name
            </label>
            <p className="font-medium break-words">{record.name}</p>
            <Input
              id={`delete-name-${record.id}`}
              value={name}
              maxLength={120}
              required
              disabled={busy}
              autoComplete="off"
              onChange={(event) => setName(event.target.value)}
            />
            {error && <p role="alert">{error}</p>}
            {conflict && (
              <Button
                type="button"
                variant="outline"
                onClick={() => window.location.reload()}
              >
                Reload case
              </Button>
            )}
            {error && (
              <Link href="/investigations" className="underline">
                Check investigation list
              </Link>
            )}
            <AlertDialogFooter>
              <Button
                type="button"
                variant="outline"
                disabled={busy}
                onClick={() => {
                  setOpen(false);
                  setName('');
                  if (!conflict) setError('');
                }}
              >
                Keep investigation
              </Button>
              <Button
                type="submit"
                variant="destructive"
                disabled={disabled || busy || conflict || name !== record.name}
              >
                {busy ? 'Deleting…' : 'Permanently delete'}
              </Button>
            </AlertDialogFooter>
          </form>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  );
}
