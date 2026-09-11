import React, { useMemo, useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  LineChart, Line, ComposedChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, ReferenceLine, Scatter, ScatterChart, ZAxis,
} from 'recharts';
import { getCowMockData } from '../utils/researchMocks';

const LFT_COLOR = { Visible: '#16a34a', 'Faint, but visible': '#f59e0b', 'Not visible': '#dc2626', Invalid: '#9ca3af' };
const LFT_BG   = { Visible: 'bg-green-50 border-green-200 text-green-800', 'Faint, but visible': 'bg-amber-50 border-amber-200 text-amber-800', 'Not visible': 'bg-red-50 border-red-200 text-red-700', Invalid: 'bg-gray-50 border-gray-200 text-gray-500' };
const LFT_OPTIONS = ['Visible', 'Faint, but visible', 'Not visible', 'Invalid'];
const HEALTH_TYPES = ['Vaccination', 'Treatment', 'Examination', 'Surgery', 'Other'];
const TICK_INTERVAL = (n) => Math.max(1, Math.floor(n / 8));

function Badge({ result }) {
  return (
    <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-semibold border ${LFT_BG[result] || LFT_BG.Invalid}`}>
      {result}
    </span>
  );
}

function StatCard({ label, value, sub, color = 'text-blue-700' }) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <p className="text-xs text-gray-500 font-medium">{label}</p>
      <p className={`text-2xl font-bold mt-1 ${color}`}>{value}</p>
      {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
    </div>
  );
}

// ── Progesterone Cycle Chart ───────────────────────────────────────────────────
const LFT_P4_VALUE = { Visible: 22, 'Faint, but visible': 8, 'Not visible': 1.5, Invalid: null };

function P4CycleChart({ ts, p4Tests }) {
  const chartData = useMemo(() => {
    if (!ts.length) return [];
    // Build estrus day index from heat detection events
    const estrus = ts.reduce((acc, d, i) => { if (d.hd > 0) acc.push(i); return acc; }, []);
    return ts.map((d, i) => {
      // Distance to nearest estrus in days
      const dist = estrus.length
        ? Math.min(...estrus.map(e => Math.abs(i - e)))
        : 21;
      // Model: trough at estrus (~1 ng/mL), peak luteal day 8–12 (~22 ng/mL), drop day 18+
      let p4;
      if (dist <= 1) p4 = 1.0 + (i % 3) * 0.2;
      else if (dist <= 8) p4 = 1 + (dist / 8) * 19;
      else if (dist <= 13) p4 = 20 + ((dist - 8) % 3) * 1.5;
      else p4 = Math.max(1.5, 22 - (dist - 13) * 2.8);
      return { date: d.date, p4: parseFloat(p4.toFixed(1)) };
    });
  }, [ts]);

  // LFT test overlay points
  const lftPoints = useMemo(() =>
    p4Tests
      .map(t => ({ date: t.date, val: LFT_P4_VALUE[t.result], result: t.result }))
      .filter(t => t.val !== null),
    [p4Tests]
  );

  const TICK = Math.max(1, Math.floor(chartData.length / 8));

  const CustomDot = (props) => {
    const { cx, cy, payload } = props;
    if (!payload?.isLft) return null;
    const color = LFT_COLOR[payload.result] || '#9ca3af';
    return <circle cx={cx} cy={cy} r={5} fill={color} stroke="#fff" strokeWidth={1.5} />;
  };

  // Merge LFT points into chart data for overlay line
  const merged = chartData.map(d => {
    const lft = lftPoints.find(l => l.date === d.date);
    return { ...d, lftVal: lft ? lft.val : null, lftResult: lft?.result, isLft: !!lft };
  });

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-5">
      <div className="flex items-start justify-between mb-1">
        <p className="text-sm font-semibold text-gray-900">Progesterone Cycle — Estimated</p>
        <div className="flex items-center gap-3 text-xs text-gray-400">
          {Object.entries(LFT_COLOR).map(([k, c]) => (
            <span key={k} className="flex items-center gap-1">
              <span className="w-2.5 h-2.5 rounded-full inline-block" style={{ background: c }} />
              {k}
            </span>
          ))}
        </div>
      </div>
      <p className="text-xs text-gray-400 mb-3">
        Modelled from Bodit heat-detection events · ng/mL · LFT test results overlaid as coloured dots
      </p>
      <ResponsiveContainer width="100%" height={180}>
        <ComposedChart data={merged} margin={{ top: 5, right: 10, left: -10, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis dataKey="date" tick={{ fontSize: 9 }} tickFormatter={d => d.slice(5)} interval={TICK} />
          <YAxis tick={{ fontSize: 10 }} domain={[0, 28]} unit=" ng/mL" width={60} />
          <Tooltip
            labelFormatter={d => `Date: ${d}`}
            formatter={(v, n, p) => {
              if (n === 'P4 (est.)') return [`${v} ng/mL`, 'P4 (est.)'];
              if (n === 'LFT') return [`${v} ng/mL — ${p.payload.lftResult}`, 'LFT result'];
              return [v, n];
            }}
          />
          <ReferenceLine y={5} stroke="#dc2626" strokeDasharray="3 3" label={{ value: 'Estrus', fontSize: 9, fill: '#dc2626', position: 'insideTopLeft' }} />
          <ReferenceLine y={16} stroke="#16a34a" strokeDasharray="3 3" label={{ value: 'Luteal', fontSize: 9, fill: '#16a34a', position: 'insideTopLeft' }} />
          <Line type="monotone" dataKey="p4" name="P4 (est.)" stroke="#8b5cf6" dot={false} strokeWidth={2} />
          <Scatter dataKey="lftVal" name="LFT" shape={<CustomDot />} fill="#16a34a" />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

// ── Editable P4 LFT Panel ─────────────────────────────────────────────────────
function P4Panel({ records, onSave }) {
  const [items, setItems] = useState(records);
  const [editIdx, setEditIdx] = useState(null);
  const [draft, setDraft] = useState(null);
  const [adding, setAdding] = useState(false);
  const [newItem, setNewItem] = useState({ date: '', result: 'Visible', notes: '' });

  useEffect(() => { setItems(records); }, [records]);

  const startEdit = (i) => { setEditIdx(i); setDraft({ ...items[i] }); setAdding(false); };
  const cancelEdit = () => { setEditIdx(null); setDraft(null); };
  const saveEdit = () => {
    const next = items.map((it, i) => i === editIdx ? draft : it);
    setItems(next); setEditIdx(null); setDraft(null); onSave(next);
  };
  const deleteItem = (i) => {
    const next = items.filter((_, j) => j !== i);
    setItems(next); setEditIdx(null); onSave(next);
  };
  const addItem = () => {
    if (!newItem.date) return;
    const next = [newItem, ...items];
    setItems(next); setAdding(false); setNewItem({ date: '', result: 'Visible', notes: '' }); onSave(next);
  };

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-5">
      <div className="flex items-center justify-between mb-3">
        <p className="text-sm font-semibold text-gray-900">Progesterone LFT History</p>
        <button onClick={() => { setAdding(true); setEditIdx(null); }}
          className="text-xs text-blue-600 hover:text-blue-800 font-medium">+ Add</button>
      </div>

      {adding && (
        <div className="mb-3 rounded-lg border border-blue-200 bg-blue-50 p-3 space-y-2">
          <input type="date" value={newItem.date} onChange={e => setNewItem(p => ({ ...p, date: e.target.value }))}
            className="w-full text-xs border border-gray-200 rounded px-2 py-1" />
          <select value={newItem.result} onChange={e => setNewItem(p => ({ ...p, result: e.target.value }))}
            className="w-full text-xs border border-gray-200 rounded px-2 py-1">
            {LFT_OPTIONS.map(o => <option key={o}>{o}</option>)}
          </select>
          <input type="text" placeholder="Notes (e.g. High P4 — luteal phase)" value={newItem.notes}
            onChange={e => setNewItem(p => ({ ...p, notes: e.target.value }))}
            className="w-full text-xs border border-gray-200 rounded px-2 py-1" />
          <div className="flex gap-2">
            <button onClick={addItem} className="px-3 py-1 bg-blue-600 text-white text-xs rounded font-semibold">Save</button>
            <button onClick={() => setAdding(false)} className="px-3 py-1 text-xs text-gray-500">Cancel</button>
          </div>
        </div>
      )}

      <div className="space-y-1">
        {items.map((t, i) => editIdx === i ? (
          <div key={i} className="rounded-lg border border-blue-200 bg-blue-50 p-3 space-y-2">
            <input type="date" value={draft.date} onChange={e => setDraft(p => ({ ...p, date: e.target.value }))}
              className="w-full text-xs border border-gray-200 rounded px-2 py-1" />
            <select value={draft.result} onChange={e => setDraft(p => ({ ...p, result: e.target.value }))}
              className="w-full text-xs border border-gray-200 rounded px-2 py-1">
              {LFT_OPTIONS.map(o => <option key={o}>{o}</option>)}
            </select>
            <input type="text" value={draft.notes} onChange={e => setDraft(p => ({ ...p, notes: e.target.value }))}
              className="w-full text-xs border border-gray-200 rounded px-2 py-1" />
            <div className="flex gap-2">
              <button onClick={saveEdit} className="px-3 py-1 bg-blue-600 text-white text-xs rounded font-semibold">Save</button>
              <button onClick={cancelEdit} className="px-3 py-1 text-xs text-gray-500">Cancel</button>
              <button onClick={() => deleteItem(i)} className="ml-auto px-3 py-1 text-xs text-red-500 hover:text-red-700">Delete</button>
            </div>
          </div>
        ) : (
          <div key={i} className="group flex items-start justify-between gap-2 py-2 border-b border-gray-50 last:border-0">
            <div className="flex-1">
              <p className="text-xs text-gray-500">{t.date}</p>
              <p className="text-xs text-gray-400 mt-0.5">{t.notes}</p>
            </div>
            <div className="flex items-center gap-2">
              <Badge result={t.result} />
              <button onClick={() => startEdit(i)}
                className="opacity-0 group-hover:opacity-100 transition-opacity text-gray-400 hover:text-blue-600">
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                </svg>
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Editable Calving Panel ────────────────────────────────────────────────────
function CalvingPanel({ records, onSave }) {
  const [items, setItems] = useState(records);
  const [editIdx, setEditIdx] = useState(null);
  const [draft, setDraft] = useState(null);
  const [adding, setAdding] = useState(false);
  const [newItem, setNewItem] = useState({ lactation: '', date: '', calving: 'Normal', calf_sex: 'Heifer calf', peak_yield: '' });

  useEffect(() => { setItems(records); }, [records]);

  const startEdit = (i) => { setEditIdx(i); setDraft({ ...items[i] }); setAdding(false); };
  const cancelEdit = () => { setEditIdx(null); setDraft(null); };
  const saveEdit = () => {
    const next = items.map((it, i) => i === editIdx ? draft : it);
    setItems(next); setEditIdx(null); setDraft(null); onSave(next);
  };
  const deleteItem = (i) => {
    const next = items.filter((_, j) => j !== i);
    setItems(next); setEditIdx(null); onSave(next);
  };
  const addItem = () => {
    if (!newItem.date) return;
    const next = [...items, newItem];
    setItems(next); setAdding(false); setNewItem({ lactation: '', date: '', calving: 'Normal', calf_sex: 'Heifer calf', peak_yield: '' }); onSave(next);
  };

  const Field = ({ label, value, onChange, type = 'text' }) => (
    <div>
      <p className="text-xs text-gray-400 mb-0.5">{label}</p>
      <input type={type} value={value} onChange={e => onChange(e.target.value)}
        className="w-full text-xs border border-gray-200 rounded px-2 py-1" />
    </div>
  );

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-5">
      <div className="flex items-center justify-between mb-3">
        <p className="text-sm font-semibold text-gray-900">Calving History</p>
        <button onClick={() => { setAdding(true); setEditIdx(null); }}
          className="text-xs text-blue-600 hover:text-blue-800 font-medium">+ Add</button>
      </div>

      {adding && (
        <div className="mb-3 rounded-lg border border-blue-200 bg-blue-50 p-3 space-y-2">
          <div className="grid grid-cols-2 gap-2">
            <Field label="Lactation #" value={newItem.lactation} onChange={v => setNewItem(p => ({ ...p, lactation: v }))} />
            <Field label="Date" value={newItem.date} onChange={v => setNewItem(p => ({ ...p, date: v }))} type="date" />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <p className="text-xs text-gray-400 mb-0.5">Calving type</p>
              <select value={newItem.calving} onChange={e => setNewItem(p => ({ ...p, calving: e.target.value }))}
                className="w-full text-xs border border-gray-200 rounded px-2 py-1">
                {['Normal', 'Assisted', 'Caesarean', 'Stillbirth'].map(o => <option key={o}>{o}</option>)}
              </select>
            </div>
            <div>
              <p className="text-xs text-gray-400 mb-0.5">Calf sex</p>
              <select value={newItem.calf_sex} onChange={e => setNewItem(p => ({ ...p, calf_sex: e.target.value }))}
                className="w-full text-xs border border-gray-200 rounded px-2 py-1">
                {['Heifer calf', 'Bull calf', 'Twin — heifer/heifer', 'Twin — bull/bull', 'Twin — heifer/bull'].map(o => <option key={o}>{o}</option>)}
              </select>
            </div>
          </div>
          <Field label="Peak milk yield" value={newItem.peak_yield} onChange={v => setNewItem(p => ({ ...p, peak_yield: v }))} />
          <div className="flex gap-2">
            <button onClick={addItem} className="px-3 py-1 bg-blue-600 text-white text-xs rounded font-semibold">Save</button>
            <button onClick={() => setAdding(false)} className="px-3 py-1 text-xs text-gray-500">Cancel</button>
          </div>
        </div>
      )}

      <div className="space-y-1">
        {items.map((c, i) => editIdx === i ? (
          <div key={i} className="rounded-lg border border-blue-200 bg-blue-50 p-3 space-y-2">
            <div className="grid grid-cols-2 gap-2">
              <div>
                <p className="text-xs text-gray-400 mb-0.5">Lactation #</p>
                <input type="text" value={draft.lactation} onChange={e => setDraft(p => ({ ...p, lactation: e.target.value }))}
                  className="w-full text-xs border border-gray-200 rounded px-2 py-1" />
              </div>
              <div>
                <p className="text-xs text-gray-400 mb-0.5">Date</p>
                <input type="date" value={draft.date} onChange={e => setDraft(p => ({ ...p, date: e.target.value }))}
                  className="w-full text-xs border border-gray-200 rounded px-2 py-1" />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <p className="text-xs text-gray-400 mb-0.5">Type</p>
                <select value={draft.calving} onChange={e => setDraft(p => ({ ...p, calving: e.target.value }))}
                  className="w-full text-xs border border-gray-200 rounded px-2 py-1">
                  {['Normal', 'Assisted', 'Caesarean', 'Stillbirth'].map(o => <option key={o}>{o}</option>)}
                </select>
              </div>
              <div>
                <p className="text-xs text-gray-400 mb-0.5">Calf sex</p>
                <select value={draft.calf_sex} onChange={e => setDraft(p => ({ ...p, calf_sex: e.target.value }))}
                  className="w-full text-xs border border-gray-200 rounded px-2 py-1">
                  {['Heifer calf', 'Bull calf', 'Twin — heifer/heifer', 'Twin — bull/bull', 'Twin — heifer/bull'].map(o => <option key={o}>{o}</option>)}
                </select>
              </div>
            </div>
            <div>
              <p className="text-xs text-gray-400 mb-0.5">Peak milk yield</p>
              <input type="text" value={draft.peak_yield} onChange={e => setDraft(p => ({ ...p, peak_yield: e.target.value }))}
                className="w-full text-xs border border-gray-200 rounded px-2 py-1" />
            </div>
            <div className="flex gap-2">
              <button onClick={saveEdit} className="px-3 py-1 bg-blue-600 text-white text-xs rounded font-semibold">Save</button>
              <button onClick={cancelEdit} className="px-3 py-1 text-xs text-gray-500">Cancel</button>
              <button onClick={() => deleteItem(i)} className="ml-auto px-3 py-1 text-xs text-red-500 hover:text-red-700">Delete</button>
            </div>
          </div>
        ) : (
          <div key={i} className="group py-2 border-b border-gray-50 last:border-0">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-gray-700">Lactation {c.lactation}</span>
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-400">{c.date}</span>
                <button onClick={() => startEdit(i)}
                  className="opacity-0 group-hover:opacity-100 transition-opacity text-gray-400 hover:text-blue-600">
                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                  </svg>
                </button>
              </div>
            </div>
            <p className="text-xs text-gray-500 mt-0.5">{c.calving} · {c.calf_sex} · Peak {c.peak_yield}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Editable Health Records Panel ─────────────────────────────────────────────
function HealthPanel({ records, onSave }) {
  const [items, setItems] = useState(records);
  const [editIdx, setEditIdx] = useState(null);
  const [draft, setDraft] = useState(null);
  const [adding, setAdding] = useState(false);
  const [newItem, setNewItem] = useState({ type: 'Vaccination', date: '', description: '', vet: '' });

  useEffect(() => { setItems(records); }, [records]);

  const startEdit = (i) => { setEditIdx(i); setDraft({ ...items[i] }); setAdding(false); };
  const cancelEdit = () => { setEditIdx(null); setDraft(null); };
  const saveEdit = () => {
    const next = items.map((it, i) => i === editIdx ? draft : it);
    setItems(next); setEditIdx(null); setDraft(null); onSave(next);
  };
  const deleteItem = (i) => {
    const next = items.filter((_, j) => j !== i);
    setItems(next); setEditIdx(null); onSave(next);
  };
  const addItem = () => {
    if (!newItem.date || !newItem.description) return;
    const next = [newItem, ...items];
    setItems(next); setAdding(false); setNewItem({ type: 'Vaccination', date: '', description: '', vet: '' }); onSave(next);
  };

  const typeColor = (t) => t === 'Vaccination' ? 'bg-blue-50 text-blue-700' : t === 'Treatment' ? 'bg-orange-50 text-orange-700' : 'bg-gray-50 text-gray-600';

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-5">
      <div className="flex items-center justify-between mb-3">
        <p className="text-sm font-semibold text-gray-900">Health Records</p>
        <button onClick={() => { setAdding(true); setEditIdx(null); }}
          className="text-xs text-blue-600 hover:text-blue-800 font-medium">+ Add</button>
      </div>

      {adding && (
        <div className="mb-3 rounded-lg border border-blue-200 bg-blue-50 p-3 space-y-2">
          <div className="grid grid-cols-2 gap-2">
            <div>
              <p className="text-xs text-gray-400 mb-0.5">Type</p>
              <select value={newItem.type} onChange={e => setNewItem(p => ({ ...p, type: e.target.value }))}
                className="w-full text-xs border border-gray-200 rounded px-2 py-1">
                {HEALTH_TYPES.map(o => <option key={o}>{o}</option>)}
              </select>
            </div>
            <div>
              <p className="text-xs text-gray-400 mb-0.5">Date</p>
              <input type="date" value={newItem.date} onChange={e => setNewItem(p => ({ ...p, date: e.target.value }))}
                className="w-full text-xs border border-gray-200 rounded px-2 py-1" />
            </div>
          </div>
          <div>
            <p className="text-xs text-gray-400 mb-0.5">Description</p>
            <input type="text" placeholder="e.g. FMD Bivalent Vaccine" value={newItem.description}
              onChange={e => setNewItem(p => ({ ...p, description: e.target.value }))}
              className="w-full text-xs border border-gray-200 rounded px-2 py-1" />
          </div>
          <div>
            <p className="text-xs text-gray-400 mb-0.5">Veterinarian</p>
            <input type="text" placeholder="Dr. Name" value={newItem.vet}
              onChange={e => setNewItem(p => ({ ...p, vet: e.target.value }))}
              className="w-full text-xs border border-gray-200 rounded px-2 py-1" />
          </div>
          <div className="flex gap-2">
            <button onClick={addItem} className="px-3 py-1 bg-blue-600 text-white text-xs rounded font-semibold">Save</button>
            <button onClick={() => setAdding(false)} className="px-3 py-1 text-xs text-gray-500">Cancel</button>
          </div>
        </div>
      )}

      <div className="space-y-1">
        {items.map((r, i) => editIdx === i ? (
          <div key={i} className="rounded-lg border border-blue-200 bg-blue-50 p-3 space-y-2">
            <div className="grid grid-cols-2 gap-2">
              <div>
                <p className="text-xs text-gray-400 mb-0.5">Type</p>
                <select value={draft.type} onChange={e => setDraft(p => ({ ...p, type: e.target.value }))}
                  className="w-full text-xs border border-gray-200 rounded px-2 py-1">
                  {HEALTH_TYPES.map(o => <option key={o}>{o}</option>)}
                </select>
              </div>
              <div>
                <p className="text-xs text-gray-400 mb-0.5">Date</p>
                <input type="date" value={draft.date} onChange={e => setDraft(p => ({ ...p, date: e.target.value }))}
                  className="w-full text-xs border border-gray-200 rounded px-2 py-1" />
              </div>
            </div>
            <div>
              <p className="text-xs text-gray-400 mb-0.5">Description</p>
              <input type="text" value={draft.description} onChange={e => setDraft(p => ({ ...p, description: e.target.value }))}
                className="w-full text-xs border border-gray-200 rounded px-2 py-1" />
            </div>
            <div>
              <p className="text-xs text-gray-400 mb-0.5">Veterinarian</p>
              <input type="text" value={draft.vet} onChange={e => setDraft(p => ({ ...p, vet: e.target.value }))}
                className="w-full text-xs border border-gray-200 rounded px-2 py-1" />
            </div>
            <div className="flex gap-2">
              <button onClick={saveEdit} className="px-3 py-1 bg-blue-600 text-white text-xs rounded font-semibold">Save</button>
              <button onClick={cancelEdit} className="px-3 py-1 text-xs text-gray-500">Cancel</button>
              <button onClick={() => deleteItem(i)} className="ml-auto px-3 py-1 text-xs text-red-500 hover:text-red-700">Delete</button>
            </div>
          </div>
        ) : (
          <div key={i} className="group py-2 border-b border-gray-50 last:border-0">
            <div className="flex items-center justify-between gap-1">
              <span className={`text-xs font-semibold px-1.5 py-0.5 rounded ${typeColor(r.type)}`}>{r.type}</span>
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-400">{r.date}</span>
                <button onClick={() => startEdit(i)}
                  className="opacity-0 group-hover:opacity-100 transition-opacity text-gray-400 hover:text-blue-600">
                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                  </svg>
                </button>
              </div>
            </div>
            <p className="text-xs text-gray-600 mt-1">{r.description}</p>
            <p className="text-xs text-gray-400">{r.vet}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Computer Vision Identification Modal ──────────────────────────────────────
function CVModal({ cow, onClose }) {
  const [mode, setMode] = useState(null); // 'ear_tag' | 'coat'
  const [phase, setPhase] = useState('idle'); // idle | scanning | result
  const [dragOver, setDragOver] = useState(false);
  const fileRef = useRef();

  const tag = cow?.summary?.tag || '';
  const cowId = cow?.cow_id || '';

  // Deterministic mock confidence from cow_id hash
  const hash = cowId.split('').reduce((a, c) => a + c.charCodeAt(0), 0);
  const conf1 = 88 + (hash % 10);
  const conf2 = 70 + (hash % 15);
  const conf3 = 40 + (hash % 20);

  const scan = (m) => {
    setMode(m);
    setPhase('scanning');
    setTimeout(() => setPhase('result'), 2200);
  };

  const handleDrop = (e) => {
    e.preventDefault(); setDragOver(false);
    if (e.dataTransfer.files.length) scan(mode || 'ear_tag');
  };

  const handleFile = (e) => {
    if (e.target.files.length) scan(mode || 'ear_tag');
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={onClose}>
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-md p-6" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-base font-bold text-gray-900">Animal Identification</h2>
            <p className="text-xs text-gray-400 mt-0.5">Computer vision · AI-assisted ID</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {phase === 'idle' && (
          <>
            <p className="text-xs text-gray-500 mb-4">Select an identification method, then upload or drag an image.</p>
            <div className="grid grid-cols-2 gap-3 mb-4">
              <button onClick={() => setMode('ear_tag')}
                className={`rounded-lg border-2 p-3 text-left transition-all ${mode === 'ear_tag' ? 'border-blue-500 bg-blue-50' : 'border-gray-200 hover:border-blue-300'}`}>
                <svg className="w-5 h-5 mb-1 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" /></svg>
                <p className="text-xs font-semibold text-gray-800">Ear Tag OCR</p>
                <p className="text-xs text-gray-400 mt-0.5">Read tag number from image</p>
              </button>
              <button onClick={() => setMode('coat')}
                className={`rounded-lg border-2 p-3 text-left transition-all ${mode === 'coat' ? 'border-purple-500 bg-purple-50' : 'border-gray-200 hover:border-purple-300'}`}>
                <svg className="w-5 h-5 mb-1 text-purple-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
                <p className="text-xs font-semibold text-gray-800">Coat Pattern</p>
                <p className="text-xs text-gray-400 mt-0.5">Match markings to herd records</p>
              </button>
              <button onClick={() => setMode('muzzle')}
                className={`rounded-lg border-2 p-3 text-left transition-all ${mode === 'muzzle' ? 'border-green-500 bg-green-50' : 'border-gray-200 hover:border-green-300'}`}>
                <svg className="w-5 h-5 mb-1 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2V9M9 21H5a2 2 0 01-2-2V9m0 0h18" /></svg>
                <p className="text-xs font-semibold text-gray-800">Muzzle Print</p>
                <p className="text-xs text-gray-400 mt-0.5">Unique nose pattern biometric</p>
              </button>
              <button onClick={() => setMode('face')}
                className={`rounded-lg border-2 p-3 text-left transition-all ${mode === 'face' ? 'border-teal-500 bg-teal-50' : 'border-gray-200 hover:border-teal-300'}`}>
                <svg className="w-5 h-5 mb-1 text-teal-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.069A1 1 0 0121 8.882v6.236a1 1 0 01-1.447.894L15 14M3 8a2 2 0 012-2h8a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V8z" /></svg>
                <p className="text-xs font-semibold text-gray-800">Facial Recognition</p>
                <p className="text-xs text-gray-400 mt-0.5">Head profile identification</p>
              </button>
            </div>

            {mode && (
              <div
                className={`border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-all ${dragOver ? 'border-blue-400 bg-blue-50' : 'border-gray-200 hover:border-blue-300'}`}
                onDragOver={e => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={handleDrop}
                onClick={() => fileRef.current?.click()}
              >
                <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={handleFile} />
                <svg className="w-8 h-8 mx-auto mb-2 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" /></svg>
                <p className="text-xs font-semibold text-gray-700">Drop image here or click to upload</p>
                <p className="text-xs text-gray-400 mt-1">JPG, PNG, HEIC · max 10 MB</p>
                <button onClick={e => { e.stopPropagation(); scan(mode); }}
                  className="mt-3 px-4 py-1.5 bg-blue-600 text-white text-xs rounded-lg font-semibold hover:bg-blue-700">
                  Use Demo Image
                </button>
              </div>
            )}
          </>
        )}

        {phase === 'scanning' && (
          <div className="py-8 text-center">
            <div className="w-12 h-12 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
            <p className="text-sm font-semibold text-gray-700">
              {mode === 'ear_tag' ? 'Reading ear tag...' : mode === 'coat' ? 'Analysing coat pattern...' : mode === 'muzzle' ? 'Matching muzzle print...' : 'Running facial recognition...'}
            </p>
            <p className="text-xs text-gray-400 mt-1">Processing image with CV model</p>
          </div>
        )}

        {phase === 'result' && (
          <div className="space-y-4">
            <div className="rounded-lg bg-green-50 border border-green-200 p-4">
              <div className="flex items-center gap-2 mb-2">
                <span className="w-2 h-2 rounded-full bg-green-500" />
                <p className="text-xs font-bold text-green-800 uppercase tracking-wide">Match Found</p>
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-lg font-bold text-gray-900 font-mono">{cowId}</p>
                  <p className="text-xs text-gray-500">Tag: {tag} · {cow?.breed}</p>
                </div>
                <div className="text-right">
                  <p className="text-2xl font-bold text-green-700">{conf1}%</p>
                  <p className="text-xs text-gray-400">confidence</p>
                </div>
              </div>
            </div>

            <div>
              <p className="text-xs font-semibold text-gray-500 mb-2 uppercase tracking-wide">Top Matches</p>
              <div className="space-y-2">
                {[{ id: cowId, tag, conf: conf1 }, { id: 'COW-1000' + ((hash + 1) % 20 + 245), tag: String(10000 + ((hash + 3) % 20)), conf: conf2 }, { id: 'COW-1000' + ((hash + 2) % 20 + 245), tag: String(10000 + ((hash + 7) % 20)), conf: conf3 }].map((m, i) => (
                  <div key={i} className="flex items-center gap-3">
                    <div className="flex-1">
                      <div className="flex items-center justify-between mb-0.5">
                        <span className="text-xs font-mono text-gray-700">{m.id}</span>
                        <span className="text-xs font-semibold text-gray-700">{m.conf}%</span>
                      </div>
                      <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                        <div className="h-full rounded-full" style={{ width: `${m.conf}%`, background: i === 0 ? '#16a34a' : i === 1 ? '#f59e0b' : '#d1d5db' }} />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {mode === 'ear_tag' && (
              <div className="rounded-lg bg-gray-50 border border-gray-200 p-3">
                <p className="text-xs font-semibold text-gray-600 mb-1">OCR Output</p>
                <p className="text-sm font-mono text-gray-800">Tag detected: <span className="text-blue-700 font-bold">{tag}</span></p>
                <p className="text-xs text-gray-400 mt-0.5">Character confidence: 99.2% · No corrections applied</p>
              </div>
            )}
            {(mode === 'coat' || mode === 'muzzle' || mode === 'face') && (
              <div className="rounded-lg bg-gray-50 border border-gray-200 p-3">
                <p className="text-xs font-semibold text-gray-600 mb-1">Analysis Output</p>
                <p className="text-xs text-gray-700">{mode === 'coat' ? 'Coat markings segmented: 12 key regions · Right flank match: 91%' : mode === 'muzzle' ? 'Muzzle print points: 847 · Biometric hash matched' : 'Facial landmarks detected: 34 · Profile angle: 12°'}</p>
              </div>
            )}

            <div className="flex gap-2">
              <button onClick={() => { setPhase('idle'); setMode(null); }}
                className="flex-1 px-3 py-2 border border-gray-200 rounded-lg text-xs font-semibold text-gray-600 hover:bg-gray-50">
                Try Again
              </button>
              <button onClick={onClose}
                className="flex-1 px-3 py-2 bg-blue-600 text-white rounded-lg text-xs font-semibold hover:bg-blue-700">
                Confirm Match
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Cow Photo Upload ──────────────────────────────────────────────────────────
function CowPhoto({ cowId }) {
  const key = `cow_photo_${cowId}`;
  const [src, setSrc] = useState(() => localStorage.getItem(key) || null);
  const inputRef = useRef();

  const handleFile = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      localStorage.setItem(key, ev.target.result);
      setSrc(ev.target.result);
    };
    reader.readAsDataURL(file);
  };

  return (
    <div className="relative flex-shrink-0 cursor-pointer group" onClick={() => inputRef.current?.click()}>
      <input ref={inputRef} type="file" accept="image/*" className="hidden" onChange={handleFile} />
      <div className="w-24 h-24 rounded-xl border-2 border-dashed border-gray-200 bg-gray-50 overflow-hidden flex items-center justify-center group-hover:border-blue-400 transition-colors">
        {src ? (
          <img src={src} alt="Cow photo" className="w-full h-full object-cover" />
        ) : (
          <div className="text-center p-2">
            <svg className="w-7 h-7 mx-auto text-gray-300 mb-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            <p className="text-xs text-gray-400 leading-tight">Add photo</p>
          </div>
        )}
      </div>
      {src && (
        <button
          onClick={e => { e.stopPropagation(); localStorage.removeItem(key); setSrc(null); }}
          className="absolute -top-1.5 -right-1.5 w-5 h-5 bg-red-500 text-white rounded-full text-xs flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity font-bold leading-none"
        >
          ×
        </button>
      )}
    </div>
  );
}

// ── Main Component ────────────────────────────────────────────────────────────
export default function ResearchCowPassport() {
  const { cowId } = useParams();
  const navigate = useNavigate();
  const base = useMemo(() => getCowMockData(cowId), [cowId]);
  const [cvOpen, setCvOpen] = useState(false);

  useEffect(() => { window.scrollTo(0, 0); }, [cowId]);

  const storageKey = `passport_${cowId}`;
  const loadOverrides = () => {
    try { return JSON.parse(localStorage.getItem(storageKey) || '{}'); } catch { return {}; }
  };

  const [overrides, setOverrides] = useState(loadOverrides);

  const p4_tests = overrides.p4_tests ?? base.p4_tests;
  const calvings = overrides.calvings ?? base.calvings;
  const health_records = overrides.health_records ?? base.health_records;

  const saveOverride = (key, val) => {
    const next = { ...loadOverrides(), [key]: val };
    localStorage.setItem(storageKey, JSON.stringify(next));
    setOverrides(next);
  };

  if (!base.summary?.cow_id) {
    return (
      <div className="p-8 text-center">
        <p className="text-gray-500">Cow <span className="font-mono">{cowId}</span> not found.</p>
        <button onClick={() => navigate('/research')} className="mt-4 text-sm text-blue-600 hover:underline">← Back</button>
      </div>
    );
  }

  const { summary, ts, milk_yield } = base;
  const avgMilk = milk_yield.length ? (milk_yield.reduce((s, d) => s + Number(d.yield), 0) / milk_yield.length).toFixed(1) : '—';

  return (
    <>
      {cvOpen && <CVModal cow={base} onClose={() => setCvOpen(false)} />}

      <div className="p-6 space-y-5 max-w-5xl mx-auto">
        {/* Back */}
        <button onClick={() => navigate('/research')} className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-800 transition-colors">
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" /></svg>
          Back to Herd Monitoring
        </button>

        {/* Header */}
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <div className="flex items-start justify-between flex-wrap gap-4">
            <div className="flex items-start gap-4">
              <CowPhoto cowId={cowId} />
              <div>
              <div className="flex items-center gap-3 mb-1 flex-wrap">
                <h1 className="text-xl font-bold text-gray-900 font-mono">{base.cow_id}</h1>
                <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold ${base.status === 'Lactating' ? 'bg-green-100 text-green-800' : 'bg-amber-100 text-amber-800'}`}>{base.status}</span>
                <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-100 text-blue-800">Lactation {base.lactation_number}</span>
                <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-gray-100 text-gray-700">Tag: {summary.tag}</span>
              </div>
              <p className="text-base font-semibold text-gray-700">{base.breed}</p>
              <p className="text-sm text-gray-500 mt-0.5">DOB: {base.dob} · Age: {base.age_years} yrs · DIM: {base.dim} · Sire: {base.sire} · Dam: {base.dam}</p>
              </div>
            </div>
            <div className="flex flex-col items-end gap-2">
              <button onClick={() => setCvOpen(true)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 text-white text-xs font-semibold hover:bg-indigo-700 transition-colors shadow-sm">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.069A1 1 0 0121 8.882v6.236a1 1 0 01-1.447.894L15 14M3 8a2 2 0 012-2h8a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V8z" />
                </svg>
                Identify Animal
              </button>
              <div className="text-right text-sm text-gray-500">
                <p className="text-xs font-semibold text-gray-700 uppercase tracking-wide">Latest Reading</p>
                <p className="text-sm text-gray-500">{summary.latest_date}</p>
                <p className="text-sm mt-0.5"><span className="font-semibold text-blue-700">{summary.latest_activity}%</span> activity</p>
                <p className="text-sm"><span className="font-semibold text-green-700">{summary.latest_rumination} min</span> rumination</p>
                <p className="mt-1 text-xs text-gray-400">Bodit Sensor · {summary.date_first} – {summary.date_last} · {summary.n_days} days</p>
              </div>
            </div>
          </div>
        </div>

        {/* KPIs */}
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
          <StatCard label="Avg Activity Rate" value={`${Number(summary.avg_activity_rate).toFixed(1)}%`} sub={`Latest: ${summary.latest_activity}%`} color="text-blue-700" />
          <StatCard label="Avg Rumination" value={`${Number(summary.avg_rumination_min).toFixed(0)} min/day`} sub={`Latest: ${summary.latest_rumination} min`} color="text-green-700" />
          <StatCard label="Avg Eating" value={`${Number(summary.avg_eating_min).toFixed(0)} min/day`} sub="daily average · sensor period" color="text-teal-700" />
          <StatCard label="Heat Detections" value={summary.total_heat_detections} sub="events · full period" color="text-purple-700" />
          <StatCard label="Total Mounting" value={summary.total_mounting.toLocaleString()} sub="events · full period" color="text-violet-700" />
          <StatCard label="Total Coughing" value={summary.total_coughing.toLocaleString()} sub="events · full period" color="text-orange-700" />
        </div>

        {/* Milk yield */}
        <div className="bg-white rounded-lg border border-gray-200 p-5">
          <p className="text-sm font-semibold text-gray-900 mb-1">Milk Yield — Last 90 Days</p>
          <p className="text-xs text-gray-400 mb-3">Daily production · lactation {base.lactation_number} · DIM {base.dim - 90}–{base.dim}</p>
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={milk_yield} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="date" tick={{ fontSize: 9 }} tickFormatter={d => d.slice(5)} interval={9} />
              <YAxis tick={{ fontSize: 10 }} unit=" L" domain={['auto', 'auto']} />
              <Tooltip formatter={(v) => [`${v} L`, 'Milk yield']} labelFormatter={d => `Date: ${d}`} />
              <ReferenceLine y={Number(avgMilk)} stroke="#6366f1" strokeDasharray="4 4"
                label={{ value: `Avg ${avgMilk}L`, fontSize: 10, fill: '#6366f1', position: 'right' }} />
              <Line type="monotone" dataKey="yield" name="Milk yield (L)" stroke="#10b981" dot={false} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Activity + Rumination */}
        <div className="bg-white rounded-lg border border-gray-200 p-5">
          <p className="text-sm font-semibold text-gray-900 mb-1">Activity Rate & Rumination — Full Sensor Range</p>
          <p className="text-xs text-gray-400 mb-3">
            {summary.date_first} – {summary.date_last} · {ts.length} observation days ·
            avg eating: <span className="font-medium text-teal-700">{Number(summary.avg_eating_min).toFixed(0)} min/day</span>
          </p>
          <ResponsiveContainer width="100%" height={210}>
            <LineChart data={ts} margin={{ top: 5, right: 45, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="date" tick={{ fontSize: 9 }} tickFormatter={d => d.slice(5)} interval={TICK_INTERVAL(ts.length)} />
              <YAxis yAxisId="l" tick={{ fontSize: 10 }} domain={[0, 100]} />
              <YAxis yAxisId="r" orientation="right" tick={{ fontSize: 10 }} />
              <Tooltip labelFormatter={d => `Date: ${d}`} formatter={(v, n) => [Number(v).toFixed(1), n]} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <ReferenceLine yAxisId="r" y={Number(summary.avg_eating_min)} stroke="#0d9488" strokeDasharray="5 3"
                label={{ value: `Eat avg ${Number(summary.avg_eating_min).toFixed(0)}min`, fontSize: 9, fill: '#0d9488', position: 'right' }} />
              <Line yAxisId="l" type="monotone" dataKey="ar" name="Activity %" stroke="#3b82f6" dot={false} strokeWidth={1.5} />
              <Line yAxisId="r" type="monotone" dataKey="rum" name="Rumination (min)" stroke="#10b981" dot={false} strokeWidth={1.5} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Mounting + Heat Detection */}
        <div className="bg-white rounded-lg border border-gray-200 p-5">
          <p className="text-sm font-semibold text-gray-900 mb-1">Mounting & Heat Detection Events — Full Sensor Range</p>
          <p className="text-xs text-gray-400 mb-3">
            {summary.date_first} – {summary.date_last} · total: <span className="font-semibold text-violet-700">{summary.total_mounting.toLocaleString()} mounting</span> · <span className="font-semibold text-purple-700 ml-1">{summary.total_heat_detections} heat detections</span>
          </p>
          <ResponsiveContainer width="100%" height={190}>
            <ComposedChart data={ts} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="date" tick={{ fontSize: 9 }} tickFormatter={d => d.slice(5)} interval={TICK_INTERVAL(ts.length)} />
              <YAxis yAxisId="l" tick={{ fontSize: 10 }} />
              <YAxis yAxisId="r" orientation="right" tick={{ fontSize: 10 }} domain={[0, 'auto']} />
              <Tooltip labelFormatter={d => `Date: ${d}`} formatter={(v, n) => [v, n]} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Bar yAxisId="l" dataKey="mt" name="Mounting" fill="#a855f7" opacity={0.75} radius={[1, 1, 0, 0]} />
              <Line yAxisId="r" type="monotone" dataKey="hd" name="Heat Detection" stroke="#7c3aed" dot={false} strokeWidth={2} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>

        {/* Progesterone cycle */}
        <P4CycleChart ts={ts} p4Tests={p4_tests} />

        {/* Editable panels */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
          <P4Panel records={p4_tests} onSave={v => saveOverride('p4_tests', v)} />
          <CalvingPanel records={calvings} onSave={v => saveOverride('calvings', v)} />
          <HealthPanel records={health_records} onSave={v => saveOverride('health_records', v)} />
        </div>

        <p className="text-xs text-gray-400 text-center pb-4">
          Bodit sensor · {summary.date_first} – {summary.date_last} · {summary.n_days} days ·
          All behavioural parameters: activity rate, rumination, eating, mounting, heat detection, coughing ·
          Hover any record to edit · Changes saved to browser
        </p>
      </div>
    </>
  );
}
