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

// Map bounds: North Central Nigeria
const MAP_BOUNDS = { latMin: 6.8, latMax: 12.8, lonMin: 5.0, lonMax: 11.5 };
const W = 620, H = 360;

function latToY(lat) { return H - ((lat - MAP_BOUNDS.latMin) / (MAP_BOUNDS.latMax - MAP_BOUNDS.latMin)) * H; }
function lonToX(lon) { return ((lon - MAP_BOUNDS.lonMin) / (MAP_BOUNDS.lonMax - MAP_BOUNDS.lonMin)) * W; }

// State label positions (approx centres)
const STATE_LABELS = [
  { name: 'Plateau',   lat: 9.5,  lon: 9.4  },
  { name: 'Niger',     lat: 9.9,  lon: 6.2  },
  { name: 'Kaduna',    lat: 10.6, lon: 7.7  },
  { name: 'Nasarawa', lat: 8.4,  lon: 8.1  },
  { name: 'Kogi',      lat: 7.4,  lon: 6.7  },
  { name: 'Benue',     lat: 7.2,  lon: 9.0  },
  { name: 'FCT',       lat: 8.95, lon: 7.35 },
  { name: 'Taraba',    lat: 7.8,  lon: 10.6 },
  { name: 'Katsina',   lat: 12.4, lon: 7.5  },
  { name: 'Zamfara',   lat: 11.8, lon: 6.3  },
  { name: 'Kwara',     lat: 8.5,  lon: 5.6  },
  { name: 'Bauchi',    lat: 10.3, lon: 9.8  },
];

// Environmental hazard zones (mock, based on real risk patterns)
const FLOOD_ZONES = [
  { name: 'Benue Basin Flood', lat: 7.3, lon: 8.8, r: 55, severity: 'high' },
  { name: 'Kogi Flood Plain',  lat: 7.6, lon: 6.6, r: 40, severity: 'medium' },
  { name: 'Niger Inland Delta', lat: 9.5, lon: 6.1, r: 35, severity: 'medium' },
];

const DROUGHT_ZONES = [
  { name: 'Katsina Drylands',  lat: 12.3, lon: 7.4, r: 50, severity: 'high' },
  { name: 'Zamfara Dry Belt',   lat: 11.9, lon: 6.2, r: 38, severity: 'medium' },
];

const DISEASE_CLUSTERS = [
  { name: 'FMD Alert — Taraba', lat: 7.85, lon: 10.5, r: 38, disease: 'FMD', severity: 'high' },
  { name: 'CBPP — Nasarawa',   lat: 8.55, lon: 8.4,  r: 30, disease: 'CBPP', severity: 'medium' },
];

function KPI({ label, value, sub, color = 'text-blue-700' }) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <p className="text-xs text-gray-500 font-medium">{label}</p>
      <p className={`text-2xl font-bold mt-1 ${color}`}>{value}</p>
      {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
    </div>
  );
}

// ── Regional SVG Map ───────────────────────────────────────────────────────────
function RegionalMap() {
  const [hovered, setHovered] = useState(null);
  const [mapLayer, setMapLayer] = useState('all');

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-5">
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <div>
          <p className="text-sm font-semibold text-gray-900">Regional Overview — North Central Nigeria</p>
          <p className="text-xs text-gray-400">Farm locations · disease clusters · environmental hazards</p>
        </div>
        <div className="flex gap-1 flex-wrap">
          {[['all','All'], ['farms','Farms'], ['disease','Disease'], ['flood','Floods'], ['drought','Drought']].map(([v, l]) => (
            <button key={v} onClick={() => setMapLayer(v)}
              className={`px-2 py-0.5 rounded text-xs font-medium border transition-colors ${mapLayer === v ? 'bg-gray-800 text-white border-gray-800' : 'bg-white text-gray-600 border-gray-200 hover:border-gray-400'}`}>
              {l}
            </button>
          ))}
        </div>
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-3 mb-2 text-xs text-gray-500">
        <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-full bg-green-600 inline-block"/>{' '}High-perf farm</span>
        <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-full bg-amber-500 inline-block"/>{' '}Med-perf farm</span>
        <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-full bg-red-500 inline-block"/>{' '}Low-perf farm</span>
        <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-full bg-blue-400 opacity-50 inline-block border border-blue-600"/>{' '}Flood zone</span>
        <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-full bg-orange-400 opacity-50 inline-block border border-orange-600"/>{' '}Drought zone</span>
        <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-full bg-red-400 opacity-40 inline-block border border-red-700"/>{' '}Disease cluster</span>
      </div>

      <div className="relative overflow-x-auto">
        <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ maxHeight: 340, background: '#f0f7ee', borderRadius: 6, border: '1px solid #e5e7eb' }}>
          {/* Background grid */}
          {[7,8,9,10,11,12].map(lat => (
            <line key={lat} x1={0} y1={latToY(lat)} x2={W} y2={latToY(lat)} stroke="#d1fae5" strokeWidth={0.5} />
          ))}
          {[6,7,8,9,10,11].map(lon => (
            <line key={lon} x1={lonToX(lon)} y1={0} x2={lonToX(lon)} y2={H} stroke="#d1fae5" strokeWidth={0.5} />
          ))}

          {/* Flood zones */}
          {(mapLayer === 'all' || mapLayer === 'flood') && FLOOD_ZONES.map((z, i) => (
            <circle key={i} cx={lonToX(z.lon)} cy={latToY(z.lat)} r={z.r}
              fill="#3b82f6" fillOpacity={z.severity === 'high' ? 0.22 : 0.14}
              stroke="#2563eb" strokeWidth={1.5} strokeDasharray="5 3" />
          ))}

          {/* Drought zones */}
          {(mapLayer === 'all' || mapLayer === 'drought') && DROUGHT_ZONES.map((z, i) => (
            <circle key={i} cx={lonToX(z.lon)} cy={latToY(z.lat)} r={z.r}
              fill="#f97316" fillOpacity={z.severity === 'high' ? 0.22 : 0.14}
              stroke="#ea580c" strokeWidth={1.5} strokeDasharray="5 3" />
          ))}

          {/* Disease clusters */}
          {(mapLayer === 'all' || mapLayer === 'disease') && DISEASE_CLUSTERS.map((z, i) => (
            <g key={i}>
              <circle cx={lonToX(z.lon)} cy={latToY(z.lat)} r={z.r}
                fill="#ef4444" fillOpacity={0.15}
                stroke="#dc2626" strokeWidth={1.5} strokeDasharray="4 2" />
              <text x={lonToX(z.lon)} y={latToY(z.lat) - z.r - 4}
                textAnchor="middle" fontSize={9} fill="#dc2626" fontWeight="600">
                {z.disease}
              </text>
            </g>
          ))}

          {/* State labels */}
          {STATE_LABELS.map(s => (
            <text key={s.name} x={lonToX(s.lon)} y={latToY(s.lat)}
              textAnchor="middle" fontSize={9} fill="#6b7280" fontWeight="500" opacity={0.8}>
              {s.name}
            </text>
          ))}

          {/* Farm dots */}
          {(mapLayer === 'all' || mapLayer === 'farms') && FARMS.map(f => {
            const x = lonToX(f.lon);
            const y = latToY(f.lat);
            const color = TIER_COLOR[f.tier];
            const isHigh = f.disease_events >= 8;
            return (
              <g key={f.id} style={{ cursor: 'pointer' }}
                onMouseEnter={() => setHovered(f)}
                onMouseLeave={() => setHovered(null)}>
                {isHigh && <circle cx={x} cy={y} r={10} fill="#dc2626" fillOpacity={0.2} />}
                <circle cx={x} cy={y} r={hovered?.id === f.id ? 7 : 5}
                  fill={color} stroke="#fff" strokeWidth={1.5} fillOpacity={0.9} />
              </g>
            );
          })}

          {/* Flood zone labels */}
          {(mapLayer === 'all' || mapLayer === 'flood') && FLOOD_ZONES.map((z, i) => (
            <text key={i} x={lonToX(z.lon)} y={latToY(z.lat) + 4}
              textAnchor="middle" fontSize={8} fill="#1d4ed8" fontWeight="600" opacity={0.8}>
              FLOOD
            </text>
          ))}

          {/* Drought zone labels */}
          {(mapLayer === 'all' || mapLayer === 'drought') && DROUGHT_ZONES.map((z, i) => (
            <text key={i} x={lonToX(z.lon)} y={latToY(z.lat) + 4}
              textAnchor="middle" fontSize={8} fill="#c2410c" fontWeight="600" opacity={0.8}>
              DROUGHT
            </text>
          ))}

          {/* Hovered tooltip */}
          {hovered && (() => {
            const x = lonToX(hovered.lon);
            const y = latToY(hovered.lat);
            const tx = x > W - 130 ? x - 135 : x + 12;
            const ty = y < 60 ? y + 10 : y - 55;
            return (
              <g>
                <rect x={tx} y={ty} width={128} height={52} rx={4}
                  fill="white" stroke="#e5e7eb" strokeWidth={1} filter="drop-shadow(0 1px 3px rgba(0,0,0,0.15))" />
                <text x={tx + 7} y={ty + 14} fontSize={10} fontWeight="700" fill="#111827">{hovered.name}</text>
                <text x={tx + 7} y={ty + 26} fontSize={9} fill="#6b7280">{hovered.lga}, {hovered.state}</text>
                <text x={tx + 7} y={ty + 38} fontSize={9} fill="#374151">
                  Activity: {hovered.avg_activity_rate}% · Disease: {hovered.disease_events}
                </text>
                <text x={tx + 7} y={ty + 49} fontSize={9} fill="#374151">
                  Milk: {hovered.avg_milk_yield_L} L/cow · {hovered.tier} tier
                </text>
              </g>
            );
          })()}
        </svg>
      </div>
    </div>
  );
}

// ── Environmental Alerts Panel ─────────────────────────────────────────────────
function EnvironmentalAlerts() {
  const alerts = [
    {
      type: 'Flood',
      icon: '🌊',
      color: 'border-blue-200 bg-blue-50',
      label: 'text-blue-700',
      severity: 'HIGH',
      sevColor: 'bg-red-100 text-red-700',
      title: 'Benue Basin Flooding',
      desc: '3 farms in flood-prone zones. Benue, Kogi rivers above seasonal average.',
      affected: ['Makurdi Valley Dairy', 'Benue Lowland Farm', 'Kogi River Ranch'],
      date: '2025-09-12',
    },
    {
      type: 'Flood',
      icon: '🌊',
      color: 'border-blue-200 bg-blue-50',
      label: 'text-blue-600',
      severity: 'WATCH',
      sevColor: 'bg-amber-100 text-amber-700',
      title: 'Niger Inland Delta — Water Level Rising',
      desc: 'Seasonal inundation risk in Niger State lowlands. Monitor pasture access.',
      affected: ['Minna Modern Dairy'],
      date: '2025-09-08',
    },
    {
      type: 'Drought',
      icon: '☀️',
      color: 'border-orange-200 bg-orange-50',
      label: 'text-orange-700',
      severity: 'HIGH',
      sevColor: 'bg-red-100 text-red-700',
      title: 'Katsina Pasture Drought',
      desc: 'Below-average rainfall. Feed scarcity risk for northern farms. Activity decline expected.',
      affected: ['Funtua Dairy Co.', 'Katsina Agro Ranch'],
      date: '2025-09-10',
    },
    {
      type: 'Disease',
      icon: '🦠',
      color: 'border-red-200 bg-red-50',
      label: 'text-red-700',
      severity: 'ALERT',
      sevColor: 'bg-red-100 text-red-700',
      title: 'FMD Outbreak — Taraba Corridor',
      desc: 'Foot-and-mouth confirmed in Wukari LGA. Movement restrictions in effect.',
      affected: ['Wukari Dairy Cooperative'],
      date: '2025-09-14',
    },
    {
      type: 'Disease',
      icon: '🦠',
      color: 'border-red-100 bg-red-50/50',
      label: 'text-red-600',
      severity: 'WATCH',
      sevColor: 'bg-amber-100 text-amber-700',
      title: 'CBPP Surveillance — Nasarawa',
      desc: 'Contagious Bovine Pleuropneumonia cases reported. Vaccination drive recommended.',
      affected: ['Kaana Cattle Farm', 'Nasarawa Agro Livestock'],
      date: '2025-09-06',
    },
  ];

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-5">
      <div className="flex items-center gap-2 mb-3">
        <span className="w-2.5 h-2.5 rounded-full bg-red-500 animate-pulse" />
        <p className="text-sm font-semibold text-gray-900">Environmental & Disease Alerts</p>
      </div>
      <div className="space-y-2.5">
        {alerts.map((a, i) => (
          <div key={i} className={`rounded-lg border px-3 py-2.5 ${a.color}`}>
            <div className="flex items-start justify-between gap-2">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5 mb-0.5">
                  <span className={`text-xs font-bold px-1.5 py-0.5 rounded ${a.sevColor}`}>{a.severity}</span>
                  <p className={`text-xs font-semibold ${a.label}`}>{a.title}</p>
                </div>
                <p className="text-xs text-gray-600 leading-snug">{a.desc}</p>
                <p className="text-xs text-gray-400 mt-1">
                  Affected: {a.affected.join(' · ')}
                </p>
              </div>
              <p className="text-xs text-gray-400 flex-shrink-0">{a.date}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// Regional production trend
function RegionalTrend() {
  const data = MONTHS.map((m, i) => {
    const totalL = FARMS.reduce((s, f) => s + f.herd_size * f.monthly_milk_L[i], 0);
    return { month: m, volume: Math.round(totalL), farms: FARMS.length };
  });
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-5">
      <p className="text-sm font-semibold text-gray-900 mb-1">Regional Milk Production — Apr–Sep 2025</p>
      <p className="text-xs text-gray-400 mb-3">Daily aggregate across all {FARMS.length} farms · litres/day</p>
      <ResponsiveContainer width="100%" height={170}>
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

function PerformanceScatter() {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-5">
      <p className="text-sm font-semibold text-gray-900 mb-1">Activity Rate vs Milk Yield — All Farms</p>
      <p className="text-xs text-gray-400 mb-3">Each point = one farm · colour = performance tier</p>
      <ResponsiveContainer width="100%" height={200}>
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
                  <p>Activity: <b>{d.x}%</b> · Milk: <b>{d.y} L/cow</b></p>
                  <p>Disease events: <b>{d.disease}</b></p>
                </div>
              );
            }}
          />
          <Scatter data={FARMS.map(f => ({ x: f.avg_activity_rate, y: f.avg_milk_yield_L, name: f.name, tier: f.tier, disease: f.disease_events }))} name="Farms">
            {FARMS.map((f, i) => <Cell key={i} fill={TIER_COLOR[f.tier]} fillOpacity={0.8} />)}
          </Scatter>
        </ScatterChart>
      </ResponsiveContainer>
      <div className="flex gap-4 mt-1">
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
        <KPI label="Monitored Farms" value={FARMS.length} sub={NETWORK.region} color="text-blue-700" />
        <KPI label="Total Herd" value={totalHerd.toLocaleString()} sub="animals across region" color="text-green-700" />
        <KPI label="Daily Milk Output" value={`${(totalDailyMilk/1000).toFixed(1)}k L`} sub="aggregate production" color="text-teal-700" />
        <KPI label="Disease Alerts" value={alertFarms} sub={`of ${FARMS.length} farms flagged`} color={alertFarms > 3 ? 'text-red-600' : 'text-amber-600'} />
      </div>

      {/* Regional map — full width */}
      <RegionalMap />

      {/* Environmental alerts + disease surveillance */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <EnvironmentalAlerts />
        <DiseaseAlerts />
      </div>

      {/* Trend + distribution */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <div className="lg:col-span-2"><RegionalTrend /></div>
        <ActivityDistribution />
      </div>

      {/* Scatter */}
      <PerformanceScatter />

      {/* Farm network table */}
      <FarmNetworkTable />

      <p className="text-xs text-gray-400 text-center pb-4">
        NDIC Platform · {FARMS.length} farms · {NETWORK.region} · Bodit behavioural sensor · {NETWORK.period}
      </p>
    </div>
  );
}
