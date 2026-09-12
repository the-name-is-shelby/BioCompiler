import { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import './App.css';

const API_BASE = 'http://127.0.0.1:8000';
const COLORS: Record<string, string> = {
  lacI: '#2a78d6', tetR: '#eb6834', cI: '#1baf7a',
  geneU: '#2a78d6', geneV: '#eb6834',
  geneX: '#2a78d6', geneY: '#eb6834', geneZ: '#1baf7a',
};

type SimResult = {
  t: number[];
  species: Record<string, number[]>;
  success: boolean;
};

function App() {
  const [circuitName, setCircuitName] = useState('repressilator');
  const [result, setResult] = useState<SimResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function run() {
      setLoading(true);
      setError(null);
      try {
        const modelRes = await fetch(`${API_BASE}/circuits/${circuitName}`);
        if (!modelRes.ok) throw new Error(`Failed to load circuit: ${modelRes.status}`);
        const model = await modelRes.json();

        const simRes = await fetch(`${API_BASE}/simulate`, {
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
}, [circuitName]);

  const proteinSeries = result
    ? Object.keys(result.species).filter((k) => k.endsWith('_protein'))
    : [];

  const chartData = result
    ? result.t.map((t, i) => {
        const row: Record<string, number> = { t: Math.round(t * 10) / 10 };
        proteinSeries.forEach((key) => {
          row[key] = Math.round(result.species[key][i] * 100) / 100;
        });
        return row;
      })
    : [];

  return (
    <div style={{ maxWidth: 900, margin: '0 auto', padding: '2rem', fontFamily: 'sans-serif' }}>
      <div style={{ display: 'flex', gap: 8, marginBottom: 24 }}>
        {['repressilator', 'toggle', 'feedforward'].map((name) => (
          <button
            key={name}
            onClick={() => setCircuitName(name)}
            style={{
              padding: '8px 16px',
              fontWeight: circuitName === name ? 700 : 400,
              background: circuitName === name ? '#2a78d6' : '#eee',
              color: circuitName === name ? '#fff' : '#333',
              border: 'none',
              borderRadius: 6,
              cursor: 'pointer',
            }}
          >
            {name}
          </button>
        ))}
      </div>

      {loading && <p>Running simulation...</p>}
      {error && (
        <p style={{ color: 'red' }}>
          Error: {error}. Is the backend running at {API_BASE}?
        </p>
      )}

      {result && !loading && (
        <div style={{ height: 400, width: '100%', maxWidth: 800 }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#333" vertical={false} />
              <XAxis dataKey="t" label={{ value: 'time', position: 'insideBottom', offset: -5 }} />
              <YAxis label={{ value: 'protein level', angle: -90, position: 'insideLeft' }} />
              <Tooltip />
              {proteinSeries.map((key) => (
                <Line
                  key={key}
                  type="monotone"
                  dataKey={key}
                  stroke={COLORS[key.replace('_protein', '')] || '#888'}
                  dot={false}
                  strokeWidth={2}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}

export default App;