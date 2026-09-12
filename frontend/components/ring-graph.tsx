'use client';

import { useEffect, useRef, useState } from 'react';
import cytoscape, { type Core } from 'cytoscape';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { type GraphData, type GraphNode, shortId } from '@/lib/api';

const colors: Record<string, string> = {
  CUSTOMER: '#76dccc',
  DEVICE: '#a496ed',
  IP: '#64aadd',
  CARD: '#e9b679',
  ADDRESS: '#c88bbd',
  MERCHANT: '#df8585',
  BANK_ACCOUNT: '#d4d285',
};

export function RingGraph({ graph }: { graph: GraphData }) {
  const container = useRef<HTMLDivElement>(null);
  const network = useRef<Core | null>(null);
  const [selected, setSelected] = useState<GraphNode | null>(null);
  const [highlight, setHighlight] = useState(true);
  useEffect(() => {
    if (!container.current) return;
    const cy = cytoscape({
      container: container.current,
      elements: [
        ...graph.nodes.map((node, index) => ({
          data: {
            ...node,
            label: shortId(node.id),
            color: colors[node.type] ?? '#94a3b8',
            shared: node.shared_infrastructure ? 1 : 0,
          },
          position: {
            x: Math.cos((index * 2 * Math.PI) / graph.nodes.length) * 220,
            y: Math.sin((index * 2 * Math.PI) / graph.nodes.length) * 220,
          },
        })),
        ...graph.edges.map((edge, index) => ({
          data: {
            ...edge,
            id: `edge-${index}`,
            shared: edge.suspicious ? 1 : 0,
          },
        })),
      ],
      style: [
        {
          selector: 'node',
          style: {
            'background-color': 'data(color)',
            label: 'data(label)',
            color: '#334155',
            'font-size': 9,
            'text-margin-y': 8,
            'text-valign': 'bottom',
            width: 22,
            height: 22,
            'border-width': 1,
            'border-color': '#64748b',
          },
        },
        { selector: 'node[type="CUSTOMER"]', style: { width: 28, height: 28 } },
        {
          selector: 'node[type="DEVICE"], node[type="CARD"]',
          style: { shape: 'round-rectangle' },
        },
        {
          selector: 'node[type="IP"], node[type="ADDRESS"]',
          style: { shape: 'diamond' },
        },
        {
          selector: 'node[type="MERCHANT"], node[type="BANK_ACCOUNT"]',
          style: { shape: 'hexagon' },
        },
        {
          selector: 'edge',
          style: {
            width: 1,
            'line-color': '#94a3b8',
            'curve-style': 'bezier',
            opacity: 0.65,
          },
        },
        {
          selector: '.shared',
          style: {
            'border-width': 3,
            'border-color': '#9a5b0a',
            'line-color': '#b7791f',
            width: 2,
          },
        },
        { selector: 'node.shared', style: { width: 28, height: 28 } },
        {
          selector: ':selected',
          style: { 'border-width': 4, 'border-color': '#0f766e' },
        },
      ],
      layout: {
        name: 'cose',
        randomize: false,
        animate: false,
        padding: 35,
        nodeRepulsion: () => 15000,
        idealEdgeLength: () => 80,
      },
      minZoom: 0.2,
      maxZoom: 4,
    });
    cy.on('tap', 'node', (event) => {
      const id = (event.target as cytoscape.NodeSingular).id();
      setSelected(graph.nodes.find((node) => node.id === id) ?? null);
    });
    network.current = cy;
    const resize = new ResizeObserver(() => {
      cy.resize();
    });
    resize.observe(container.current);
    return () => {
      resize.disconnect();
      cy.destroy();
      network.current = null;
    };
  }, [graph]);
  useEffect(() => {
    const cy = network.current;
    if (!cy) return;
    cy.elements().removeClass('shared');
    if (highlight) cy.elements('[shared = 1]').addClass('shared');
  }, [graph, highlight]);
  return (
    <>
      <div className="graph-toolbar">
        <Button
          variant="outline"
          size="sm"
          onClick={() => network.current?.fit(undefined, 35)}
        >
          Fit graph
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            const node =
              selected && network.current?.getElementById(selected.id);
            if (node) network.current?.fit(node.closedNeighborhood(), 60);
          }}
          disabled={!selected}
        >
          Focus selected
        </Button>
        <Button
          variant={highlight ? 'secondary' : 'ghost'}
          size="sm"
          onClick={() => setHighlight(!highlight)}
        >
          Shared infrastructure {highlight ? 'on' : 'off'}
        </Button>
      </div>
      <div
        ref={container}
        className="network-canvas"
        aria-label="Interactive candidate network; drag to pan, scroll to zoom"
      />
      <div className="graph-legend">
        {Object.entries(colors).map(([type, color]) => (
          <span key={type}>
            <i style={{ background: color }} />
            {type === 'BANK_ACCOUNT' ? 'Payout' : type.toLowerCase()}
          </span>
        ))}
      </div>
      <div className="node-inspector">
        <Select
          value={selected?.id ?? ''}
          onValueChange={(id) => {
            const node = graph.nodes.find((item) => item.id === id);
            setSelected(node ?? null);
            if (node) {
              network.current?.elements().unselect();
              network.current?.getElementById(node.id).select();
            }
          }}
        >
          <SelectTrigger aria-label="Inspect graph node" className="w-full">
            <SelectValue placeholder="Select a node to inspect" />
          </SelectTrigger>
          <SelectContent>
            {graph.nodes.map((node) => (
              <SelectItem key={node.id} value={node.id}>
                {node.type} · {shortId(node.id)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {selected && (
          <div className="mt-3">
            <p className="mono break-all">{selected.id}</p>
            <p className="muted text-sm">
              {selected.type} ·{' '}
              {selected.shared_infrastructure
                ? 'Shared by multiple observed customers or merchants'
                : 'Member of the candidate event graph'}{' '}
              ·{' '}
              {
                graph.edges.filter(
                  (edge) =>
                    edge.source === selected.id || edge.target === selected.id,
                ).length
              }{' '}
              observed relationships
            </p>
          </div>
        )}
      </div>
    </>
  );
}
