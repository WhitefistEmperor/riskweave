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
import {
  type EvidenceGraph,
  type EvidenceKey,
  evidenceLabel,
} from '@/lib/evidence';
import { shortId } from '@/lib/api';

const palette: Record<string, string> = {
  CUSTOMER: '#a7c8ef',
  DEVICE: '#b3a3d9',
  IP: '#79b9c9',
  CARD: '#d9bc87',
  ADDRESS: '#c4a0ba',
  MERCHANT: '#ddaaa0',
  BANK_ACCOUNT: '#b7c590',
};
const typeLabel = (type: string) =>
  type === 'BANK_ACCOUNT'
    ? 'Payout account'
    : type === 'IP'
      ? 'IP address'
      : type.charAt(0) + type.slice(1).toLowerCase();

export default function EvidenceNetwork({
  graph,
  onEvidence,
}: {
  graph: EvidenceGraph;
  onEvidence: (key: EvidenceKey) => void;
}) {
  const container = useRef<HTMLDivElement>(null);
  const network = useRef<Core | null>(null);
  const [selection, setSelection] = useState('');
  const [height, setHeight] = useState(460);
  const node = graph.nodes.find((item) => item.id === selection);
  const edge = graph.edges.find((item) => item.id === selection);
  const related = node
    ? graph.edges.filter(
        (item) => item.source === node.id || item.target === node.id,
      )
    : [];
  useEffect(() => {
    if (!container.current) return;
    const cy = cytoscape({
      container: container.current,
      elements: [
        ...graph.nodes.map((item, index) => ({
          data: {
            ...item,
            label: shortId(item.id),
            color: palette[item.type] ?? '#a4b2c3',
            shared: Number(item.shared_infrastructure),
          },
          position: {
            x: Math.cos((index * Math.PI * 2) / graph.nodes.length) * 240,
            y: Math.sin((index * Math.PI * 2) / graph.nodes.length) * 240,
          },
        })),
        ...graph.edges.map((item) => ({ data: item })),
      ],
      style: [
        {
          selector: 'node',
          style: {
            width: 25,
            height: 25,
            'background-color': 'data(color)',
            label: 'data(label)',
            color: '#d9e5f4',
            'font-size': 14,
            'text-valign': 'bottom',
            'text-margin-y': 8,
            'text-background-color': '#131c27',
            'text-background-opacity': 0.85,
            'text-background-padding': '2px',
            'border-color': '#607083',
            'border-width': 1,
          },
        },
        { selector: 'node[type="CUSTOMER"]', style: { width: 32, height: 32 } },
        {
          selector: 'node[type="DEVICE"],node[type="CARD"]',
          style: { shape: 'round-rectangle' },
        },
        {
          selector: 'node[type="IP"],node[type="ADDRESS"]',
          style: { shape: 'diamond' },
        },
        {
          selector: 'node[type="MERCHANT"],node[type="BANK_ACCOUNT"]',
          style: { shape: 'hexagon' },
        },
        {
          selector: 'node[shared=1]',
          style: { 'border-width': 3, 'border-color': '#e1c394' },
        },
        {
          selector: 'edge',
          style: {
            width: 1.5,
            'line-color': '#607791',
            'curve-style': 'bezier',
            'target-arrow-shape': 'triangle',
            'target-arrow-color': '#607791',
            'arrow-scale': 0.6,
          },
        },
        {
          selector: 'edge[relationship="pays out to"]',
          style: { 'line-style': 'dashed' },
        },
        {
          selector: 'node:selected',
          style: { 'border-width': 4, 'border-color': '#fff' },
        },
        {
          selector: 'edge:selected',
          style: {
            width: 3,
            'line-color': '#e4c69c',
            label: 'data(relationship)',
            color: '#f0ddbd',
            'font-size': 11,
            'text-background-color': '#131c27',
            'text-background-opacity': 1,
            'text-background-padding': '4px',
            'text-rotation': 'autorotate',
          },
        },
        { selector: '.dimmed', style: { opacity: 0.22 } },
      ],
      layout: {
        name: 'cose',
        nodeDimensionsIncludeLabels: true,
        nodeOverlap: 12,
        componentSpacing: 40,
        randomize: false,
        animate: false,
        padding: 42,
        nodeRepulsion: () => 18000,
        idealEdgeLength: () => 70,
      },
      minZoom: 0.15,
      maxZoom: 4,
      wheelSensitivity: 0.2,
    });
    network.current = cy;
    cy.on('tap', 'node, edge', (event) => setSelection(event.target.id()));
    cy.on('tap', (event) => {
      if (event.target === cy) setSelection('');
    });
    const resize = new ResizeObserver(() => cy.resize());
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
    cy.elements().unselect().removeClass('dimmed');
    if (selection) {
      const selected = cy.getElementById(selection);
      selected.select();
      const selectedEdge = cy.edges().filter((item) => item.id() === selection);
      const neighborhood = selectedEdge.length
        ? selectedEdge.union(selectedEdge.connectedNodes())
        : selected.closedNeighborhood();
      cy.elements().difference(neighborhood).addClass('dimmed');
    }
  }, [selection, graph]);
  const zoom = (factor: number) => {
    const cy = network.current;
    if (cy)
      cy.zoom({
        level: cy.zoom() * factor,
        renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 },
      });
  };
  return (
    <div className="evidence-network">
      <div className="network-workarea">
        <div className="network-actions">
          <Button
            variant="outline"
            size="sm"
            onClick={() => network.current?.fit(undefined, 42)}
          >
            Fit graph
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => zoom(1.25)}
            aria-label="Zoom in"
          >
            +
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => zoom(0.8)}
            aria-label="Zoom out"
          >
            −
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setSelection('');
              network.current?.fit(undefined, 42);
            }}
          >
            Reset view
          </Button>
          <Button
            variant="ghost"
            size="sm"
            disabled={!selection}
            onClick={() => {
              const cy = network.current;
              if (cy)
                cy.fit(cy.getElementById(selection).closedNeighborhood(), 70);
            }}
          >
            Focus selected
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setHeight((h) => (h === 460 ? 640 : 460))}
          >
            {height === 460 ? 'Expand graph' : 'Compact graph'}
          </Button>
        </div>
        <div
          ref={container}
          className="evidence-canvas"
          style={{ height }}
          aria-hidden="true"
        />
        <div className="network-legend">
          {Object.entries(palette).map(([type, color]) => (
            <span key={type}>
              <i style={{ background: color }} className={`shape-${type}`} />
              {typeLabel(type)}
            </span>
          ))}
        </div>
        <p className="network-caption">
          Drag to pan · Scroll to zoom · Gold outline: shared resource · Dashed
          arrow: payout relationship
        </p>
      </div>
      <aside className="network-inspector" aria-label="Graph details">
        <span className="product-kicker">INSPECT CONNECTIONS</span>
        <h3>
          {node
            ? typeLabel(node.type)
            : edge
              ? 'Recorded relationship'
              : 'Select an entity or link'}
        </h3>
        <p className="muted text-xs">
          Choose on the graph or use the keyboard-accessible selectors below.
        </p>
        <label id="entity-picker-label" htmlFor="entity-picker">
          Entity
        </label>
        <Select
          value={node?.id ?? ''}
          onValueChange={(value) => setSelection(String(value ?? ''))}
        >
          <SelectTrigger
            id="entity-picker"
            aria-labelledby="entity-picker-label"
          >
            <SelectValue placeholder="Select an entity">
              {node
                ? `${typeLabel(node.type)} · ${shortId(node.id)}`
                : 'Select an entity'}
            </SelectValue>
          </SelectTrigger>
          <SelectContent>
            {graph.nodes.map((item) => (
              <SelectItem key={item.id} value={item.id}>
                {typeLabel(item.type)} · {shortId(item.id)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <label id="edge-picker-label" htmlFor="edge-picker">
          Relationship
        </label>
        <Select
          value={edge?.id ?? ''}
          onValueChange={(value) => setSelection(String(value ?? ''))}
        >
          <SelectTrigger id="edge-picker" aria-labelledby="edge-picker-label">
            <SelectValue placeholder="Select a relationship">
              {edge ? edge.relationship : 'Select a relationship'}
            </SelectValue>
          </SelectTrigger>
          <SelectContent>
            {graph.edges.map((item) => (
              <SelectItem key={item.id} value={item.id}>
                {shortId(item.source)} → {shortId(item.target)} ·{' '}
                {item.relationship}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {node && (
          <div className="selection-details">
            <p className="mono">{node.id}</p>
            <p>
              {node.shared_infrastructure
                ? 'Shared by multiple observed customers or merchants.'
                : 'An entity reported by the candidate evidence.'}
            </p>
            <p>{related.length} explicit relationships shown.</p>
            {!related.length && (
              <p className="muted">
                No link is provided by the available queries. None has been
                inferred.
              </p>
            )}
            {related.map((item) => (
              <button
                key={item.id}
                onClick={() => setSelection(item.id)}
                className="relationship-item"
              >
                {item.relationship}
                <span>
                  {shortId(item.source === node.id ? item.target : item.source)}{' '}
                  →
                </span>
              </button>
            ))}
          </div>
        )}
        {edge && (
          <div className="selection-details">
            <p>
              <strong>{edge.relationship}</strong>
            </p>
            <p className="mono">{edge.source}</p>
            <span>↓</span>
            <p className="mono">{edge.target}</p>
            <p className="muted">
              Source: {evidenceLabel(edge.query)}. No per-edge event count is
              provided by this query.
            </p>
            <Button
              variant="outline"
              size="sm"
              onClick={() => onEvidence(edge.query)}
            >
              Open source evidence
            </Button>
          </div>
        )}
      </aside>
      <p className="network-scope">
        {graph.nodes.length} entities · {graph.edges.length} explicit links.
        This is an evidence projection, not the complete event graph.
        Unshared-resource links are not present in these queries. No missing
        relationship is inferred.
      </p>
    </div>
  );
}
