import { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import './App.css';

const API_BASE = 'http://127.0.0.1:8000';
const COLORS: Record<string, string> = {
  lacI: '#4a90d9', tetR: '#ff8a5c', cI: '#33d6a6',
  geneU: '#4a90d9', geneV: '#ff8a5c',
  geneX: '#4a90d9', geneY: '#ff8a5c', geneZ: '#33d6a6',
  phlF: '#c86bff', betI: '#ffd166', amtR: '#4adede',
};

type SimResult = {
  t: number[];
  species: Record<string, number[]>;
  success: boolean;
};

type ModelJson = {
  parts: { id: string; [key: string]: unknown }[];
  edges: { from: string; to: string; type: string }[];
};

const CIRCUITS = [
  { id: 'repressilator', label: 'Repressilator' },
  { id: 'toggle', label: 'Toggle switch' },
  { id: 'feedforward', label: 'Feedforward loop' },
  { id: 'real_gate_ring', label: 'Real-gate ring (PhlF/BetI/AmtR)' },
  { id: 'cello_nor_gate', label: 'Cello NOR gate demo' },
];

function friendlyError(raw: string): string {
  if (raw.includes('RESOURCE_EXHAUSTED') || raw.includes('429')) {
    return 'Daily AI quota reached for this key. This resets at midnight Pacific Time — try again after that, or switch to a key from a different Google account.';
  }
  if (raw.toLowerCase().includes('failed to fetch')) {
    return "Can't reach the backend. Check that the FastAPI server is still running.";
  }
  return raw.length > 160 ? raw.slice(0, 160) + '…' : raw;
}

function ChartSkeleton() {
  return (
    <div style={{ display: 'flex', alignItems: 'flex-end', gap: 6, height: '90%', padding: '0 4px' }}>
      {[40, 70, 50, 85, 60, 90, 45, 75, 55, 65].map((h, i) => (
        <div key={i} className="skeleton-block" style={{ flex: 1, height: `${h}%`, animationDelay: `${i * 0.08}s` }} />
      ))}
    </div>
  );
}

function CircuitDiagram({ model }: { model: ModelJson | null }) {
  if (!model || model.parts.length === 0) return null;

  const width = 680;
  const height = 400;
  const cx = width / 2;
  const cy = height / 2;
  const nodeR = 42;
  const layoutR = model.parts.length <= 2 ? 130 : 115;

  const positions: Record<string, { x: number; y: number }> = {};
  model.parts.forEach((p, i) => {
    if (model.parts.length === 1) {
      positions[p.id] = { x: cx, y: cy };
    } else {
      const angle = -Math.PI / 2 + (i * 2 * Math.PI) / model.parts.length;
      positions[p.id] = { x: cx + layoutR * Math.cos(angle), y: cy + layoutR * Math.sin(angle) };
    }
  });

  return (
    <svg width="100%" viewBox={`0 0 ${width} ${height}`} role="img">
      <title>Circuit structure diagram</title>
      <defs>
        <marker id="activateArrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
          <path d="M1 1L9 5L1 9Z" fill="var(--accent-activate)" />
        </marker>
      </defs>
      {model.edges.map((edge, i) => {
        const from = positions[edge.from];
        const to = positions[edge.to];
        if (!from || !to) return null;
        const dx = to.x - from.x;
        const dy = to.y - from.y;
        const dist = Math.hypot(dx, dy) || 1;
        const ux = dx / dist;
        const uy = dy / dist;
        const x1 = from.x + ux * nodeR;
        const y1 = from.y + uy * nodeR;
        const x2 = to.x - ux * (nodeR + (edge.type === 'repress' ? 14 : 8));
        const y2 = to.y - uy * (nodeR + (edge.type === 'repress' ? 14 : 8));
        const isRepress = edge.type === 'repress';
        const px = -uy;
        const py = ux;
        const tickLen = 13;

        return (
          <g key={i}>
            <line
              x1={x1} y1={y1} x2={x2} y2={y2}
              stroke={isRepress ? 'var(--accent-repress)' : 'var(--accent-activate)'}
              strokeWidth={2.5}
              markerEnd={isRepress ? undefined : 'url(#activateArrow)'}
            />
            {isRepress && (
              <line
                x1={x2 + px * tickLen} y1={y2 + py * tickLen}
                x2={x2 - px * tickLen} y2={y2 - py * tickLen}
                stroke="var(--accent-repress)" strokeWidth={3}
              />
            )}
          </g>
        );
      })}
      {model.parts.map((p) => {
        const color = COLORS[p.id] || '#8888aa';
        const pos = positions[p.id];
        return (
          <g key={p.id}>
            <circle cx={pos.x} cy={pos.y} r={nodeR} fill={color + '1a'} stroke={color} strokeWidth={2.5} />
            <text x={pos.x} y={pos.y + 6} textAnchor="middle" fontSize={13} fontWeight={600} fill="var(--text-primary)" fontFamily="IBM Plex Mono, monospace">{p.id.includes('_') ? p.id.split('_').slice(-2).join('_') : p.id}</text>
          </g>
        );
      })}
      <g transform={`translate(24, ${height - 26})`}>
        <line x1={0} y1={0} x2={28} y2={0} stroke="var(--accent-activate)" strokeWidth={2.5} markerEnd="url(#activateArrow)" />
        <text x={36} y={5} fontSize={12} fill="var(--text-secondary)">activates</text>
        <line x1={160} y1={0} x2={188} y2={0} stroke="var(--accent-repress)" strokeWidth={2.5} />
        <line x1={188} y1={-7} x2={188} y2={7} stroke="var(--accent-repress)" strokeWidth={3} />
        <text x={196} y={5} fontSize={12} fill="var(--text-secondary)">represses</text>
      </g>
    </svg>
  );
}

function App() {
  const [circuitName, setCircuitName] = useState('repressilator');
  const [mode, setMode] = useState<'deterministic' | 'stochastic'>('deterministic');
  const [result, setResult] = useState<SimResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const [currentModel, setCurrentModel] = useState<ModelJson | null>(null);
  const [instruction, setInstruction] = useState('');
  const [explanation, setExplanation] = useState<string | null>(null);
  const [substitutionNote, setSubstitutionNote] = useState<string | null>(null);
  const [editLoading, setEditLoading] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function run() {
      setLoading(true);
      setError(null);
      setExplanation(null);
      setSubstitutionNote(null);
      setEditError(null);
      try {
        const modelRes = await fetch(`${API_BASE}/circuits/${circuitName}`);
        if (!modelRes.ok) throw new Error(`Failed to load circuit: ${modelRes.status}`);
        const model: ModelJson = await modelRes.json();
        if (cancelled) return;
        setCurrentModel(model);

        const simRes = await fetch(`${API_BASE}/simulate?mode=${mode}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(model),
        });
        if (!simRes.ok) throw new Error(`Simulation failed: ${simRes.status}`);
        const simData = await simRes.json();
        if (!cancelled) setResult(simData);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    run();
    return () => { cancelled = true; };
  }, [circuitName, mode]);

  async function handleEditSubmit() {
    if (!currentModel || !instruction.trim()) return;
    setEditLoading(true);
    setEditError(null);
    setExplanation(null);
    setSubstitutionNote(null);
    try {
      const res = await fetch(`${API_BASE}/edit_and_explain`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ instruction, current_model: currentModel }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `Request failed: ${res.status}`);

      setCurrentModel(data.edited_model);
      setResult(data.after);
      setExplanation(data.explanation);
      setSubstitutionNote(data.substitution_note || null);
    } catch (err) {
      setEditError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setEditLoading(false);
    }
  }

  const proteinSeries = result
    ? Object.keys(result.species).filter((k) => k.endsWith('_protein'))
    : [];

  const downsampleStep = result ? Math.max(1, Math.floor(result.t.length / 2000)) : 1;
  const chartData = result
    ? result.t.filter((_, i) => i % downsampleStep === 0).map((t, i) => {
        const originalIndex = i * downsampleStep;
        const row: Record<string, number> = { t: Math.round(t * 10) / 10 };
        proteinSeries.forEach((key) => {
          row[key] = Math.round(result.species[key][originalIndex] * 100) / 100;
        });
        return row;
      })
    : [];

  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>
      <aside style={{
        width: 240, flexShrink: 0,
        background: 'var(--surface-sidebar)', borderRight: '1px solid var(--border)',
        padding: '28px 20px', display: 'flex', flexDirection: 'column',
      }}>
        <div style={{ marginBottom: 40 }}>
          <div style={{ fontSize: 18, fontWeight: 600, letterSpacing: '-0.01em' }}>BioCompiler</div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4, lineHeight: 1.5 }}>
            Live gene circuit simulation
          </div>
        </div>

        <div style={{ fontSize: 11, color: 'var(--text-muted)', letterSpacing: '0.08em', marginBottom: 12, textTransform: 'uppercase' }}>
          Circuits
        </div>
        <nav style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {CIRCUITS.map((c) => (
            <button
              key={c.id}
              onClick={() => setCircuitName(c.id)}
              className={`nav-item ${circuitName === c.id ? 'nav-item-active' : ''}`}
            >
              {c.label}
            </button>
          ))}
        </nav>

        <div style={{ fontSize: 11, color: 'var(--text-muted)', letterSpacing: '0.08em', marginTop: 32, marginBottom: 12, textTransform: 'uppercase' }}>
          Solver mode
        </div>
        <nav style={{ display: 'flex', flexDirection: 'column', gap: 2, marginBottom: 'auto' }}>
          <button onClick={() => setMode('deterministic')} className={`nav-item ${mode === 'deterministic' ? 'nav-item-active' : ''}`}>
            Deterministic (ODE)
          </button>
          <button onClick={() => setMode('stochastic')} className={`nav-item ${mode === 'stochastic' ? 'nav-item-active' : ''}`}>
            Stochastic (Gillespie)
          </button>
        </nav>
        <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
          Kernel v1 · repress / activate
        </div>
      </aside>

      <main style={{ flex: 1, padding: '32px 40px' }}>
        {loading && <p style={{ color: 'var(--text-secondary)' }}>Running simulation...</p>}
        {error && (
          <p style={{ color: '#ff8a8a' }}>{friendlyError(error)}</p>
        )}

        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))',
          gap: 20,
          marginBottom: 24,
          maxWidth: 1400,
        }}>
          <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 10, padding: '16px 20px 8px' }}>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 8 }}>
              Circuit structure
            </div>
            <CircuitDiagram model={currentModel} />
          </div>

          <div style={{
            height: 360,
            background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 10, padding: '16px 20px',
          }}>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 8 }}>
              Expression over time
            </div>
            {result && !loading ? (
              <ResponsiveContainer width="100%" height="90%">
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                  <XAxis dataKey="t" stroke="var(--text-muted)" tick={{ fill: 'var(--text-secondary)', fontSize: 12 }} label={{ value: 'time', position: 'insideBottom', offset: -5, fill: 'var(--text-secondary)' }} />
                  <YAxis stroke="var(--text-muted)" tick={{ fill: 'var(--text-secondary)', fontSize: 12 }} label={{ value: 'protein level', angle: -90, position: 'insideLeft', fill: 'var(--text-secondary)' }} />
                  <Tooltip contentStyle={{ background: 'var(--surface-sidebar)', border: '1px solid var(--border-strong)', borderRadius: 8, fontFamily: 'IBM Plex Mono, monospace', fontSize: 12 }} />
                  {proteinSeries.map((key) => (
                    <Line key={key} type="monotone" dataKey={key} stroke={COLORS[key.replace('_protein', '')] || '#888'} dot={false} strokeWidth={2} />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <ChartSkeleton />
            )}
          </div>
        </div>

        <div style={{ maxWidth: 800 }}>
          <label htmlFor="instruction" style={{ display: 'block', marginBottom: 10, color: 'var(--text-secondary)', fontSize: 14 }}>
            Tell it what to change
          </label>
          <div style={{ display: 'flex', gap: 10 }}>
            <input
              id="instruction"
              type="text"
              value={instruction}
              onChange={(e) => setInstruction(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') handleEditSubmit(); }}
              placeholder="e.g. remove the repression from cI to lacI"
              className="input-field"
              disabled={editLoading || !currentModel}
            />
            <button
              onClick={handleEditSubmit}
              disabled={editLoading || !currentModel || !instruction.trim()}
              className="btn-primary"
            >
              {editLoading ? 'Thinking...' : 'Apply'}
            </button>
          </div>

          {editError && <p style={{ color: '#ff8a8a', marginTop: 14, fontSize: 14 }}>{friendlyError(editError)}</p>}

          {substitutionNote && (
            <div style={{
              marginTop: 16, padding: '14px 18px', borderRadius: 8,
              background: '#221d10', border: '1px solid #4a3d1a', color: '#e0c56b',
              fontSize: 14, lineHeight: 1.6,
            }}>
              <div style={{ fontWeight: 600, marginBottom: 4 }}>Outside supported mechanisms</div>
              Showing the nearest equivalent instead, since this system only simulates published,
              characterized regulatory types.
              <div className="mono" style={{ marginTop: 8, opacity: 0.85, fontSize: 13 }}>{substitutionNote}</div>
            </div>
          )}

          {explanation && (
            <div style={{
              marginTop: 16, padding: '14px 18px', borderRadius: 8,
              background: '#0f1a20', border: '1px solid #1e3a45', color: '#d5e6ec',
              fontSize: 14, lineHeight: 1.65,
            }}>
              {explanation}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

export default App;