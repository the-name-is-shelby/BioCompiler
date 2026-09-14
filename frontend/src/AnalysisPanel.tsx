import { useState, type ReactNode } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';

type ModelJson = { parts: { id: string; [key: string]: unknown }[]; edges: { from: string; to: string; type: string }[] };

type StabilityResult = {
  equilibrium_found: boolean;
  reason?: string;
  residual?: number;
  verdict?: string;
  max_real_eigenvalue?: number;
  complex_eigenvalues_present?: boolean;
  equilibrium_state?: Record<string, { mRNA: number; protein: number }>;
};
type SweepPoint = { parameter_value: number; final?: number; amplitude?: number; stability: string };
type BifPoint = { parameter_value: number; n_stable_branches: number; branches: Record<string, number>[] };
type NullPoint = { x: number; y: number };
type PhasePortrait = {
  gene_x: string;
  gene_y: string;
  vector_field: { x: number; y: number; dx: number; dy: number }[];
  x_nullcline: NullPoint[];
  y_nullcline: NullPoint[];
  fixed_other_genes: Record<string, number>;
};

async function post(apiBase: string, path: string, body: unknown) {
  const res = await fetch(`${apiBase}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || `Request failed: ${res.status}`);
  return data;
}

const PARAMS = ['maxExpression', 'basalExpression', 'hillCoeff', 'degradationRate', 'halfMaxConst'];

function Card({ children }: { children: ReactNode }) {
  return (
    <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 10, padding: '18px 20px', marginTop: 16 }}>
      {children}
    </div>
  );
}

function ErrBox({ msg }: { msg: string }) {
  return <p style={{ color: '#ff8a8a', marginTop: 10, fontSize: 14 }}>{msg}</p>;
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{label}</span>
      {children}
    </div>
  );
}

export default function AnalysisPanel({ model, apiBase }: { model: ModelJson | null; apiBase: string }) {
  const [tab, setTab] = useState<'stability' | 'sweep' | 'bifurcation' | 'phase'>('stability');
  const geneIds = model ? model.parts.map((p) => p.id) : [];

  // --- Stability ---
  const [stab, setStab] = useState<StabilityResult | null>(null);
  const [stabErr, setStabErr] = useState<string | null>(null);
  const [stabLoading, setStabLoading] = useState(false);
  async function runStability() {
    if (!model) return;
    setStabLoading(true); setStabErr(null); setStab(null);
    try { setStab(await post(apiBase, '/stability', model)); }
    catch (e) { setStabErr(e instanceof Error ? e.message : 'Unknown error'); }
    finally { setStabLoading(false); }
  }

  // --- Sensitivity Sweep ---
  const [sweepPart, setSweepPart] = useState('ALL');
  const [sweepParam, setSweepParam] = useState('maxExpression');
  const [sweepValues, setSweepValues] = useState('50,100,150,200,250,300');
  const [sweepSpecies, setSweepSpecies] = useState('');
  const [sweep, setSweep] = useState<SweepPoint[] | null>(null);
  const [sweepErr, setSweepErr] = useState<string | null>(null);
  const [sweepLoading, setSweepLoading] = useState(false);
  async function runSweep() {
    if (!model) return;
    setSweepLoading(true); setSweepErr(null); setSweep(null);
    try {
      const values = sweepValues.split(',').map((v) => parseFloat(v.trim())).filter((v) => !isNaN(v));
      const data = await post(apiBase, '/sensitivity_sweep', {
        model, target_part_id: sweepPart, target_param: sweepParam, values,
        output_species: sweepSpecies || null,
      });
      setSweep(data.sweep);
    } catch (e) { setSweepErr(e instanceof Error ? e.message : 'Unknown error'); }
    finally { setSweepLoading(false); }
  }

  // --- Bifurcation ---
  const [bifPart, setBifPart] = useState('ALL');
  const [bifParam, setBifParam] = useState('maxExpression');
  const [bifValues, setBifValues] = useState('50,100,150,200,250,300');
  const [bif, setBif] = useState<BifPoint[] | null>(null);
  const [bifErr, setBifErr] = useState<string | null>(null);
  const [bifLoading, setBifLoading] = useState(false);
  async function runBifurcation() {
    if (!model) return;
    setBifLoading(true); setBifErr(null); setBif(null);
    try {
      const values = bifValues.split(',').map((v) => parseFloat(v.trim())).filter((v) => !isNaN(v));
      const data = await post(apiBase, '/bifurcation_diagram', { model, target_part_id: bifPart, target_param: bifParam, values });
      setBif(data.bifurcation);
    } catch (e) { setBifErr(e instanceof Error ? e.message : 'Unknown error'); }
    finally { setBifLoading(false); }
  }

  // --- Phase Portrait ---
  const [geneX, setGeneX] = useState('');
  const [geneY, setGeneY] = useState('');
  const [gridN, setGridN] = useState(20);
  const [phase, setPhase] = useState<PhasePortrait | null>(null);
  const [phaseErr, setPhaseErr] = useState<string | null>(null);
  const [phaseLoading, setPhaseLoading] = useState(false);
  async function runPhase() {
    if (!model || !geneX || !geneY) return;
    setPhaseLoading(true); setPhaseErr(null); setPhase(null);
    try { setPhase(await post(apiBase, '/phase_portrait', { model, gene_x: geneX, gene_y: geneY, grid_n: gridN })); }
    catch (e) { setPhaseErr(e instanceof Error ? e.message : 'Unknown error'); }
    finally { setPhaseLoading(false); }
  }

  if (!model) return null;

  return (
    <Card>
      <div style={{ fontSize: 11, color: 'var(--text-muted)', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 14 }}>
        Stats / Stability analysis
      </div>

      {/* Tabs: underline style, deliberately NOT btn-primary so they read as
          navigation, not as the action button below them. */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 16, borderBottom: '1px solid var(--border)' }}>
        {(['stability', 'sweep', 'bifurcation', 'phase'] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            style={{
              background: 'transparent',
              border: 'none',
              borderBottom: tab === t ? '2px solid #4a90d9' : '2px solid transparent',
              color: tab === t ? '#ffffff' : 'var(--text-muted)',
              fontWeight: tab === t ? 600 : 400,
              padding: '8px 14px',
              cursor: 'pointer',
              fontSize: 14,
              marginBottom: -1,
            }}
          >
            {t === 'stability' ? 'Stability' : t === 'sweep' ? 'Sensitivity sweep' : t === 'bifurcation' ? 'Bifurcation' : 'Phase portrait'}
          </button>
        ))}
      </div>

      {tab === 'stability' && (
        <div>
          <button className="btn-primary" onClick={runStability} disabled={stabLoading}>
            {stabLoading ? 'Running...' : 'Run stability analysis'}
          </button>
          {stabErr && <ErrBox msg={stabErr} />}
          {stab && (
            <div style={{ marginTop: 14, fontSize: 14, color: 'var(--text-secondary)' }}>
              {stab.equilibrium_found === false ? (
                <p>No equilibrium found — {stab.reason} (residual: {stab.residual})</p>
              ) : (
                <>
                  <p>
                    <b style={{ color: stab.verdict === 'stable' ? '#33d6a6' : stab.verdict === 'unstable' ? '#ff8a5c' : '#e0c56b' }}>
                      {stab.verdict?.toUpperCase()}
                    </b>
                    {' '}— max real eigenvalue: {stab.max_real_eigenvalue}, complex eigenvalues: {String(stab.complex_eigenvalues_present)}
                  </p>
                  <table style={{ marginTop: 8, fontSize: 13 }}>
                    <thead>
                      <tr><th style={{ textAlign: 'left', paddingRight: 16 }}>Gene</th><th style={{ paddingRight: 16 }}>mRNA</th><th>Protein</th></tr>
                    </thead>
                    <tbody>
                      {Object.entries(stab.equilibrium_state ?? {}).map(([gid, v]) => (
                        <tr key={gid}><td style={{ paddingRight: 16 }}>{gid}</td><td style={{ paddingRight: 16 }}>{v.mRNA}</td><td>{v.protein}</td></tr>
                      ))}
                    </tbody>
                  </table>
                </>
              )}
            </div>
          )}
        </div>
      )}

      {tab === 'sweep' && (
        <div>
          <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', alignItems: 'flex-end' }}>
            <Field label="Target gene (which gene's parameter to vary)">
              <select className="input-field" value={sweepPart} onChange={(e) => setSweepPart(e.target.value)}>
                <option value="ALL">ALL genes (vary together, keeps symmetry)</option>
                {geneIds.map((g) => <option key={g} value={g}>{g}</option>)}
              </select>
            </Field>
            <Field label="Parameter to vary">
              <select className="input-field" value={sweepParam} onChange={(e) => setSweepParam(e.target.value)}>
                {PARAMS.map((p) => <option key={p} value={p}>{p}</option>)}
              </select>
            </Field>
            <Field label="Values to test (comma-separated)">
              <input className="input-field" style={{ width: 220 }} value={sweepValues} onChange={(e) => setSweepValues(e.target.value)} placeholder="e.g. 50,100,150,200" />
            </Field>
            <Field label="Species to chart (optional)">
              <select className="input-field" value={sweepSpecies} onChange={(e) => setSweepSpecies(e.target.value)}>
                <option value="">— none, table only —</option>
                {geneIds.flatMap((g) => [`${g}_mRNA`, `${g}_protein`]).map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </Field>
            <button className="btn-primary" onClick={runSweep} disabled={sweepLoading}>{sweepLoading ? 'Running...' : 'Run sweep'}</button>
          </div>
          {sweepErr && <ErrBox msg={sweepErr} />}
          {sweep && (
            <>
              {sweepSpecies && (
                <div style={{ height: 260, marginTop: 16 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={sweep}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                      <XAxis dataKey="parameter_value" stroke="var(--text-muted)" label={{ value: `${sweepParam} value`, position: 'insideBottom', offset: -5, fill: 'var(--text-muted)' }} />
                      <YAxis stroke="var(--text-muted)" />
                      <Tooltip />
                      <Legend />
                      <Line type="monotone" dataKey="final" stroke="#4a90d9" name="final value" />
                      <Line type="monotone" dataKey="amplitude" stroke="#ff8a5c" name="amplitude" />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )}
              <table style={{ marginTop: 12, fontSize: 13 }}>
                <thead><tr><th style={{ textAlign: 'left', paddingRight: 16 }}>{sweepParam} value</th><th>Stability</th></tr></thead>
                <tbody>
                  {sweep.map((row, i) => (
                    <tr key={i}><td style={{ paddingRight: 16 }}>{row.parameter_value}</td><td>{row.stability}</td></tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </div>
      )}

      {tab === 'bifurcation' && (
        <div>
          <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', alignItems: 'flex-end' }}>
            <Field label="Target gene (which gene's parameter to vary)">
              <select className="input-field" value={bifPart} onChange={(e) => setBifPart(e.target.value)}>
                <option value="ALL">ALL genes (vary together, keeps symmetry)</option>
                {geneIds.map((g) => <option key={g} value={g}>{g}</option>)}
              </select>
            </Field>
            <Field label="Parameter to vary">
              <select className="input-field" value={bifParam} onChange={(e) => setBifParam(e.target.value)}>
                {PARAMS.map((p) => <option key={p} value={p}>{p}</option>)}
              </select>
            </Field>
            <Field label="Values to test (comma-separated)">
              <input className="input-field" style={{ width: 220 }} value={bifValues} onChange={(e) => setBifValues(e.target.value)} placeholder="e.g. 50,100,150,200" />
            </Field>
            <button className="btn-primary" onClick={runBifurcation} disabled={bifLoading}>{bifLoading ? 'Running...' : 'Run bifurcation scan'}</button>
          </div>
          {bifErr && <ErrBox msg={bifErr} />}
          {bif && (
            <div style={{ height: 220, marginTop: 16 }}>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 6 }}>
                # of distinct stable resting states found at each parameter value. 0 means the circuit never settles — e.g. an oscillator like the repressilator.
              </div>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={bif}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="parameter_value" stroke="var(--text-muted)" label={{ value: `${bifParam} value`, position: 'insideBottom', offset: -5, fill: 'var(--text-muted)' }} />
                  <YAxis allowDecimals={false} stroke="var(--text-muted)" label={{ value: '# stable branches', angle: -90, position: 'insideLeft', fill: 'var(--text-muted)' }} />
                  <Tooltip />
                  <Line type="stepAfter" dataKey="n_stable_branches" stroke="#33d6a6" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      )}

      {tab === 'phase' && (
        <div>
          <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', alignItems: 'flex-end' }}>
            <Field label="Gene X (horizontal axis)">
              <select className="input-field" value={geneX} onChange={(e) => setGeneX(e.target.value)}>
                <option value="">Select gene X</option>
                {geneIds.map((g) => <option key={g} value={g}>{g}</option>)}
              </select>
            </Field>
            <Field label="Gene Y (vertical axis)">
              <select className="input-field" value={geneY} onChange={(e) => setGeneY(e.target.value)}>
                <option value="">Select gene Y</option>
                {geneIds.map((g) => <option key={g} value={g}>{g}</option>)}
              </select>
            </Field>
            <Field label="Grid resolution">
              <input className="input-field" style={{ width: 80 }} type="number" value={gridN} onChange={(e) => setGridN(parseInt(e.target.value) || 20)} />
            </Field>
            <button className="btn-primary" onClick={runPhase} disabled={phaseLoading || !geneX || !geneY} style={{ opacity: (!geneX || !geneY) ? 0.5 : 1 }}>
              {phaseLoading ? 'Running...' : !geneX || !geneY ? 'Select both genes first' : 'Run phase portrait'}
            </button>
          </div>
          {phaseErr && <ErrBox msg={phaseErr} />}
          {phase && (
            <div style={{ height: 320, marginTop: 16 }}>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 6 }}>
                Nullclines shown (intersections = fixed points). Full vector field ({phase.vector_field.length} points) is in the response if you want a quiver overlay later.
              </div>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis type="number" dataKey="x" stroke="var(--text-muted)" label={{ value: geneX, position: 'insideBottom', fill: 'var(--text-muted)', offset: -5 }} />
                  <YAxis type="number" dataKey="y" stroke="var(--text-muted)" label={{ value: geneY, angle: -90, position: 'insideLeft', fill: 'var(--text-muted)' }} />
                  <Tooltip />
                  <Legend />
                  <Line
                    data={[...phase.x_nullcline].sort((a: NullPoint, b: NullPoint) => a.x - b.x)}
                    dataKey="y"
                    type="monotone"
                    stroke="#4a90d9"
                    dot={false}
                    name={`${geneX} nullcline`}
                  />
                  <Line
                    data={[...phase.y_nullcline].sort((a: NullPoint, b: NullPoint) => a.x - b.x)}
                    dataKey="y"
                    type="monotone"
                    stroke="#ff8a5c"
                    dot={false}
                    name={`${geneY} nullcline`}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}