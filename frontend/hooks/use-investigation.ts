'use client';

import { useEffect, useRef, useState } from 'react';
import { ApiError } from '@/lib/client';
import type { UploadProgress } from '@/lib/upload-transport';
import {
  platformApi,
  pollRun,
  type InvestigationRecord,
  type ArtifactRecord,
  type AnalysisRun,
  type AnalysisResult,
} from '@/lib/platform-api';

export function useInvestigation(
  investigationId: string,
  initialRunId?: string,
) {
  const [record, setRecord] = useState<InvestigationRecord | null>(null);
  const [artifacts, setArtifacts] = useState<ArtifactRecord[]>([]);
  const [artifactId, setArtifactId] = useState('');
  const [runs, setRuns] = useState<AnalysisRun[]>([]);
  const [runId, setRunId] = useState(initialRunId ?? '');
  const [run, setRun] = useState<AnalysisRun | null>(null);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState<'upload' | 'discard' | 'start' | null>(null);
  const [uploadStage, setUploadStage] = useState<UploadProgress | null>(null);
  const [attempt, setAttempt] = useState(0);
  const pendingStart = useRef<{ artifactId: string; key: string } | null>(null);
  const pendingUpload = useRef<{
    name: string;
    size: number;
    modified: number;
    key: string;
  } | null>(null);
  const inFlight = useRef(false);
  const upsertRun = (value: AnalysisRun) =>
    setRuns((history) =>
      [...history.filter((item) => item.id !== value.id), value].sort((a, b) =>
        a.created_at.localeCompare(b.created_at),
      ),
    );

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      platformApi.investigation(investigationId, controller.signal),
      platformApi.artifacts(investigationId, controller.signal),
      platformApi.runs(investigationId, controller.signal),
      platformApi.pendingUploads(investigationId, controller.signal),
    ])
      .then(([item, files, history, uploads]) => {
        if (controller.signal.aborted) return;
        setRecord(item);
        setUploadStage(uploads[0] ?? null);
        setArtifacts(files);
        setArtifactId((current) => current || files.at(-1)?.id || '');
        const sorted = [...history].sort((a, b) =>
          a.created_at.localeCompare(b.created_at),
        );
        setRuns(sorted);
        setRunId((current) => current || sorted.at(-1)?.id || '');
      })
      .catch((reason) => {
        if (!controller.signal.aborted) setError(reason);
      });
    return () => controller.abort();
  }, [investigationId, attempt]);

  useEffect(() => {
    if (!runId) return;
    const controller = new AbortController();
    pollRun(
      runId,
      (value) => {
        if (value.investigation_id !== investigationId)
          throw new Error(
            'This run belongs to a different investigation. Open a run from this investigation’s history.',
          );
        setRun(value);
        upsertRun(value);
      },
      controller.signal,
    )
      .then(async (terminal) => {
        if (controller.signal.aborted || terminal?.status !== 'completed')
          return;
        const value = await platformApi.results(
          runId,
          controller.signal,
          terminal,
        );
        if (!controller.signal.aborted) setResult(value);
      })
      .catch((reason) => {
        if (!controller.signal.aborted) setError(reason);
      });
    return () => controller.abort();
  }, [runId, investigationId, attempt]);

  function selectRun(value: string, writeUrl = true) {
    if (value !== runId) {
      setRun(null);
      setResult(null);
      setRunId(value);
    }
    setError(null);
    if (writeUrl) {
      const url = new URL(window.location.href);
      url.search = '';
      url.searchParams.set('run', value);
      window.history.pushState(null, '', url);
      window.dispatchEvent(new Event('ringsentinel:navigation'));
    }
  }
  useEffect(() => {
    const sync = () => {
      const value =
        new URL(window.location.href).searchParams.get('run') ??
        initialRunId ??
        '';
      setRunId((current) => {
        if (current !== value) {
          setRun(null);
          setResult(null);
          setError(null);
        }
        return value;
      });
    };
    window.addEventListener('popstate', sync);
    return () => window.removeEventListener('popstate', sync);
  }, [initialRunId]);

  async function upload(file: File) {
    if (inFlight.current) return;
    inFlight.current = true;
    setBusy('upload');
    setError(null);
    let terminalConflict = false;
    if (
      !pendingUpload.current ||
      pendingUpload.current.name !== file.name ||
      pendingUpload.current.size !== file.size ||
      pendingUpload.current.modified !== file.lastModified
    ) {
      pendingUpload.current = {
        name: file.name,
        size: file.size,
        modified: file.lastModified,
        key: crypto.randomUUID(),
      };
    }
    try {
      const item = await platformApi.upload(
        investigationId,
        file,
        pendingUpload.current.key,
        (progress) =>
          setUploadStage(progress.status === 'pending' ? progress : null),
      );
      pendingUpload.current = null;
      setUploadStage(null);
      setArtifacts((items) => [
        ...items.filter((value) => value.id !== item.id),
        item,
      ]);
      setArtifactId(item.id);
    } catch (reason) {
      terminalConflict =
        reason instanceof ApiError && reason.code === 'CONFLICT';
      if (
        reason instanceof ApiError &&
        ['INVALID_DATASET', 'UPLOAD_TOO_LARGE', 'VALIDATION_ERROR'].includes(
          reason.code,
        )
      )
        pendingUpload.current = null;
      setError(reason);
    } finally {
      const remainingStage = await refreshUpload();
      if (terminalConflict && remainingStage === null)
        pendingUpload.current = null;
      inFlight.current = false;
      setBusy(null);
    }
  }
  async function refreshUpload() {
    try {
      const [item, uploads] = await Promise.all([
        platformApi.investigation(investigationId),
        platformApi.pendingUploads(investigationId),
      ]);
      setRecord(item);
      setUploadStage(uploads[0] ?? null);
      return uploads[0] ?? null;
    } catch (reason) {
      // Preserve the original upload error; the Retry control reloads server state.
      setError((current: unknown) => current ?? reason);
    }
  }
  async function discardUpload() {
    if (!uploadStage || inFlight.current) return;
    inFlight.current = true;
    setBusy('discard');
    setError(null);
    try {
      await platformApi.cancelUpload(investigationId, uploadStage.id);
      pendingUpload.current = null;
      setUploadStage(null);
    } catch (reason) {
      setError(reason);
    } finally {
      await refreshUpload();
      inFlight.current = false;
      setBusy(null);
    }
  }
  async function start() {
    if (
      !artifactId ||
      inFlight.current ||
      uploadStage ||
      record?.status === 'uploading'
    )
      return;
    inFlight.current = true;
    setBusy('start');
    setError(null);
    // Retry ambiguous transport failures with the SAME key, never an automatic new POST.
    if (pendingStart.current?.artifactId !== artifactId)
      pendingStart.current = { artifactId, key: crypto.randomUUID() };
    try {
      const value = await platformApi.start(
        investigationId,
        artifactId,
        pendingStart.current.key,
      );
      pendingStart.current = null;
      selectRun(value.id);
      setRun(value);
      upsertRun(value);
    } catch (reason) {
      setError(reason);
    } finally {
      inFlight.current = false;
      setBusy(null);
    }
  }
  const activeRun =
    runs.some(
      (item) => item.status === 'queued' || item.status === 'running',
    ) ||
    run?.status === 'queued' ||
    run?.status === 'running';
  return {
    record,
    artifacts,
    artifactId,
    setArtifactId,
    runs,
    runId,
    run,
    result,
    error,
    busy,
    activeRun,
    selectRun,
    upload,
    uploadStage,
    discardUpload,
    start,
    retry: () => {
      setError(null);
      setAttempt((n) => n + 1);
    },
  };
}
