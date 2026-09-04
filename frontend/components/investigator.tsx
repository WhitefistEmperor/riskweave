'use client';

import { useEffect, useRef, useState } from 'react';
import { Sparkles, ArrowUpRight, FileCheck2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Textarea } from '@/components/ui/textarea';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import { EvidenceValue, humanize } from '@/components/evidence-value';
import type { JsonValue } from '@/lib/api';
import { apiRequest } from '@/lib/client';
import { Failure, LoadingState } from '@/components/workspace-states';
import { object, strings } from '@/lib/response-validation';

type Answer = {
  provider: string;
  statements: { id: string; text: string; query: string; path: string }[];
  sources: { query: string; result: JsonValue }[];
  limitations: string[];
  warning: string | null;
};
const suggestions = [
  'Why was this ring flagged?',
  'Which entities connect these customers?',
  'What changed just before detection?',
  'How much financial exposure is associated with this ring?',
  'How does this differ from a legitimate hostel?',
  'Show the activity chronologically.',
];
function validAnswer(value: unknown): boolean {
  return (
    object(value) &&
    typeof value.provider === 'string' &&
    Array.isArray(value.statements) &&
    value.statements.every(
      (item) =>
        object(item) &&
        ['id', 'text', 'query', 'path'].every(
          (key) => typeof item[key] === 'string',
        ),
    ) &&
    Array.isArray(value.sources) &&
    value.sources.every(
      (item) =>
        object(item) && typeof item.query === 'string' && 'result' in item,
    ) &&
    strings(value.limitations) &&
    (value.warning === null || typeof value.warning === 'string')
  );
}

export function Investigator({
  candidateId,
  eventCount,
  runId,
}: {
  candidateId: string;
  eventCount?: number;
  runId?: string;
}) {
  const [question, setQuestion] = useState(suggestions[0]);
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [openSources, setOpenSources] = useState<string[]>([]);
  const request = useRef<AbortController | null>(null);
  const inFlight = useRef(false);
  useEffect(() => () => request.current?.abort(), []);
  async function ask() {
    if (inFlight.current || !question.trim()) return;
    inFlight.current = true;
    const controller = new AbortController();
    request.current = controller;
    setBusy(true);
    setError(null);
    setAnswer(null);
    setOpenSources([]);
    try {
      const result = await apiRequest<Answer>(
        runId
          ? `/v1/runs/${encodeURIComponent(runId)}/rings/${encodeURIComponent(candidateId)}/investigate`
          : '/investigate',
        {
          method: 'POST',
          signal: controller.signal,
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(
            runId
              ? { question }
              : {
                  candidate_id: candidateId,
                  question,
                  event_count: eventCount ?? null,
                },
          ),
        },
        validAnswer,
      );
      if (!controller.signal.aborted) setAnswer(result);
    } catch (reason: unknown) {
      if (!controller.signal.aborted) setError(reason);
    } finally {
      if (!controller.signal.aborted) setBusy(false);
      inFlight.current = false;
    }
  }
  return (
    <div className="investigator-grid">
      <Card className="panel p-5">
        <div className="flex gap-3 items-center mb-3">
          <Sparkles size={21} className="cyan" />
          <h2>Grounded investigator</h2>
        </div>
        <p className="muted text-sm mb-5">
          Ask about this exact evidence snapshot. The investigator retrieves
          controlled facts; it cannot classify fraud or invent missing evidence.
        </p>
        <label htmlFor="analyst-question" className="eyebrow">
          ANALYST QUESTION
        </label>
        <Textarea
          id="analyst-question"
          value={question}
          maxLength={1000}
          disabled={busy}
          onChange={(event) => setQuestion(event.target.value)}
          className="mt-2 min-h-28"
        />
        <Button
          onClick={() => void ask()}
          disabled={busy || !question.trim()}
          className="mt-3"
        >
          {busy ? 'Querying evidence…' : 'Ask investigator'}{' '}
          <ArrowUpRight size={15} />
        </Button>
        <p className="eyebrow mt-8 mb-3">SUGGESTED QUERIES</p>
        <div className="space-y-2">
          {suggestions.map((suggestion) => (
            <Button
              key={suggestion}
              variant="outline"
              className="suggestion-button"
              onClick={() => setQuestion(suggestion)}
              disabled={busy}
            >
              {suggestion}
            </Button>
          ))}
        </div>
      </Card>
      <Card className="panel p-5">
        <div className="flex items-center justify-between gap-3 mb-5">
          <h2>Evidence-backed response</h2>
          <FileCheck2 size={19} className="muted" />
        </div>
        <Failure error={error} />
        {busy && (
          <LoadingState label="Retrieving the selected candidate’s computed evidence…" />
        )}
        {!answer && !busy && !error && (
          <p className="muted py-10">
            {busy
              ? 'Retrieving the selected candidate’s computed evidence…'
              : 'Run a query to see cited observations and their source data.'}
          </p>
        )}
        {answer && (
          <>
            <span className="status-chip cyan">
              {answer.provider === 'openai_extractive_summary'
                ? 'OpenAI · extractive evidence summary'
                : answer.provider === 'disabled_evidence_only'
                  ? 'LLM disabled · computed evidence only'
                  : 'Deterministic evidence fallback · no LLM'}
            </span>
            <p className="muted text-sm my-4">
              Every sentence below is rendered from computed facts. The optional
              LLM selects and orders facts; it cannot add prose.
            </p>
            {answer.warning && (
              <p className="amber text-sm mb-3">{answer.warning}</p>
            )}
            <ol className="answer-statements">
              {answer.statements.map((statement) => (
                <li key={statement.id}>
                  <p>{statement.text}</p>
                  <a
                    href={`#source-${statement.query}`}
                    className="evidence-citation"
                    onClick={() =>
                      setOpenSources((current) => [
                        ...new Set([...current, statement.query]),
                      ])
                    }
                  >
                    [{statement.id}] {statement.query} · {statement.path}
                  </a>
                </li>
              ))}
            </ol>
            <div className="trust-box">
              {answer.limitations.map((text) => (
                <p key={text}>{text}</p>
              ))}
            </div>
            <Accordion
              multiple
              value={openSources}
              onValueChange={(value) => setOpenSources(value as string[])}
              className="mt-5"
            >
              {answer.sources.map((source) => (
                <AccordionItem
                  key={source.query}
                  value={source.query}
                  id={`source-${source.query}`}
                >
                  <AccordionTrigger>
                    Source: {humanize(source.query)}
                  </AccordionTrigger>
                  <AccordionContent>
                    <EvidenceValue value={source.result} />
                  </AccordionContent>
                </AccordionItem>
              ))}
            </Accordion>
          </>
        )}
      </Card>
    </div>
  );
}
