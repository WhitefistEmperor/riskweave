'use client';

import { useEffect, useRef } from 'react';
import { flushSync } from 'react-dom';

type Screen = 'overview' | 'explorer' | 'benchmark' | 'hard-negatives';
type Action = 'start' | 'pause' | 'step' | 'reset';
type State = {
  screen: Screen;
  timestamp: string | null;
  observedEvents: number;
  candidateId: string | null;
  running: boolean;
};
type Tool = {
  name: string;
  description: string;
  inputSchema: object;
  annotations: { readOnlyHint: boolean };
  execute: (input: unknown) => unknown;
};
type ModelContext = {
  registerTool: (
    tool: Tool,
    options: { signal: AbortSignal },
  ) => void | Promise<void>;
};

export function useConsoleTools(
  state: State,
  navigate: (screen: Screen) => void,
  control: (action: Action) => void,
) {
  const latest = useRef({ state, navigate, control });
  useEffect(() => {
    latest.current = { state, navigate, control };
  }, [state, navigate, control]);
  useEffect(() => {
    const context = (document as Document & { modelContext?: ModelContext })
      .modelContext;
    if (!context?.registerTool) return;
    const lifecycle = new AbortController();
    const register = (tool: Tool) => {
      try {
        void Promise.resolve(
          context.registerTool(tool, { signal: lifecycle.signal }),
        ).catch(() => {
          /* Optional browser capability; visible UI remains available. */
        });
      } catch {
        /* Unsupported implementation must not break the console. */
      }
    };
    register({
      name: 'read_ring_console',
      description:
        'Read the visible workspace and observed replay position. No future candidate information.',
      inputSchema: {
        type: 'object',
        properties: {},
        additionalProperties: false,
      },
      annotations: { readOnlyHint: true },
      execute: () => latest.current.state,
    });
    register({
      name: 'navigate_ring_workspace',
      description:
        'Open a workspace. Explorer opens completed-ecosystem review, not the live replay snapshot.',
      inputSchema: {
        type: 'object',
        properties: {
          screen: {
            type: 'string',
            enum: ['overview', 'explorer', 'benchmark', 'hard-negatives'],
          },
        },
        required: ['screen'],
        additionalProperties: false,
      },
      annotations: { readOnlyHint: false },
      execute: (input) => {
        const screen = (input as { screen?: string } | null)?.screen;
        if (
          !screen ||
          !['overview', 'explorer', 'benchmark', 'hard-negatives'].includes(
            screen,
          )
        )
          throw new Error('Invalid workspace');
        flushSync(() => latest.current.navigate(screen as Screen));
        return { screen, status: 'workspace_opened' };
      },
    });
    register({
      name: 'control_ring_replay',
      description:
        'Start, pause, step, or reset the same local replay shown in the overview.',
      inputSchema: {
        type: 'object',
        properties: {
          action: { type: 'string', enum: ['start', 'pause', 'step', 'reset'] },
        },
        required: ['action'],
        additionalProperties: false,
      },
      annotations: { readOnlyHint: false },
      execute: (input) => {
        const action = (input as { action?: string } | null)?.action;
        if (!action || !['start', 'pause', 'step', 'reset'].includes(action))
          throw new Error('Invalid replay action');
        if (!latest.current.state.timestamp)
          throw new Error('Replay is still loading');
        flushSync(() => latest.current.control(action as Action));
        return { action, status: 'applied' };
      },
    });
    return () => lifecycle.abort();
  }, []);
}
