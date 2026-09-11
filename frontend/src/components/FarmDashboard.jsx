import React, { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  LineChart, Line, BarChart, Bar, ComposedChart,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, ReferenceLine,
} from 'recharts';
import RESEARCH from '../data/research_data.json';
import NETWORK from '../data/farm_network.json';

const FARM = NETWORK.farms[0]; // NCN-001 = the real Bodit farm
const fmt = (n, d = 1) => Number(n).toFixed(d);
const TICK = (n) => Math.max(1, Math.floor(n / 8));

function KPI({ label, value, sub, color = 'text-blue-700' }) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <p className="text-xs text-gray-500 font-medium">{label}</p>
      <p className={`text-2xl font-bold mt-1 ${color}`}>{value}</p>
      {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
    </div>
  );
}

function HerdTable({ onSelect, selected }) {
  const navigate = useNavigate();
  const [sort, setSort] = useState('total_heat_detections');
  const sorted = useMemo(
    () => [...RESEARCH.cow_summary].sort((a, b) => b[sort] - a[sort]),
    [sort]
  );
  return (
    <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
      <div className="px-5 py-3 border-b border-gray-100 flex items-center justify-between">
        <p className="text-sm font-semibold text-gray-900">Herd — {RESEARCH.cow_summary.length} Animals</p>
        <select className="text-xs border border-gray-200 rounded px-2 py-1" value={sort} onChange={e => setSort(e.target.value)}>
          <option value="total_heat_detections">Sort: Heat Detections</option>
          <option value="total_mounting">Sort: Mounting</option>
          <option value="avg_activity_rate">Sort: Activity Rate</option>
          <option value="avg_rumination_min">Sort: Rumination</option>
          <option value="total_coughing">Sort: Coughing</option>
        </select>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-2 text-left text-xs font-semibold text-gray-500">Cow ID</th>
              <th className="px-4 py-2 text-right text-xs font-semibold text-gray-500">Activity %</th>
              <th className="px-4 py-2 text-right text-xs font-semibold text-gray-500">Rum (min)</th>
              <th className="px-4 py-2 text-right text-xs font-semibold text-gray-500">Eating (min)</th>
              <th className="px-4 py-2 text-right text-xs font-semibold text-gray-500">Heat Det.</th>
              <th className="px-4 py-2 text-right text-xs font-semibold text-gray-500">Mounting</th>
              <th className="px-4 py-2 text-right text-xs font-semibold text-gray-500">Coughing</th>
              <th className="px-4 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {sorted.map(cow => (
              <tr
                key={cow.cow_id}
                className={`border-t border-gray-50 cursor-pointer hover:bg-blue-50 transition-colors ${selected === cow.cow_id ? 'bg-blue-50' : ''}`}
                onClick={() => onSelect(cow.cow_id === selected ? null : cow.cow_id)}
              >
                <td className="px-4 py-2 font-mono text-xs text-gray-700">{cow.cow_id}</td>
                <td className="px-4 py-2 text-right">
                  <span className={`font-semibold ${cow.avg_activity_rate > 70 ? 'text-green-700' : cow.avg_activity_rate > 55 ? 'text-yellow-700' : 'text-red-600'}`}>
                    {fmt(cow.avg_activity_rate)}%
                  </span>
                </td>
                <td className="px-4 py-2 text-right text-gray-700">{fmt(cow.avg_rumination_min, 0)}</td>
                <td className="px-4 py-2 text-right text-gray-700">{fmt(cow.avg_eating_min, 0)}</td>
                <td className="px-4 py-2 text-right font-semibold text-purple-700">{cow.total_heat_detections}</td>
                <td className="px-4 py-2 text-right text-gray-600">{cow.total_mounting}</td>
                <td className="px-4 py-2 text-right text-gray-500">{cow.total_coughing}</td>
                <td className="px-4 py-2 text-xs text-blue-500 font-medium"
                  onClick={e => { e.stopPropagation(); navigate(`/farm/animals/${cow.cow_id}`); }}>
                  Passport →
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function CowDetail({ cowId }) {
  const ts = cowId ? RESEARCH.cow_ts[cowId] || [] : [];
  if (!cowId || !ts.length) return (
    <div className="bg-white rounded-lg border border-gray-200 p-5">
      <p className="text-sm font-semibold text-gray-900 mb-1">Sensor Detail</p>
      <p className="text-sm text-gray-400 mt-4">Click a cow row to view its sensor time-series.</p>
    </div>
  );
  const display = ts.slice(-30);
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-5 space-y-4">
      <p className="text-sm font-semibold text-gray-900">{cowId} — Last 30 Days</p>
      <ResponsiveContainer width="100%" height={160}>
        <LineChart data={display} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis dataKey="date" tick={{ fontSize: 9 }} tickFormatter={d => d.slice(5)} interval={4} />
          <YAxis yAxisId="l" tick={{ fontSize: 10 }} domain={[0, 100]} />
          <YAxis yAxisId="r" orientation="right" tick={{ fontSize: 10 }} />
          <Tooltip labelFormatter={d => `Date: ${d}`} formatter={(v, n) => [fmt(v), n]} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <Line yAxisId="l" type="monotone" dataKey="ar" name="Activity %" stroke="#3b82f6" dot={false} strokeWidth={2} />
          <Line yAxisId="r" type="monotone" dataKey="rum" name="Rumination (min)" stroke="#10b981" dot={false} strokeWidth={2} />
        </LineChart>
      </ResponsiveContainer>
      <ResponsiveContainer width="100%" height={120}>
        <ComposedChart data={display} margin={{ top: 0, right: 10, left: -20, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis dataKey="date" tick={{ fontSize: 9 }} tickFormatter={d => d.slice(5)} interval={4} />
          <YAxis tick={{ fontSize: 10 }} />
          <Tooltip labelFormatter={d => `Date: ${d}`} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <Bar dataKey="mt" name="Mounting" fill="#a855f7" radius={[1,1,0,0]} />
          <Line type="monotone" dataKey="hd" name="Heat Det." stroke="#7c3aed" dot={false} strokeWidth={2} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

function HerdTrend() {
  const herdDaily = useMemo(() => {
    const byDate = {};
    Object.values(RESEARCH.cow_ts).forEach(cowDays => {
      cowDays.forEach(d => {
        if (!byDate[d.date]) byDate[d.date] = { date: d.date, ar: [], rum: [], mt: 0, hd: 0 };
        byDate[d.date].ar.push(d.ar);
        byDate[d.date].rum.push(d.rum);
        byDate[d.date].mt += d.mt;
        byDate[d.date].hd += d.hd;
      });
    });
    return Object.values(byDate)
      .sort((a, b) => a.date.localeCompare(b.date))
      .map(d => ({
        date: d.date,
        ar: (d.ar.reduce((s, v) => s + v, 0) / d.ar.length).toFixed(1),
        rum: (d.rum.reduce((s, v) => s + v, 0) / d.rum.length).toFixed(0),
        mt: d.mt,
        hd: d.hd,
      }))
      .slice(-60);
  }, []);

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-5">
      <p className="text-sm font-semibold text-gray-900 mb-1">Herd Activity & Rumination — Last 60 Days</p>
      <ResponsiveContainer width="100%" height={190}>
        <LineChart data={herdDaily} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis dataKey="date" tick={{ fontSize: 9 }} tickFormatter={d => d.slice(5)} interval={TICK(herdDaily.length)} />
          <YAxis yAxisId="l" tick={{ fontSize: 10 }} domain={[0, 100]} />
          <YAxis yAxisId="r" orientation="right" tick={{ fontSize: 10 }} />
          <Tooltip labelFormatter={d => `Date: ${d}`} formatter={(v, n) => [v, n]} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <Line yAxisId="l" type="monotone" dataKey="ar" name="Activity %" stroke="#3b82f6" dot={false} strokeWidth={2} />
          <Line yAxisId="r" type="monotone" dataKey="rum" name="Rumination (min)" stroke="#10b981" dot={false} strokeWidth={2} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export default function FarmDashboard() {
  const [selectedCow, setSelectedCow] = useState(null);
  const totalMilk = Math.round(FARM.herd_size * FARM.avg_milk_yield_L);
  const avgActivity = RESEARCH.cow_summary.reduce((s, c) => s + c.avg_activity_rate, 0) / RESEARCH.cow_summary.length;

  return (
    <div className="p-6 space-y-5">
      {/* Farm header */}
      <div className="bg-white rounded-lg border border-gray-200 p-5">
        <div className="flex items-start justify-between flex-wrap gap-3">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <h1 className="text-xl font-bold text-gray-900">{FARM.name}</h1>
              <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-green-100 text-green-800">High Performing</span>
            </div>
            <p className="text-sm text-gray-500">{FARM.lga}, {FARM.state} · Owner: {FARM.owner}</p>
            <p className="text-xs text-gray-400 mt-1">Bodit sensor · {FARM.sensor_days} days monitored · {NETWORK.period}</p>
          </div>
          <div className="text-right text-sm">
            <p className="text-xs text-gray-500 font-medium uppercase tracking-wide">Daily Milk Output</p>
            <p className="text-2xl font-bold text-green-700">{totalMilk.toLocaleString()} L</p>
            <p className="text-xs text-gray-400">@ ₦320/L = ₦{(totalMilk * 320).toLocaleString()}/day</p>
          </div>
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        <KPI label="Herd Size" value={FARM.herd_size} sub={`${FARM.sensor_days} sensor days`} color="text-blue-700" />
        <KPI label="Avg Activity Rate" value={`${avgActivity.toFixed(1)}%`} sub="herd average" color="text-blue-700" />
        <KPI label="Avg Rumination" value={`${fmt(FARM.avg_rumination_min, 0)} min`} sub="daily herd avg" color="text-green-700" />
        <KPI label="Avg Eating" value={`${fmt(FARM.avg_eating_min, 0)} min`} sub="daily herd avg" color="text-teal-700" />
        <KPI label="Heat Detections" value={RESEARCH.cow_summary.reduce((s,c)=>s+c.total_heat_detections,0)} sub="full period · all cows" color="text-purple-700" />
        <KPI label="Avg Milk Yield" value={`${FARM.avg_milk_yield_L} L/cow`} sub={`${totalMilk}L total/day`} color="text-orange-700" />
      </div>

      {/* Herd trend */}
      <HerdTrend />

      {/* Herd table + cow detail */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
        <div className="xl:col-span-2">
          <HerdTable onSelect={setSelectedCow} selected={selectedCow} />
        </div>
        <CowDetail cowId={selectedCow} />
      </div>

      <p className="text-xs text-gray-400 text-center pb-4">
        {FARM.name} · {FARM.id} · Bodit behavioural sensor · Click any cow row for detail · Passport → for full individual record
      </p>
    </div>
  );
}
