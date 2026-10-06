'use client';
import { useEffect, useMemo, useRef, useState } from 'react';
import cytoscape, { type Core, type ElementDefinition } from 'cytoscape';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
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
  const largeNetwork = graph.nodes.length > 250 || graph.edges.length > 500;
  const total = graph.nodes.length + graph.edges.length;
  const [progress, setProgress] = useState<{
    graph: EvidenceGraph;
    loaded: number;
  } | null>(null);
  const loaded = progress?.graph === graph ? progress.loaded : 0;
  const ready = progress?.graph === graph && loaded === total;
  const [entitySearch, setEntitySearch] = useState('');
  const [entityPage, setEntityPage] = useState(0);
  const [relationshipSearch, setRelationshipSearch] = useState('');
  const [relationshipPage, setRelationshipPage] = useState(0);
  const filteredEntities = useMemo(() => {
    const query = entitySearch.trim().toLowerCase();
    return query
      ? graph.nodes.filter((item) =>
          `${item.id} ${typeLabel(item.type)}`.toLowerCase().includes(query),
        )
      : graph.nodes;
  }, [graph, entitySearch]);
  const filteredRelationships = useMemo(() => {
    const query = relationshipSearch.trim().toLowerCase();
    return query
      ? graph.edges.filter((item) =>
          `${item.source} ${item.target} ${item.relationship}`
            .toLowerCase()
            .includes(query),
        )
      : graph.edges;
  }, [graph, relationshipSearch]);
  const entityPages = Math.max(1, Math.ceil(filteredEntities.length / 64));
  const relationshipPages = Math.max(
    1,
    Math.ceil(filteredRelationships.length / 64),
  );
  const currentEntityPage = Math.min(entityPage, entityPages - 1);
  const currentRelationshipPage = Math.min(
    relationshipPage,
    relationshipPages - 1,
  );
  const entityChoices = useMemo(
    () =>
      largeNetwork
        ? filteredEntities.slice(
            currentEntityPage * 64,
            (currentEntityPage + 1) * 64,
          )
        : graph.nodes,
    [graph, largeNetwork, filteredEntities, currentEntityPage],
  );
  const relationshipChoices = useMemo(
    () =>
      largeNetwork
        ? filteredRelationships.slice(
            currentRelationshipPage * 64,
            (currentRelationshipPage + 1) * 64,
          )
        : graph.edges,
    [graph, largeNetwork, filteredRelationships, currentRelationshipPage],
  );
  const entityOptions = useMemo(
    () =>
      entityChoices.map((item) => (
        <SelectItem key={item.id} value={item.id}>
          {typeLabel(item.type)} · {shortId(item.id)}
        </SelectItem>
      )),
    [entityChoices],
  );
  const relationshipOptions = useMemo(
    () =>
      relationshipChoices.map((item) => (
        <SelectItem key={item.id} value={item.id}>
          {shortId(item.source)} → {shortId(item.target)} · {item.relationship}
        </SelectItem>
      )),
    [relationshipChoices],
  );
  const node = graph.nodes.find((item) => item.id === selection);
  const edge = graph.edges.find((item) => item.id === selection);
  const related = node
    ? graph.edges.filter(
        (item) => item.source === node.id || item.target === node.id,
      )
    : [];
  useEffect(() => {
    if (!container.current) return;
    const columns = Math.max(
      1,
      Math.ceil(
        Math.sqrt(
          (graph.nodes.length * container.current.clientWidth) /
            Math.max(1, container.current.clientHeight),
        ),
      ),
    );
    const elements: ElementDefinition[] = [
      ...graph.nodes.map((item, index) => ({
        data: {
          ...item,
          label: shortId(item.id),
          color: palette[item.type] ?? '#a4b2c3',
          shared: Number(item.shared_infrastructure),
        },
        position: largeNetwork
          ? { x: (index % columns) * 56, y: Math.floor(index / columns) * 56 }
          : {
              x: Math.cos((index * Math.PI * 2) / graph.nodes.length) * 240,
              y: Math.sin((index * Math.PI * 2) / graph.nodes.length) * 240,
            },
      })),
      ...graph.edges.map((item) => ({ data: item })),
    ];
    const cy = cytoscape({
      container: container.current,
      elements: largeNetwork ? [] : elements,
      style: [
        {
          selector: 'node',
          style: {
            width: 25,
            height: 25,
            'background-color': 'data(color)',
            label: 'data(label)',
            color: '#334155',
            'font-size': 14,
            'min-zoomed-font-size': largeNetwork ? 8 : 0,
            'text-valign': 'bottom',
            'text-margin-y': 8,
            'text-background-color': '#f8fafc',
            'text-background-opacity': 0.85,
            'text-background-padding': '2px',
            'border-color': '#66788a',
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
          style: { 'border-width': 3, 'border-color': '#a56413' },
        },
        {
          selector: 'edge',
          style: {
            width: 1.5,
            'line-color': '#8496a8',
            'curve-style': 'bezier',
            'target-arrow-shape': 'triangle',
            'target-arrow-color': '#8496a8',
            'arrow-scale': 0.6,
          },
        },
        {
          selector: 'edge[relationship="pays out to"]',
          style: { 'line-style': 'dashed' },
        },
        {
          selector: 'node:selected',
          style: { 'border-width': 4, 'border-color': '#1f4f7a' },
        },
        {
          selector: 'edge:selected',
          style: {
            width: 3,
            'line-color': '#9b6a2a',
            label: 'data(relationship)',
            color: '#6b4a16',
            'font-size': 11,
            'text-background-color': '#ffffff',
            'text-background-opacity': 1,
            'text-background-padding': '4px',
            'text-rotation': 'autorotate',
          },
        },
        { selector: '.dimmed', style: { opacity: 0.22 } },
      ],
      layout: largeNetwork
        ? {
            name: 'preset',
            fit: false,
          }
        : {
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
      minZoom: largeNetwork ? 0.0001 : 0.15,
      maxZoom: 4,
      wheelSensitivity: 0.2,
    });
    network.current = cy;
    let cancelled = false;
    let complete = !largeNetwork;
    let frame = 0;
    let cursor = 0;
    const loadNext = () => {
      if (cancelled) return;
      const end = Math.min(cursor + 100, elements.length);
      cy.batch(() => cy.add(elements.slice(cursor, end)));
      cursor = end;
      if (cursor < elements.length) {
        frame = requestAnimationFrame(loadNext);
      } else {
        complete = true;
        cy.fit(undefined, 42);
      }
      setProgress({ graph, loaded: cursor });
    };
    if (largeNetwork) frame = requestAnimationFrame(loadNext);
    else
      frame = requestAnimationFrame(() =>
        setProgress({ graph, loaded: total }),
      );
    cy.on('tap', 'node, edge', (event) => {
      if (complete) setSelection(event.target.id());
    });
    cy.on('tap', (event) => {
      if (event.target === cy) setSelection('');
    });
    const resize = new ResizeObserver(() => cy.resize());
    resize.observe(container.current);
    return () => {
      cancelled = true;
      cancelAnimationFrame(frame);
      resize.disconnect();
      cy.destroy();
      if (network.current === cy) network.current = null;
    };
  }, [graph, largeNetwork, total]);
  useEffect(() => {
    const cy = network.current;
    if (!cy || !ready) return;
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
  }, [selection, graph, ready]);
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
            disabled={!ready}
            onClick={() => network.current?.fit(undefined, 42)}
          >
            Fit graph
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => zoom(1.25)}
            disabled={!ready}
            aria-label="Zoom in"
          >
            +
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => zoom(0.8)}
            disabled={!ready}
            aria-label="Zoom out"
          >
            −
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={!ready}
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
            disabled={!selection || !ready}
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
        {!ready && (
          <div className="network-loading" aria-live="polite">
            <p>
              Preparing network: {loaded.toLocaleString()} of{' '}
              {total.toLocaleString()} entities and links.
            </p>
            <progress
              aria-label="Network loading progress"
              value={loaded}
              max={Math.max(1, total)}
            />
          </div>
        )}
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
        {largeNetwork && (
          <>
            <label htmlFor="entity-search">Find entity</label>
            <Input
              id="entity-search"
              type="search"
              value={entitySearch}
              maxLength={200}
              placeholder="Full ID or entity type"
              onChange={(event) => {
                setEntitySearch(event.target.value);
                setEntityPage(0);
              }}
            />
            <p className="muted text-xs">
              {filteredEntities.length.toLocaleString()} matching entities ·
              page {currentEntityPage + 1} of {entityPages}
            </p>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                aria-label="Previous entity page"
                disabled={currentEntityPage === 0}
                onClick={() => setEntityPage(currentEntityPage - 1)}
              >
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                aria-label="Next entity page"
                disabled={currentEntityPage + 1 >= entityPages}
                onClick={() => setEntityPage(currentEntityPage + 1)}
              >
                Next
              </Button>
            </div>
            {!filteredEntities.length && (
              <p className="muted text-xs">No matching entities.</p>
            )}
          </>
        )}
        <Select
          disabled={!ready}
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
          <SelectContent>{entityOptions}</SelectContent>
        </Select>
        <label id="edge-picker-label" htmlFor="edge-picker">
          Relationship
        </label>
        {largeNetwork && (
          <>
            <label htmlFor="relationship-search">Find relationship</label>
            <Input
              id="relationship-search"
              type="search"
              value={relationshipSearch}
              maxLength={200}
              placeholder="Full endpoint ID or relationship"
              onChange={(event) => {
                setRelationshipSearch(event.target.value);
                setRelationshipPage(0);
              }}
            />
            <p className="muted text-xs">
              {filteredRelationships.length.toLocaleString()} matching
              relationships · page {currentRelationshipPage + 1} of{' '}
              {relationshipPages}
            </p>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                aria-label="Previous relationship page"
                disabled={currentRelationshipPage === 0}
                onClick={() => setRelationshipPage(currentRelationshipPage - 1)}
              >
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                aria-label="Next relationship page"
                disabled={currentRelationshipPage + 1 >= relationshipPages}
                onClick={() => setRelationshipPage(currentRelationshipPage + 1)}
              >
                Next
              </Button>
            </div>
            {!filteredRelationships.length && (
              <p className="muted text-xs">No matching relationships.</p>
            )}
          </>
        )}
        <Select
          disabled={!ready}
          value={edge?.id ?? ''}
          onValueChange={(value) => setSelection(String(value ?? ''))}
        >
          <SelectTrigger id="edge-picker" aria-labelledby="edge-picker-label">
            <SelectValue placeholder="Select a relationship">
              {edge ? edge.relationship : 'Select a relationship'}
            </SelectValue>
          </SelectTrigger>
          <SelectContent>{relationshipOptions}</SelectContent>
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
      {largeNetwork && (
        <p className="muted text-xs">
          Large networks use a grid layout. Select an entity and use Focus
          selected to inspect its connections. All reported entities and links
          remain available.
        </p>
      )}
    </div>
  );
}
