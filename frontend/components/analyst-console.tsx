'use client';

import { useEffect, useState, type ReactNode } from 'react';
import Link from 'next/link';
import { RingExplorer } from '@/components/ring-explorer';
import { BenchmarkView } from '@/components/benchmark-view';
import { HardNegatives } from '@/components/hard-negatives';
import { useConsoleTools } from '@/hooks/use-console-tools';
import { Line, LineChart, ReferenceLine, YAxis } from 'recharts';
import { ChartContainer } from '@/components/ui/chart';
import {
  Activity,
  ArrowRight,
  CircleHelp,
  FlaskConical,
  GitFork,
  LayoutDashboard,
  Network,
  Pause,
  Play,
  RotateCcw,
  ShieldCheck,
  SkipForward,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyTitle,
} from '@/components/ui/empty';
import { Progress } from '@/components/ui/progress';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarTrigger,
  useSidebar,
} from '@/components/ui/sidebar';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  clock,
  dateTime,
  loadConsoleData,
  money,
  shortId,
  type ConsoleData,
} from '@/lib/api';

type Screen = 'overview' | 'explorer' | 'benchmark' | 'hard-negatives';
const navigation = [
  { id: 'overview', label: 'Overview', icon: LayoutDashboard },
  { id: 'explorer', label: 'Ring Explorer', icon: Network },
  { id: 'benchmark', label: 'Benchmark', icon: FlaskConical },
  { id: 'hard-negatives', label: 'Hard negatives', icon: ShieldCheck },
] as const;

export function AnalystConsole() {
  const [data, setData] = useState<ConsoleData | null>(null);
  const [error, setError] = useState('');
  const [screen, setScreen] = useState<Screen>('overview');
  const [explorerPrefix, setExplorerPrefix] = useState<number | undefined>();
  const [explorerCandidate, setExplorerCandidate] = useState<
    string | undefined
  >();
  const [cursor, setCursor] = useState(0);
  const [running, setRunning] = useState(false);
  const [speed, setSpeed] = useState('1');
  useEffect(() => {
    let active = true;
    loadConsoleData()
      .then((result) => {
        if (active) setData(result);
      })
      .catch((reason: unknown) => {
        if (active) setError(String(reason));
      });
    return () => {
      active = false;
    };
  }, []);
  useEffect(() => {
    if (!running || !data) return;
    const timer = window.setInterval(
      () => {
        setCursor((position) =>
          Math.min(position + 1, data.simulation.events.length - 1),
        );
      },
      550 / Number(speed),
    );
    return () => window.clearInterval(timer);
  }, [data, running, speed]);
  const current = data?.simulation.events[cursor];
  const atEnd = data ? cursor === data.simulation.events.length - 1 : false;
  const live = current?.candidate_state;
  useConsoleTools(
    {
      screen,
      timestamp: current?.timestamp ?? null,
      observedEvents: current?.observed_event_count ?? 0,
      candidateId: live?.candidate_id ?? null,
      running: running && !atEnd,
    },
    (nextScreen) => {
      setExplorerPrefix(undefined);
      setExplorerCandidate(undefined);
      setScreen(nextScreen);
    },
    (action) => {
      if (action === 'reset') {
        setRunning(false);
        setCursor(0);
      }
      if (action === 'pause') setRunning(false);
      if (action === 'start') {
        if (atEnd) setCursor(0);
        setRunning(true);
      }
      if (action === 'step') {
        setRunning(false);
        setCursor(
          Math.min(cursor + 1, (data?.simulation.events.length ?? 1) - 1),
        );
      }
    },
  );
  const attackActive = Boolean(
    current &&
    data &&
    current.timestamp >= data.simulation.attack_start_timestamp,
  );
  const feed =
    data?.simulation.events
      .slice(Math.max(0, cursor - 11), cursor + 1)
      .toReversed() ?? [];
  const plotted =
    data?.simulation.events.slice(Math.max(0, cursor - 35), cursor + 1) ?? [];

  return (
    <SidebarProvider>
      <Sidebar className="console-sidebar">
        <SidebarHeader className="brand">
          <div className="brand-icon">
            <GitFork size={23} />
          </div>
          <div>
            <strong>RiskWeave</strong>
            <span>NETWORK RISK INTELLIGENCE</span>
          </div>
        </SidebarHeader>
        <SidebarContent className="px-4 py-7">
          <p className="eyebrow px-3 mb-4">Workspace</p>
          <SidebarMenu>
            {navigation.map(({ id, label, icon: Icon }) => (
              <SidebarMenuItem key={id}>
                <WorkspaceButton
                  active={screen === id}
                  onClick={() => {
                    setExplorerPrefix(undefined);
                    setExplorerCandidate(undefined);
                    setScreen(id);
                  }}
                >
                  <Icon />
                  <span>{label}</span>
                </WorkspaceButton>
              </SidebarMenuItem>
            ))}
            <SidebarMenuItem>
              <SidebarMenuButton
                render={
                  <Link href="/investigations" aria-label="Investigations" />
                }
              >
                <GitFork />
                <span>Investigations</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
          <div className="sidebar-note">
            <Activity size={16} />
            <span>
              SEED 105 · LOCAL REPLAY
              <br />
              <small>Deterministic synthetic ecosystem</small>
            </span>
          </div>
        </SidebarContent>
        <SidebarFooter className="p-5">
          <div className="trust-note">
            <CircleHelp size={16} />
            <p>Decision support, not an automated fraud verdict.</p>
          </div>
          <div className="sidebar-version">
            PHASE 4 <span>Evidence-first</span>
          </div>
        </SidebarFooter>
      </Sidebar>
      <SidebarInset>
        <header className="topbar">
          <div className="flex items-center gap-3">
            <SidebarTrigger />
            <span>
              Risk operations{' '}
              <span className="muted">
                / {navigation.find((item) => item.id === screen)?.label}
              </span>
            </span>
          </div>
          <span className="demo-badge">
            <span /> DEMO MODE · SYNTHETIC
          </span>
        </header>
        <main className="console-main">
          {!data ? (
            <>
              <div className="page-heading">
                <p className="eyebrow">RISKWEAVE WORKSPACE</p>
                <h1>
                  {error
                    ? 'Backend connection unavailable'
                    : 'Preparing the evidence workspace'}
                </h1>
                <p className="muted">
                  {error
                    ? 'Start the Python service with uv run ringsentinel-api, then retry.'
                    : 'Reproducing the held-out seed 105 model. First startup may take around 20 seconds.'}
                </p>
              </div>
              {error ? (
                <Card className="panel p-6">
                  <p>{error}</p>
                  <Button onClick={() => window.location.reload()}>
                    Retry connection
                  </Button>
                </Card>
              ) : (
                <div className="metrics-grid">
                  {[1, 2, 3, 4].map((id) => (
                    <Skeleton key={id} className="h-32" />
                  ))}
                </div>
              )}
            </>
          ) : screen === 'explorer' ? (
            <RingExplorer
              key={`${explorerPrefix ?? 'full'}-${explorerCandidate ?? 'default'}`}
              eventCount={explorerPrefix}
              initialCandidate={explorerCandidate}
              onBack={() => setScreen('overview')}
            />
          ) : screen === 'benchmark' ? (
            <BenchmarkView benchmark={data.benchmark} />
          ) : screen === 'hard-negatives' ? (
            <HardNegatives />
          ) : (
            <>
              <div className="page-heading">
                <div>
                  <p className="eyebrow">PAYMENT NETWORK MONITORING</p>
                  <h1>See the ring. Not just the transaction.</h1>
                  <p className="muted">
                    A chronological demonstration window: ordinary activity to
                    connected evidence. Original UTC event timestamps are
                    preserved.
                  </p>
                </div>
                <div className="clock-block">
                  <span className="eyebrow">REPLAY CLOCK · UTC</span>
                  <strong>{current ? dateTime(current.timestamp) : '—'}</strong>
                </div>
              </div>
              <div className="metrics-grid">
                <Metric
                  label="Ecosystem entities"
                  value={data.overview.monitored_entities.toLocaleString()}
                  detail="Full generated population"
                />
                <Metric
                  label="Events observed"
                  value={(current?.observed_event_count ?? 0).toLocaleString()}
                  detail={`of ${data.overview.monitored_events.toLocaleString()} total events`}
                />
                <Metric
                  label="Focus candidate rings"
                  value={live ? '1' : '0'}
                  detail={
                    live
                      ? `${live.customers} linked customers · review required`
                      : 'Awaiting sufficient connected evidence'
                  }
                  accent={Boolean(live)}
                />
                <Metric
                  label="Candidate exposure"
                  value={money(live?.estimated_exposure_minor ?? 0)}
                  detail="Observed gross exposure · not expected loss"
                  accent={Boolean(live)}
                />
              </div>
              <p className="replay-disclosure">
                Earlier history: an isolated event crossed threshold at{' '}
                {dateTime(data.simulation.earlier_isolated_alert_timestamp)}{' '}
                UTC, but did not form a candidate. This compact window begins
                later. The eight-minute result describes the first matched focus
                ring, not average performance.
              </p>
              <div className="workspace-grid">
                <div className="space-y-5">
                  <Card className="panel simulation-panel">
                    <div className="panel-heading">
                      <div>
                        <p className="eyebrow">LIVE SIMULATION</p>
                        <h2>Relationships change the picture</h2>
                      </div>
                      <span
                        className={`status-chip ${running && !atEnd ? 'cyan' : ''}`}
                      >
                        {atEnd
                          ? 'Replay complete'
                          : running
                            ? 'Replaying'
                            : 'Paused'}
                      </span>
                    </div>
                    <div className="replay-controls">
                      <Button
                        onClick={() => {
                          if (atEnd) setCursor(0);
                          setRunning(!running || atEnd);
                        }}
                      >
                        <span>
                          {running && !atEnd ? (
                            <Pause size={15} />
                          ) : (
                            <Play size={15} />
                          )}
                        </span>
                        {running && !atEnd ? 'Pause' : 'Start replay'}
                      </Button>
                      <Button
                        variant="outline"
                        onClick={() => {
                          setRunning(false);
                          setCursor(
                            Math.min(
                              cursor + 1,
                              data.simulation.events.length - 1,
                            ),
                          );
                        }}
                        disabled={atEnd}
                      >
                        <SkipForward size={15} /> Step
                      </Button>
                      <Button
                        variant="ghost"
                        onClick={() => {
                          setRunning(false);
                          setCursor(0);
                        }}
                      >
                        <RotateCcw size={15} /> Reset
                      </Button>
                      <Select
                        value={speed}
                        onValueChange={(value) => {
                          if (value) setSpeed(value);
                        }}
                      >
                        <SelectTrigger
                          aria-label="Replay speed"
                          className="ml-auto w-24"
                        >
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {['1', '2', '4'].map((value) => (
                            <SelectItem key={value} value={value}>
                              {value}× speed
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="replay-progress">
                      <Progress
                        value={
                          ((cursor + 1) / data.simulation.events.length) * 100
                        }
                      />
                      <span>
                        {cursor + 1} / {data.simulation.events.length} window
                        events
                      </span>
                    </div>
                    <div className="stage-track">
                      <div className="active">
                        <span>01</span>
                        <strong>Ordinary activity</strong>
                        <small>Individual transactions</small>
                      </div>
                      <div className={attackActive ? 'active' : ''}>
                        <span>02</span>
                        <strong>Connections accumulate</strong>
                        <small>Activation: labeled demo truth</small>
                      </div>
                      <div className={live ? 'alert' : ''}>
                        <span>03</span>
                        <strong>Candidate appears</strong>
                        <small>
                          {live
                            ? `${data.simulation.detection_delay_minutes} min after activation`
                            : 'Minimum connected evidence'}
                        </small>
                      </div>
                    </div>
                    <div className="signal-heading">
                      <span>
                        Activation (demo truth):{' '}
                        {clock(data.simulation.attack_start_timestamp)} UTC
                      </span>
                      <span>
                        First focus alert:{' '}
                        {live
                          ? `${clock(data.simulation.first_alert_timestamp)} UTC · ${data.simulation.detection_delay_minutes} min`
                          : 'Not observed yet'}
                      </span>
                    </div>
                    <div className="signal-heading mt-4">
                      <span>
                        Event risk score <small>uncalibrated</small>
                      </span>
                      <strong>{current?.risk_score.toFixed(3)}</strong>
                    </div>
                    <ChartContainer
                      className="risk-chart"
                      config={{
                        risk_score: { label: 'Risk score', color: '#0f766e' },
                      }}
                      aria-label="Observed event risk scores with detection threshold"
                    >
                      <LineChart data={plotted}>
                        <YAxis domain={[0, 1]} hide />
                        <ReferenceLine
                          y={data.simulation.threshold}
                          stroke="#9a5b0a"
                          strokeDasharray="5 5"
                        />
                        <Line
                          dataKey="risk_score"
                          stroke="var(--color-risk_score)"
                          strokeWidth={2}
                          dot={false}
                          isAnimationActive={false}
                        />
                      </LineChart>
                    </ChartContainer>
                    <div className="chart-caption">
                      <span>
                        Last {plotted.length} observed events · chronological
                      </span>
                      <span>
                        Threshold {data.simulation.threshold.toFixed(2)}
                      </span>
                    </div>
                  </Card>
                  <Card className="panel">
                    <div className="panel-heading">
                      <h2>Payment stream</h2>
                      <span className="muted text-sm">
                        Newest observed first · UTC
                      </span>
                    </div>
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Time</TableHead>
                          <TableHead>Customer → Merchant</TableHead>
                          <TableHead>Amount</TableHead>
                          <TableHead>Risk score</TableHead>
                          <TableHead>Signal</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {feed.map((event) => (
                          <TableRow key={event.event_id}>
                            <TableCell className="mono">
                              {clock(event.timestamp)}
                            </TableCell>
                            <TableCell className="mono">
                              {shortId(event.customer_id)}{' '}
                              <span className="muted">→</span>{' '}
                              {shortId(event.merchant_id)}
                            </TableCell>
                            <TableCell>
                              {money(event.amount_minor)}
                              {event.event_type === 'REFUND' && (
                                <small className="amber block">Refund</small>
                              )}
                            </TableCell>
                            <TableCell className="mono">
                              {event.risk_score.toFixed(3)}
                            </TableCell>
                            <TableCell>
                              <span
                                className={`status-chip ${event.threshold_crossed ? 'amber' : ''}`}
                              >
                                {event.threshold_crossed
                                  ? 'Above threshold'
                                  : 'Below threshold'}
                              </span>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </Card>
                </div>
                <div className="space-y-5">
                  <Card
                    className={`panel candidate-panel ${live ? 'detected' : ''}`}
                  >
                    <div className="panel-heading">
                      <h2>Candidate watch</h2>
                      <Network size={19} />
                    </div>
                    {live ? (
                      <div className="p-5 space-y-5">
                        <span className="status-chip amber">
                          CONNECTED EVIDENCE DETECTED
                        </span>
                        <h3>
                          Coordinated activity
                          <br />
                          worth investigating
                        </h3>
                        <p className="mono muted">
                          {shortId(live.candidate_id)}
                        </p>
                        <div className="candidate-stats">
                          <div>
                            <strong>{live.customers}</strong>
                            <span>customers</span>
                          </div>
                          <div>
                            <strong>{live.events}</strong>
                            <span>linked events</span>
                          </div>
                          <div>
                            <strong>{live.risk_score.toFixed(2)}</strong>
                            <span>risk score</span>
                          </div>
                        </div>
                        <p className="muted text-sm">
                          A candidate is a review hypothesis, not a confirmed
                          fraud ring. Only observed prefix evidence is shown
                          here.
                        </p>
                        <Button
                          className="w-full"
                          onClick={() => {
                            setRunning(false);
                            setExplorerPrefix(current?.observed_event_count);
                            setExplorerCandidate(live.candidate_id);
                            setScreen('explorer');
                          }}
                        >
                          Open Ring Explorer <ArrowRight size={16} />
                        </Button>
                      </div>
                    ) : (
                      <Empty className="py-12">
                        <EmptyHeader>
                          <Network
                            className="mx-auto mb-3 text-muted-foreground"
                            size={34}
                          />
                          <EmptyTitle>No focus candidate yet</EmptyTitle>
                          <EmptyDescription>
                            Run the stream to watch shared relationships
                            accumulate into a reviewable ring.
                          </EmptyDescription>
                        </EmptyHeader>
                      </Empty>
                    )}
                  </Card>
                  <Card className="panel p-5">
                    <p className="eyebrow">WHY THE NETWORK MATTERS</p>
                    <h2>Same events. More context.</h2>
                    <p className="muted text-sm">
                      Measured Phase 3 PR-AUC · five held-out synthetic seeds
                    </p>
                    {['transaction_hgb', 'network_aware_hgb'].map((name) => (
                      <div key={name} className="benchmark-bar">
                        <div>
                          <span>
                            {name === 'transaction_hgb'
                              ? 'Transaction only'
                              : 'Network aware'}
                          </span>
                          <strong>
                            {data.benchmark.models[name]?.pr_auc.mean.toFixed(
                              3,
                            )}
                          </strong>
                        </div>
                        <Progress
                          value={
                            (data.benchmark.models[name]?.pr_auc.mean ?? 0) *
                            100
                          }
                        />
                      </div>
                    ))}
                    <Table className="mt-4">
                      <TableHeader>
                        <TableRow>
                          <TableHead>Metric</TableHead>
                          <TableHead>Txn</TableHead>
                          <TableHead>Network</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {[
                          ['recall', 'Recall'],
                          ['f1', 'F1'],
                          ['ring_detection_rate', 'Ring detection'],
                        ].map(([key, label]) => (
                          <TableRow key={key}>
                            <TableCell>{label}</TableCell>
                            <TableCell>
                              {(
                                data.benchmark.models.transaction_hgb[key]
                                  .mean * 100
                              ).toFixed(1)}
                              %
                            </TableCell>
                            <TableCell>
                              {(
                                data.benchmark.models.network_aware_hgb[key]
                                  .mean * 100
                              ).toFixed(1)}
                              %
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                    <Button
                      variant="ghost"
                      className="justify-between w-full"
                      onClick={() => setScreen('benchmark')}
                    >
                      Inspect measured benchmark <ArrowRight size={16} />
                    </Button>
                  </Card>
                  <div className="trust-note">
                    <CircleHelp size={18} />
                    <p>
                      Demo truth is an evaluation overlay, never a detection
                      feature. Risk scores are not calibrated fraud
                      probabilities.
                    </p>
                  </div>
                </div>
              </div>
            </>
          )}
        </main>
      </SidebarInset>
    </SidebarProvider>
  );
}

function Metric({
  label,
  value,
  detail,
  accent = false,
}: {
  label: string;
  value: string;
  detail: string;
  accent?: boolean;
}) {
  return (
    <Card className={`metric-card ${accent ? 'metric-accent' : ''}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </Card>
  );
}

function WorkspaceButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  const { setOpenMobile } = useSidebar();
  return (
    <SidebarMenuButton
      isActive={active}
      className="nav-item"
      onClick={() => {
        onClick();
        setOpenMobile(false);
      }}
    >
      {children}
    </SidebarMenuButton>
  );
}
