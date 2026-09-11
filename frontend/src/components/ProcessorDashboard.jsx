import React, { useState, useMemo } from 'react';
import {
  BarChart, Bar, LineChart, Line, ComposedChart, Area,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, Cell, ReferenceLine,
} from 'recharts';
import NETWORK from '../data/farm_network.json';

// Processor sources from 12 farms (top performers, sorted by daily volume)
const SUPPLIERS = [...NETWORK.farms]
  .sort((a, b) => (b.herd_size * b.avg_milk_yield_L) - (a.herd_size * a.avg_milk_yield_L))
  .slice(0, 12);

const MONTHS = ['Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep'];

function KPI({ label, value, sub, color = 'text-blue-700' }) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <p className="text-xs text-gray-500 font-medium">{label}</p>
      <p className={`text-2xl font-bold mt-1 ${color}`}>{value}</p>
      {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
    </div>
  );
}

// Reliability score: based on activity consistency and disease events
function reliabilityScore(farm) {
  const actScore = Math.min(100, farm.avg_activity_rate * 1.2);
  const diseaseDeduction = farm.disease_events * 4;
  const varianceDeduction = farm.tier === 'high' ? 0 : farm.tier === 'medium' ? 8 : 18;
  return Math.max(0, Math.round(actScore - diseaseDeduction - varianceDeduction));
}

function SupplyVolumeChart() {
  const data = MONTHS.map((m, i) => {
    const entry = { month: m };
    let total = 0;
    SUPPLIERS.forEach(f => {
      const vol = Math.round(f.herd_size * f.monthly_milk_L[i]);
      total += vol;
    });
    entry.total = total;
    entry.high = Math.round(SUPPLIERS.filter(f=>f.tier==='high').reduce((s,f)=>s+f.herd_size*f.monthly_milk_L[i],0));
    entry.medium = Math.round(SUPPLIERS.filter(f=>f.tier==='medium').reduce((s,f)=>s+f.herd_size*f.monthly_milk_L[i],0));
    return entry;
  });

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-5">
      <p className="text-sm font-semibold text-gray-900 mb-1">Daily Supply Volume — Apr–Sep 2025</p>
      <p className="text-xs text-gray-400 mb-3">Stacked by supplier tier · litres/day · {SUPPLIERS.length} active suppliers</p>
      <ResponsiveContainer width="100%" height={190}>
        <BarChart data={data} margin={{ top: 0, right: 10, left: 10, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis dataKey="month" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 10 }} tickFormatter={v => `${(v/1000).toFixed(1)}k`} />
          <Tooltip formatter={(v, n) => [`${v.toLocaleString()} L`, n]} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <Bar dataKey="high" name="High-tier suppliers" stackId="a" fill="#16a34a" />
          <Bar dataKey="medium" name="Medium-tier suppliers" stackId="a" fill="#f59e0b" radius={[2,2,0,0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function SupplierTable() {
  const [sort, setSort] = useState('volume');
  const sorted = useMemo(() => {
    return [...SUPPLIERS].sort((a, b) => {
      if (sort === 'volume') return (b.herd_size * b.avg_milk_yield_L) - (a.herd_size * a.avg_milk_yield_L);
      if (sort === 'reliability') return reliabilityScore(b) - reliabilityScore(a);
      if (sort === 'activity') return b.avg_activity_rate - a.avg_activity_rate;
      return 0;
    });
  }, [sort]);

  return (
    <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
      <div className="px-5 py-3 border-b border-gray-100 flex items-center justify-between flex-wrap gap-2">
        <p className="text-sm font-semibold text-gray-900">Supplier Benchmarking — {SUPPLIERS.length} Farms</p>
        <select className="text-xs border border-gray-200 rounded px-2 py-1" value={sort} onChange={e => setSort(e.target.value)}>
          <option value="volume">Sort: Daily volume</option>
          <option value="reliability">Sort: Reliability</option>
          <option value="activity">Sort: Herd activity</option>
        </select>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-2 text-left text-xs font-semibold text-gray-500">Supplier</th>
              <th className="px-4 py-2 text-right text-xs font-semibold text-gray-500">Herd</th>
              <th className="px-4 py-2 text-right text-xs font-semibold text-gray-500">L/cow/day</th>
              <th className="px-4 py-2 text-right text-xs font-semibold text-gray-500">Daily Vol (L)</th>
              <th className="px-4 py-2 text-right text-xs font-semibold text-gray-500">Activity %</th>
              <th className="px-4 py-2 text-right text-xs font-semibold text-gray-500">Rumination</th>
              <th className="px-4 py-2 text-right text-xs font-semibold text-gray-500">Disease Events</th>
              <th className="px-4 py-2 text-right text-xs font-semibold text-gray-500">Reliability</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((f, i) => {
              const dailyVol = Math.round(f.herd_size * f.avg_milk_yield_L);
              const rel = reliabilityScore(f);
              return (
                <tr key={f.id} className={`border-t border-gray-50 ${i % 2 ? 'bg-gray-50/30' : ''}`}>
                  <td className="px-4 py-2">
                    <p className="text-xs font-semibold text-gray-800">{f.name}</p>
                    <p className="text-xs text-gray-400">{f.state} · {f.id}</p>
                  </td>
                  <td className="px-4 py-2 text-right text-sm text-gray-700">{f.herd_size}</td>
                  <td className="px-4 py-2 text-right text-sm text-gray-700">{f.avg_milk_yield_L.toFixed(1)}</td>
                  <td className="px-4 py-2 text-right text-sm font-bold text-blue-700">{dailyVol.toLocaleString()}</td>
                  <td className="px-4 py-2 text-right">
                    <span className={`text-sm font-semibold ${f.avg_activity_rate > 70 ? 'text-green-700' : f.avg_activity_rate > 55 ? 'text-amber-700' : 'text-red-600'}`}>
                      {f.avg_activity_rate.toFixed(1)}%
                    </span>
                  </td>
                  <td className="px-4 py-2 text-right text-sm text-gray-600">{f.avg_rumination_min} min</td>
                  <td className="px-4 py-2 text-right">
                    <span className={`text-sm ${f.disease_events >= 5 ? 'text-red-600 font-semibold' : 'text-gray-600'}`}>{f.disease_events}</span>
                  </td>
                  <td className="px-4 py-2 text-right">
                    <div className="flex items-center justify-end gap-1.5">
                      <div className="w-12 bg-gray-100 rounded-full h-1.5 overflow-hidden">
                        <div className="h-full rounded-full"
                          style={{ width: `${rel}%`, background: rel >= 75 ? '#16a34a' : rel >= 55 ? '#f59e0b' : '#dc2626' }} />
                      </div>
                      <span className={`text-xs font-semibold ${rel >= 75 ? 'text-green-700' : rel >= 55 ? 'text-amber-700' : 'text-red-600'}`}>{rel}</span>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="px-5 py-2 text-xs text-gray-400 border-t border-gray-50">
        Reliability = sensor-derived composite: activity rate, disease events, tier variance · higher = more consistent supply
      </p>
    </div>
  );
}

function SupplyForecast() {
  // Forecast Sep–Dec based on trend
  const historical = MONTHS.map((m, i) => ({
    month: m,
    actual: Math.round(SUPPLIERS.reduce((s,f) => s+f.herd_size*f.monthly_milk_L[i], 0)),
  }));
  const lastActual = historical[historical.length - 1].actual;
  const trend = (historical[5].actual - historical[0].actual) / 5; // L/month change
  const forecast = [
    { month: 'Oct', forecast: Math.round(lastActual + trend * 1), lower: Math.round(lastActual + trend * 1 - 300), upper: Math.round(lastActual + trend * 1 + 300) },
    { month: 'Nov', forecast: Math.round(lastActual + trend * 2), lower: Math.round(lastActual + trend * 2 - 500), upper: Math.round(lastActual + trend * 2 + 500) },
    { month: 'Dec', forecast: Math.round(lastActual + trend * 3), lower: Math.round(lastActual + trend * 3 - 700), upper: Math.round(lastActual + trend * 3 + 700) },
  ];
  const combined = [
    ...historical,
    ...forecast.map(f => ({ month: f.month, forecast: f.forecast, lower: f.lower, upper: f.upper })),
  ];

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-5">
      <p className="text-sm font-semibold text-gray-900 mb-1">Supply Forecast — Q4 2025</p>
      <p className="text-xs text-gray-400 mb-3">Historical Apr–Sep + 3-month forecast with confidence band · L/day total</p>
      <ResponsiveContainer width="100%" height={180}>
        <ComposedChart data={combined} margin={{ top: 5, right: 10, left: 10, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis dataKey="month" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 10 }} tickFormatter={v => `${(v/1000).toFixed(1)}k`} />
          <Tooltip formatter={(v, n) => [`${v?.toLocaleString()} L`, n]} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <Area dataKey="upper" fill="#bfdbfe" stroke="none" name="Upper bound" />
          <Area dataKey="lower" fill="#ffffff" stroke="none" name="Lower bound" />
          <Line type="monotone" dataKey="actual" name="Actual supply" stroke="#3b82f6" dot={{ r: 4 }} strokeWidth={2} />
          <Line type="monotone" dataKey="forecast" name="Forecast" stroke="#6366f1" strokeDasharray="5 3" dot={{ r: 3 }} strokeWidth={2} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

function HerdHealthSummary() {
  const highCount = SUPPLIERS.filter(f => f.tier === 'high').length;
  const midCount = SUPPLIERS.filter(f => f.tier === 'medium').length;
  const lowCount = SUPPLIERS.filter(f => f.tier === 'low').length;
  const avgActivity = (SUPPLIERS.reduce((s,f)=>s+f.avg_activity_rate,0)/SUPPLIERS.length).toFixed(1);
  const avgRum = Math.round(SUPPLIERS.reduce((s,f)=>s+f.avg_rumination_min,0)/SUPPLIERS.length);

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-5">
      <p className="text-sm font-semibold text-gray-900 mb-3">Supplier Herd Health Summary</p>
      <div className="space-y-3">
        <div className="flex items-center justify-between py-2 border-b border-gray-50">
          <p className="text-sm text-gray-600">Avg herd activity rate</p>
          <p className="text-sm font-bold text-blue-700">{avgActivity}%</p>
        </div>
        <div className="flex items-center justify-between py-2 border-b border-gray-50">
          <p className="text-sm text-gray-600">Avg rumination</p>
          <p className="text-sm font-bold text-green-700">{avgRum} min/day</p>
        </div>
        <div className="flex items-center justify-between py-2 border-b border-gray-50">
          <p className="text-sm text-gray-600">High-performing suppliers</p>
          <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-green-100 text-green-800">{highCount} farms</span>
        </div>
        <div className="flex items-center justify-between py-2 border-b border-gray-50">
          <p className="text-sm text-gray-600">Medium-performing</p>
          <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-800">{midCount} farms</span>
        </div>
        {lowCount > 0 && (
          <div className="flex items-center justify-between py-2">
            <p className="text-sm text-gray-600">At-risk suppliers</p>
            <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-red-100 text-red-700">{lowCount} farms</span>
          </div>
        )}
        <p className="text-xs text-gray-400 pt-1">Herd health = key predictor of milk quality &amp; volume reliability</p>
      </div>
    </div>
  );
}

export default function ProcessorDashboard() {
  const totalDailyVol = Math.round(SUPPLIERS.reduce((s,f) => s+f.herd_size*f.avg_milk_yield_L, 0));
  const avgReliability = Math.round(SUPPLIERS.reduce((s,f) => s+reliabilityScore(f), 0) / SUPPLIERS.length);
  const topSupplier = [...SUPPLIERS].sort((a,b) => (b.herd_size*b.avg_milk_yield_L)-(a.herd_size*a.avg_milk_yield_L))[0];
  const avgActivity = (SUPPLIERS.reduce((s,f)=>s+f.avg_activity_rate,0)/SUPPLIERS.length).toFixed(1);

  return (
    <div className="p-6 space-y-5">
      <div>
        <h1 className="text-xl font-bold text-gray-900">Processor Supply Chain — {NETWORK.region}</h1>
        <p className="text-sm text-gray-500 mt-0.5">
          {SUPPLIERS.length} supplier farms · supply reliability derived from Bodit sensor data · {NETWORK.period}
        </p>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KPI label="Daily Supply" value={`${totalDailyVol.toLocaleString()} L`} sub={`${SUPPLIERS.length} supplier farms`} color="text-blue-700" />
        <KPI label="Avg Herd Activity" value={`${avgActivity}%`} sub="supply quality proxy" color="text-green-700" />
        <KPI label="Avg Reliability Score" value={avgReliability} sub="sensor-derived · /100" color={avgReliability >= 70 ? 'text-green-700' : 'text-amber-600'} />
        <KPI label="Largest Supplier" value={`${Math.round(topSupplier.herd_size * topSupplier.avg_milk_yield_L)} L/day`} sub={topSupplier.name.split(' ').slice(0,2).join(' ')} color="text-purple-700" />
      </div>

      {/* Supply volume + forecast */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <SupplyVolumeChart />
        <SupplyForecast />
      </div>

      {/* Supplier table + health summary */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-5">
        <div className="lg:col-span-3">
          <SupplierTable />
        </div>
        <HerdHealthSummary />
      </div>

      <p className="text-xs text-gray-400 text-center pb-4">
        Supply reliability derived from Bodit behavioural sensor data · activity rate, rumination, disease burden ·
        {SUPPLIERS.length} supplier farms · {NETWORK.region} · {NETWORK.period}
      </p>
    </div>
  );
}
