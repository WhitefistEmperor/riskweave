'use client';

import { useEffect, useState } from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { RingGraph } from '@/components/ring-graph';
import { apiGet, type GraphData } from '@/lib/api';
import { humanize } from '@/components/evidence-value';

type Community = {
  community_id: string;
  archetype: string;
  size: number;
  rationale: string;
  event_count: number;
  shared_entity_types: Record<string, number>;
  max_graph_heuristic_score: number;
  max_network_score: number;
  graph_heuristic_flagged: boolean;
  network_aware_flagged: boolean;
  graph_threshold: number;
  network_threshold: number;
  graph: GraphData;
};

export function HardNegatives() {
  const [communities, setCommunities] = useState<Community[] | null>(null);
  const [selected, setSelected] = useState(0);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    apiGet<Community[]>('/hard-negatives')
      .then((value) => {
        if (active) setCommunities(value);
      })
      .catch((reason: unknown) => {
        if (active) setError(String(reason));
      });
    return () => {
      active = false;
    };
  }, []);
  if (error)
    return (
      <Card className="panel p-5">
        <h2>Community data unavailable</h2>
        <p>{error}</p>
      </Card>
    );
  if (!communities) return <Skeleton className="h-96" />;
  const community = communities[selected];
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">BENIGN HARD-NEGATIVE LAB · SEED 105</p>
          <h1>Connected does not mean coordinated abuse.</h1>
          <p className="muted">
            Legitimate dense communities, scored by the same held-out
            network-aware model.
          </p>
        </div>
      </div>
      <div className="community-picker">
        {communities.map((item, index) => (
          <Button
            key={item.community_id}
            variant={selected === index ? 'secondary' : 'outline'}
            onClick={() => setSelected(index)}
          >
            {humanize(item.archetype)}{' '}
            <span className="muted">{item.size}</span>
          </Button>
        ))}
      </div>
      <div className="two-column mb-5">
        <Card className="panel p-5">
          <p className="eyebrow">LABELED BENIGN SCENARIO · EVALUATION ONLY</p>
          <h2 className="capitalize">{humanize(community.archetype)}</h2>
          <p className="muted mt-3">{community.rationale}</p>
          <dl className="definition-list">
            <dt>Customers</dt>
            <dd>{community.size}</dd>
            <dt>Observed events</dt>
            <dd>{community.event_count}</dd>
            <dt>Shared resources</dt>
            <dd>
              {Object.entries(community.shared_entity_types)
                .map(([key, value]) => `${value} ${key.toLowerCase()}`)
                .join(' · ')}
            </dd>
          </dl>
        </Card>
        <Card className="panel p-5">
          <h2>Actual model outcomes</h2>
          <div className="model-outcome">
            <span>Naive graph heuristic</span>
            <strong
              className={community.graph_heuristic_flagged ? 'amber' : 'cyan'}
            >
              {community.graph_heuristic_flagged
                ? 'Community flagged'
                : 'Not flagged'}
            </strong>
            <small>
              Maximum event score{' '}
              {community.max_graph_heuristic_score.toFixed(3)} · threshold{' '}
              {community.graph_threshold.toFixed(2)}
            </small>
          </div>
          <div className="model-outcome">
            <span>Network-aware model</span>
            <strong
              className={community.network_aware_flagged ? 'amber' : 'cyan'}
            >
              {community.network_aware_flagged
                ? 'Community flagged'
                : 'Not flagged'}
            </strong>
            <small>
              Maximum event score {community.max_network_score.toFixed(3)} ·
              threshold {community.network_threshold.toFixed(2)}
            </small>
          </div>
          <p className="muted text-sm mt-4">
            Scores belong to different methods and are not calibrated
            probabilities. A community is flagged when any member event exceeds
            that method’s threshold.
          </p>
        </Card>
      </div>
      <Card className="panel">
        <div className="panel-heading">
          <h2>Legitimate sharing can look suspicious</h2>
          <span className="muted text-sm">
            Community customers + shared resources only
          </span>
        </div>
        <RingGraph key={community.community_id} graph={community.graph} />
      </Card>
      <div className="trust-box">
        The heuristic uses sharing rules; the network-aware model also receives
        temporal and behavioral context. These observed outcomes support
        “sharing alone is insufficient.” They do not prove which feature caused
        this individual prediction, and the ground-truth rationale is not a
        detection input.
      </div>
    </>
  );
}
