import { Card } from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { type Benchmark, type Metrics, money } from '@/lib/api';

const labels: Record<string, string> = {
  transaction_hgb: 'Transaction-only ML',
  graph_heuristic: 'Graph heuristic',
  network_aware_hgb: 'RingSentinel network-aware',
  transaction_only: 'Transaction only',
  transaction_plus_infrastructure: '+ Infrastructure sharing',
  transaction_plus_temporal: '+ Temporal context',
  transaction_plus_structural: '+ Structural graph',
  full_network_aware: 'Full network-aware',
};
const fields = [
  ['pr_auc', 'PR-AUC'],
  ['precision', 'Precision'],
  ['recall', 'Recall'],
  ['f1', 'F1'],
  ['false_positive_rate', 'FPR'],
  ['ring_detection_rate', 'Ring detection'],
  ['benign_communities_flagged', 'Benign groups flagged'],
] as const;

export function BenchmarkView({ benchmark }: { benchmark: Benchmark }) {
  const exposure = benchmark.exposure.matched_rings as {
    mean_relative_error: number;
    aggregate_estimated_exposure_minor: number;
    aggregate_actual_exposure_minor: number;
    mae_minor: number;
    median_absolute_error_minor: number;
    ring_count: number;
  };
  const under =
    1 -
    exposure.aggregate_estimated_exposure_minor /
      exposure.aggregate_actual_exposure_minor;
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">MEASURED VALIDATION · PHASE 3</p>
          <h1>The benchmark, with the caveats.</h1>
          <p className="muted">
            Five held-out synthetic ecosystems · seeds{' '}
            {benchmark.seeds.join(', ')} ·{' '}
            {benchmark.transactions_per_seed.toLocaleString()} payments per seed
            plus refunds
          </p>
        </div>
        <span className="status-chip cyan">Artifact-backed results</span>
      </div>
      <div className="metrics-grid">
        <Kpi
          label="Transaction-only PR-AUC"
          value={benchmark.models.transaction_hgb.pr_auc.mean.toFixed(3)}
        />
        <Kpi
          label="Network-aware PR-AUC"
          value={benchmark.models.network_aware_hgb.pr_auc.mean.toFixed(3)}
        />
        <Kpi
          label="Network ring detection"
          value={`${(benchmark.models.network_aware_hgb.ring_detection_rate.mean * 100).toFixed(0)}%`}
        />
        <Kpi
          label="Exposure mean relative error"
          value={`${(exposure.mean_relative_error * 100).toFixed(2)}%`}
        />
      </div>
      <Card className="panel mb-5">
        <div className="panel-heading">
          <h2>Same test ecosystems. Different information.</h2>
          <span className="muted text-sm">
            Mean ± population standard deviation
          </span>
        </div>
        <MetricTable rows={benchmark.models} />
        <p className="table-footnote">
          PR-AUC summarizes event ranking. Ring detection is evaluated
          separately; it does not imply every event was detected. Benign groups
          flagged is a count out of six per seed.
        </p>
      </Card>
      <Card className="panel mb-5">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">CONTROLLED FEATURE ABLATION</p>
            <h2>Where does the gain come from?</h2>
          </div>
        </div>
        <MetricTable rows={benchmark.ablations} ablation />
        <p className="table-footnote">
          Each “+” row adds that family to transaction features, not to the
          preceding row. Training seeds, validation-threshold selection, and
          model family are held fixed.
        </p>
      </Card>
      <div className="two-column">
        <Card className="panel p-5">
          <p className="eyebrow">
            EXPOSURE VALIDATION · {exposure.ring_count} MATCHED RINGS
          </p>
          <h2>Detection is not valuation accuracy</h2>
          <dl className="definition-list">
            <dt>Estimated aggregate</dt>
            <dd>{money(exposure.aggregate_estimated_exposure_minor)}</dd>
            <dt>Ground-truth aggregate</dt>
            <dd>{money(exposure.aggregate_actual_exposure_minor)}</dd>
            <dt>Aggregate underestimation</dt>
            <dd>{(under * 100).toFixed(2)}%</dd>
            <dt>Mean absolute error</dt>
            <dd>{money(exposure.mae_minor)}</dd>
            <dt>Median absolute error</dt>
            <dd>{money(exposure.median_absolute_error_minor)}</dd>
          </dl>
          <p className="muted text-sm">
            Exposure counts at-risk purchase/refund value once per original
            payment. It is not calibrated expected loss.
          </p>
        </Card>
        <Card className="panel p-5">
          <p className="eyebrow">TRANSPARENCY</p>
          <h2>Strong synthetic evidence. Bounded claims.</h2>
          <ul className="limitations-list">
            {benchmark.limitations.map((item) => (
              <li key={item}>{item}</li>
            ))}
            <li>
              The eight-minute alert is one seed/scenario demonstration, not the
              average detection delay.
            </li>
          </ul>
          <p className="muted text-sm mt-4">
            Source: results/phase3/phase3_results.json · unchanged measured
            artifact. Full held-archetype results and weaknesses remain in
            phase3_summary.md.
          </p>
        </Card>
      </div>
    </>
  );
}
function MetricTable({
  rows,
  ablation = false,
}: {
  rows: Record<string, Metrics>;
  ablation?: boolean;
}) {
  const shownFields = ablation
    ? [
        ...fields.slice(0, -1),
        ['hard_negative_false_positive_rate', 'Benign-community flag rate'],
      ]
    : fields;
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Model / feature set</TableHead>
          {shownFields.map(([key, label]) => (
            <TableHead key={key}>{label}</TableHead>
          ))}
        </TableRow>
      </TableHeader>
      <TableBody>
        {Object.entries(rows).map(([name, metrics]) => (
          <TableRow
            key={name}
            className={name.includes('network_aware') ? 'highlight-row' : ''}
          >
            <TableCell>{labels[name] ?? name}</TableCell>
            {shownFields.map(([key]) => {
              const metric = metrics[key];
              const percent = key.endsWith('rate');
              const scale = percent ? 100 : 1;
              return (
                <TableCell key={key} className="mono">
                  {metric ? (
                    <>
                      {(metric.mean * scale).toFixed(percent ? 2 : 3)}
                      {percent ? '%' : ''}
                      <small className="metric-std">
                        ± {(metric.std * scale).toFixed(percent ? 2 : 3)}
                        {percent ? '%' : ''}
                      </small>
                    </>
                  ) : (
                    'Not reported'
                  )}
                </TableCell>
              );
            })}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <Card className="metric-card">
      <span>{label}</span>
      <strong>{value}</strong>
    </Card>
  );
}
