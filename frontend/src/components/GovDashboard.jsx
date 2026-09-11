import React, { useState, useMemo } from 'react';
import {
  BarChart, Bar, LineChart, Line, ScatterChart, Scatter,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, Cell, ReferenceLine,
} from 'recharts';
import NETWORK from '../data/farm_network.json';

const FARMS = NETWORK.farms;
const MONTHS = ['Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep'];

const TIER_COLOR = { high: '#16a34a', medium: '#f59e0b', low: '#dc2626' };
const TIER_BG = { high: 'bg-green-100 text-green-800', medium: 'bg-amber-100 text-amber-800', low: 'bg-red-100 text-red-700' };

function KPI({ label, value, sub, color = 'text-blue-700' }) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <p className="text-xs text-gray-500 font-medium">{label}</p>
      <p className={`text-2xl font-bold mt-1 ${color}`}>{value}</p>
      {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
    </div>
  );
}

// Regional production trend — aggregate all farms' monthly milk
function RegionalTrend() {
  const data = MONTHS.map((m, i) => {
    const totalL = FARMS.reduce((s, f) => s + f.herd_size * f.monthly_milk_L[i], 0);
    return { month: m, volume: Math.round(totalL), farms: FARMS.length };
  });
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-5">
      <p className="text-sm font-semibold text-gray-900 mb-1">Regional Milk Production — Apr–Sep 2025</p>
      <p className="text-xs text-gray-400 mb-3">Daily aggregate across all {FARMS.length} farms · litres/day</p>
      <ResponsiveContainer width="100%" height={180}>
        <LineChart data={data} margin={{ top: 5, right: 10, left: 10, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis dataKey="month" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 10 }} tickFormatter={v => `${(v/1000).toFixed(1)}k`} />
          <Tooltip formatter={(v) => [`${v.toLocaleString()} L/day`, 'Total production']} />
          <Line type="monotone" dataKey="volume" name="Daily milk (L)" stroke="#3b82f6" dot={{ r: 4 }} strokeWidth={2} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

// Farm network table
function FarmNetworkTable() {
  const [sort, setSort] = useState('avg_activity_rate');
  const [filter, setFilter] = useState('all');
  const sorted = useMemo(() => {
    let f = filter === 'all' ? FARMS : FARMS.filter(x => x.tier === filter);
    return [...f].sort((a, b) => b[sort] - a[sort]);
  }, [sort, filter]);

  return (
    <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
      <div className="px-5 py-3 border-b border-gray-100 flex items-center justify-between flex-wrap gap-2">
        <p className="text-sm font-semibold text-gray-900">Farm Network — {FARMS.length} Farms · {NETWORK.region}</p>
        <div className="flex gap-2">
          <select className="text-xs border border-gray-200 rounded px-2 py-1" value={filter} onChange={e => setFilter(e.target.value)}>
            <option value="all">All tiers</option>
            <option value="high">High performing</option>
            <option value="medium">Medium</option>
            <option value="low">Low performing</option>
          </select>
          <select className="text-xs border border-gray-200 rounded px-2 py-1" value={sort} onChange={e => setSort(e.target.value)}>
            <option value="avg_activity_rate">Sort: Activity</option>
            <option value="avg_milk_yield_L">Sort: Milk yield</option>
            <option value="disease_events">Sort: Disease events</option>
            <option value="herd_size">Sort: Herd size</option>
            <option value="avg_rumination_min">Sort: Rumination</option>
          </select>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-2 text-left text-xs font-semibold text-gray-500">Farm</th>
              <th className="px-4 py-2 text-left text-xs font-semibold text-gray-500">State</th>
              <th className="px-4 py-2 text-right text-xs font-semibold text-gray-500">Herd</th>
              <th className="px-4 py-2 text-right text-xs font-semibold text-gray-500">Activity %</th>
              <th className="px-4 py-2 text-right text-xs font-semibold text-gray-500">Rum (min)</th>
              <th className="px-4 py-2 text-right text-xs font-semibold text-gray-500">Milk L/cow</th>
              <th className="px-4 py-2 text-right text-xs font-semibold text-gray-500">Daily Vol (L)</th>
              <th className="px-4 py-2 text-right text-xs font-semibold text-gray-500">Disease</th>
              <th className="px-4 py-2 text-xs font-semibold text-gray-500">Tier</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((f, i) => (
              <tr key={f.id} className={`border-t border-gray-50 ${i % 2 ? 'bg-gray-50/30' : ''}`}>
                <td className="px-4 py-2">
                  <p className="text-xs font-semibold text-gray-800">{f.name}</p>
                  <p className="text-xs text-gray-400">{f.id}</p>
                </td>
                <td className="px-4 py-2 text-xs text-gray-600">{f.state}</td>
                <td className="px-4 py-2 text-right text-sm text-gray-700">{f.herd_size}</td>
                <td className="px-4 py-2 text-right">
                  <span className={`font-semibold text-sm ${f.avg_activity_rate > 70 ? 'text-green-700' : f.avg_activity_rate > 55 ? 'text-amber-700' : 'text-red-600'}`}>
                    {f.avg_activity_rate.toFixed(1)}%
                  </span>
                </td>
                <td className="px-4 py-2 text-right text-sm text-gray-600">{f.avg_rumination_min}</td>
                <td className="px-4 py-2 text-right text-sm text-gray-700">{f.avg_milk_yield_L.toFixed(1)}</td>
                <td className="px-4 py-2 text-right text-sm font-semibold text-blue-700">{Math.round(f.herd_size * f.avg_milk_yield_L).toLocaleString()}</td>
                <td className="px-4 py-2 text-right">
                  <span className={`text-sm font-semibold ${f.disease_events >= 8 ? 'text-red-600' : f.disease_events >= 4 ? 'text-amber-600' : 'text-gray-600'}`}>
                    {f.disease_events}
                  </span>
                </td>
                <td className="px-4 py-2">
                  <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${TIER_BG[f.tier]}`}>{f.tier}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// Activity vs Milk scatter
function PerformanceScatter() {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-5">
      <p className="text-sm font-semibold text-gray-900 mb-1">Activity Rate vs Milk Yield — All Farms</p>
      <p className="text-xs text-gray-400 mb-3">Each point = one farm · colour = performance tier</p>
      <ResponsiveContainer width="100%" height={220}>
        <ScatterChart margin={{ top: 10, right: 20, left: -10, bottom: 10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis type="number" dataKey="x" name="Activity %" domain={[40, 85]} tick={{ fontSize: 10 }}
            label={{ value: 'Activity Rate (%)', position: 'insideBottom', offset: -5, fontSize: 11 }} />
          <YAxis type="number" dataKey="y" name="Milk yield" domain={[6, 23]} tick={{ fontSize: 10 }}
            label={{ value: 'L/cow/day', angle: -90, position: 'insideLeft', fontSize: 10, offset: 15 }} />
          <ReferenceLine x={65} stroke="#9ca3af" strokeDasharray="4 3" label={{ value: 'Activity threshold', fontSize: 9, fill: '#9ca3af' }} />
          <Tooltip cursor={{ strokeDasharray: '3 3' }}
            content={({ payload }) => {
              if (!payload?.length) return null;
              const d = payload[0].payload;
              return (
                <div className="bg-white border border-gray-200 rounded shadow px-3 py-2 text-xs">
                  <p className="font-semibold">{d.name}</p>
                  <p>Activity: <b>{d.x}%</b></p>
                  <p>Milk: <b>{d.y} L/cow</b></p>
                  <p>Disease events: <b>{d.disease}</b></p>
                </div>
              );
            }}
          />
          <Scatter
            data={FARMS.map(f => ({ x: f.avg_activity_rate, y: f.avg_milk_yield_L, name: f.name, tier: f.tier, disease: f.disease_events }))}
            name="Farms"
          >
            {FARMS.map((f, i) => (
              <Cell key={i} fill={TIER_COLOR[f.tier]} fillOpacity={0.8} />
            ))}
          </Scatter>
        </ScatterChart>
      </ResponsiveContainer>
      <div className="flex gap-4 mt-2">
        {Object.entries(TIER_COLOR).map(([t, c]) => (
          <span key={t} className="flex items-center gap-1.5 text-xs text-gray-500">
            <span className="w-3 h-3 rounded-full" style={{ background: c }} />
            {t.charAt(0).toUpperCase() + t.slice(1)} performing
          </span>
        ))}
      </div>
    </div>
  );
}

// Disease alert panel
function DiseaseAlerts() {
  const alerts = FARMS.filter(f => f.disease_events >= 5).sort((a,b) => b.disease_events - a.disease_events);
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-5">
      <div className="flex items-center gap-2 mb-3">
        <span className="w-2.5 h-2.5 rounded-full bg-red-500 animate-pulse" />
        <p className="text-sm font-semibold text-gray-900">Disease Surveillance Alerts</p>
      </div>
      <div className="space-y-2">
        {alerts.map(f => (
          <div key={f.id} className={`flex items-start justify-between rounded-lg px-3 py-2 border ${f.disease_events >= 8 ? 'bg-red-50 border-red-200' : 'bg-amber-50 border-amber-200'}`}>
            <div>
              <p className="text-xs font-semibold text-gray-800">{f.name}</p>
              <p className="text-xs text-gray-500">{f.lga}, {f.state}</p>
              {f.notes && f.notes.startsWith('⚠') && <p className="text-xs text-red-600 mt-0.5">{f.notes.replace('⚠ ', '')}</p>}
            </div>
            <div className="text-right ml-3 flex-shrink-0">
              <p className="text-sm font-bold text-red-600">{f.disease_events}</p>
              <p className="text-xs text-gray-400">events</p>
              <p className="text-xs text-amber-700">Cough idx: {f.coughing_index}</p>
            </div>
          </div>
        ))}
      </div>
      <p className="mt-3 text-xs text-gray-400">Farms with ≥5 disease events · {alerts.length} of {FARMS.length} flagged</p>
    </div>
  );
}

// Activity distribution bar
function ActivityDistribution() {
  const bins = [
    { label: '≥75%', color: '#16a34a', farms: FARMS.filter(f => f.avg_activity_rate >= 75) },
    { label: '65–75%', color: '#84cc16', farms: FARMS.filter(f => f.avg_activity_rate >= 65 && f.avg_activity_rate < 75) },
    { label: '55–65%', color: '#f59e0b', farms: FARMS.filter(f => f.avg_activity_rate >= 55 && f.avg_activity_rate < 65) },
    { label: '<55%', color: '#dc2626', farms: FARMS.filter(f => f.avg_activity_rate < 55) },
  ];
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-5">
      <p className="text-sm font-semibold text-gray-900 mb-3">Herd Activity Distribution</p>
      <div className="space-y-2">
        {bins.map(b => (
          <div key={b.label} className="flex items-center gap-3">
            <p className="text-xs text-gray-500 w-16 flex-shrink-0">{b.label}</p>
            <div className="flex-1 bg-gray-100 rounded-full h-4 overflow-hidden">
              <div className="h-full rounded-full" style={{ width: `${(b.farms.length / FARMS.length) * 100}%`, background: b.color }} />
            </div>
            <p className="text-xs font-semibold text-gray-700 w-12 text-right">{b.farms.length} farms</p>
          </div>
        ))}
      </div>
      <p className="mt-3 text-xs text-gray-400">Sensor-derived activity rate · all {FARMS.length} farms</p>
    </div>
  );
}

export default function GovDashboard() {
  const totalHerd = FARMS.reduce((s, f) => s + f.herd_size, 0);
  const totalDailyMilk = Math.round(FARMS.reduce((s, f) => s + f.herd_size * f.avg_milk_yield_L, 0));
  const avgActivity = (FARMS.reduce((s, f) => s + f.avg_activity_rate, 0) / FARMS.length).toFixed(1);
  const alertFarms = FARMS.filter(f => f.disease_events >= 5).length;

  return (
    <div className="p-6 space-y-5">
      <div>
        <h1 className="text-xl font-bold text-gray-900">FMARD Regional Overview — {NETWORK.region}</h1>
        <p className="text-sm text-gray-500 mt-0.5">{FARMS.length} monitored farms · Bodit sensor data · {NETWORK.period}</p>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KPI label="Monitored Farms" value={FARMS.length} sub={`${NETWORK.region}`} color="text-blue-700" />
        <KPI label="Total Herd" value={totalHerd.toLocaleString()} sub="animals across region" color="text-green-700" />
        <KPI label="Daily Milk Output" value={`${(totalDailyMilk/1000).toFixed(1)}k L`} sub="aggregate production" color="text-teal-700" />
        <KPI label="Disease Alerts" value={alertFarms} sub={`of ${FARMS.length} farms flagged`} color={alertFarms > 3 ? 'text-red-600' : 'text-amber-600'} />
      </div>

      {/* Trend + distribution */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <div className="lg:col-span-2">
          <RegionalTrend />
        </div>
        <ActivityDistribution />
      </div>

      {/* Scatter + alerts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <div className="lg:col-span-2">
          <PerformanceScatter />
        </div>
        <DiseaseAlerts />
      </div>

      {/* Farm network table */}
      <FarmNetworkTable />

      <p className="text-xs text-gray-400 text-center pb-4">
        NDIC Platform · {FARMS.length} farms · {NETWORK.region} · Bodit behavioural sensor · {NETWORK.period}
      </p>
    </div>
  );
}
