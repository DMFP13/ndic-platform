import React, { useState, useMemo } from 'react';
import {
  BarChart, Bar, ScatterChart, Scatter, XAxis, YAxis,
  CartesianGrid, Tooltip, ResponsiveContainer, Cell, ReferenceLine,
} from 'recharts';
import RESEARCH from '../data/research_data.json';
import NETWORK  from '../data/farm_network.json';

const COWS     = RESEARCH.cow_summary;
const P4_READS = RESEARCH.p4_readings;
const FARMS    = NETWORK.farms;

// ── Urgency scoring ──────────────────────────────────────────────────────────
const coughRate = c => c.n_days > 0 ? c.total_coughing / c.n_days : 0;

function urgencyScore(c) {
  const cr    = coughRate(c);
  const actDrop = Math.max(0, c.avg_activity_rate - c.latest_activity);
  const lowAct  = Math.max(0, 60 - c.latest_activity);
  return (cr * 1.8) + (lowAct * 0.6) + (actDrop * 0.4);
}

function urgencyLabel(score) {
  if (score >= 14) return { label: 'Urgent',   cls: 'bg-red-100 text-red-700 border-red-200' };
  if (score >= 7)  return { label: 'Review',   cls: 'bg-amber-100 text-amber-700 border-amber-200' };
  return              { label: 'Stable',   cls: 'bg-green-100 text-green-700 border-green-200' };
}

// Latest P4 result per cow tag
const latestP4 = useMemo => {
  const map = {};
  P4_READS.forEach(r => {
    if (!map[r.cow] || r.date > map[r.cow].date) map[r.cow] = r;
  });
  return map;
};
const P4_MAP = (() => {
  const m = {};
  P4_READS.forEach(r => { if (!m[r.cow] || r.date > m[r.cow].date) m[r.cow] = r; });
  return m;
})();

const P4_COLOR = { Visible: '#16a34a', 'Faint, but visible': '#f59e0b', 'Not visible': '#dc2626', Invalid: '#9ca3af' };

function KPI({ label, value, sub, color = 'text-gray-900' }) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <p className="text-xs text-gray-500 font-medium">{label}</p>
      <p className={`text-2xl font-bold mt-1 ${color}`}>{value}</p>
      {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
    </div>
  );
}

// ── Priority Case Queue ───────────────────────────────────────────────────────
function PriorityQueue() {
  const [filter, setFilter] = useState('all');
  const [sort, setSort]     = useState('urgency');

  const scored = useMemo(() => COWS.map(c => ({
    ...c,
    coughPerDay: coughRate(c),
    score: urgencyScore(c),
    urgency: urgencyLabel(urgencyScore(c)),
    p4: P4_MAP[c.tag] || null,
  })), []);

  const filtered = useMemo(() => {
    let rows = scored;
    if (filter === 'urgent') rows = rows.filter(r => r.score >= 14);
    if (filter === 'review') rows = rows.filter(r => r.score >= 7 && r.score < 14);
    if (filter === 'stable') rows = rows.filter(r => r.score < 7);
    if (sort === 'urgency')  rows = [...rows].sort((a, b) => b.score - a.score);
    if (sort === 'cough')    rows = [...rows].sort((a, b) => b.coughPerDay - a.coughPerDay);
    if (sort === 'activity') rows = [...rows].sort((a, b) => a.latest_activity - b.latest_activity);
    return rows;
  }, [scored, filter, sort]);

  const urgentCount = scored.filter(r => r.score >= 14).length;
  const reviewCount = scored.filter(r => r.score >= 7 && r.score < 14).length;

  return (
    <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
      <div className="px-5 py-3 border-b border-gray-100 flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          {urgentCount > 0 && <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />}
          <p className="text-sm font-semibold text-gray-900">Priority Case Queue — {COWS.length} Animals</p>
        </div>
        <div className="flex gap-2 flex-wrap">
          {[['all','All'], ['urgent','Urgent'], ['review','Review'], ['stable','Stable']].map(([v, l]) => (
            <button key={v} onClick={() => setFilter(v)}
              className={`px-2 py-0.5 rounded text-xs font-medium border transition-colors ${filter === v ? 'bg-gray-800 text-white border-gray-800' : 'bg-white text-gray-600 border-gray-200 hover:border-gray-400'}`}>
              {l}{v === 'urgent' && urgentCount > 0 ? ` (${urgentCount})` : v === 'review' && reviewCount > 0 ? ` (${reviewCount})` : ''}
            </button>
          ))}
          <select className="text-xs border border-gray-200 rounded px-2 py-0.5" value={sort} onChange={e => setSort(e.target.value)}>
            <option value="urgency">Sort: Urgency</option>
            <option value="cough">Sort: Coughing</option>
            <option value="activity">Sort: Activity (low first)</option>
          </select>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-2 text-left text-xs font-semibold text-gray-500">Animal</th>
              <th className="px-4 py-2 text-right text-xs font-semibold text-gray-500">Latest Activity</th>
              <th className="px-4 py-2 text-right text-xs font-semibold text-gray-500">Avg Activity</th>
              <th className="px-4 py-2 text-right text-xs font-semibold text-gray-500">Cough / day</th>
              <th className="px-4 py-2 text-right text-xs font-semibold text-gray-500">Rumination</th>
              <th className="px-4 py-2 text-xs font-semibold text-gray-500">P4 (latest)</th>
              <th className="px-4 py-2 text-xs font-semibold text-gray-500">Priority</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((c, i) => (
              <tr key={c.cow_id} className={`border-t border-gray-50 ${i % 2 ? 'bg-gray-50/30' : ''}`}>
                <td className="px-4 py-2">
                  <p className="text-xs font-semibold text-gray-800">{c.cow_id}</p>
                  <p className="text-xs text-gray-400">Tag {c.tag}</p>
                </td>
                <td className="px-4 py-2 text-right">
                  <span className={`text-sm font-bold ${c.latest_activity < 50 ? 'text-red-600' : c.latest_activity < 65 ? 'text-amber-600' : 'text-green-700'}`}>
                    {c.latest_activity.toFixed(1)}%
                  </span>
                </td>
                <td className="px-4 py-2 text-right text-sm text-gray-600">{c.avg_activity_rate.toFixed(1)}%</td>
                <td className="px-4 py-2 text-right">
                  <span className={`text-sm font-semibold ${c.coughPerDay > 8 ? 'text-red-600' : c.coughPerDay > 4 ? 'text-amber-600' : 'text-gray-600'}`}>
                    {c.coughPerDay.toFixed(1)}
                  </span>
                </td>
                <td className="px-4 py-2 text-right text-sm text-gray-600">{c.latest_rumination ? Math.round(c.latest_rumination) : '—'} min</td>
                <td className="px-4 py-2">
                  {c.p4 ? (
                    <span className="text-xs font-medium px-1.5 py-0.5 rounded" style={{ background: P4_COLOR[c.p4.lft_lower] + '20', color: P4_COLOR[c.p4.lft_lower] }}>
                      {c.p4.lft_lower === 'Faint, but visible' ? 'Faint' : c.p4.lft_lower}
                    </span>
                  ) : <span className="text-xs text-gray-400">No test</span>}
                </td>
                <td className="px-4 py-2">
                  <span className={`text-xs font-semibold px-2 py-0.5 rounded-full border ${c.urgency.cls}`}>
                    {c.urgency.label}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="px-5 py-2 border-t border-gray-50">
        <p className="text-xs text-gray-400">Urgency = coughing rate + activity drop + low-activity penalty · Bodit sensor data</p>
      </div>
    </div>
  );
}

// ── Coughing Rate Chart ───────────────────────────────────────────────────────
function CoughingChart() {
  const data = [...COWS]
    .map(c => ({ tag: c.tag.slice(-4), rate: parseFloat(coughRate(c).toFixed(1)), activity: c.avg_activity_rate }))
    .sort((a, b) => b.rate - a.rate);

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-5">
      <p className="text-sm font-semibold text-gray-900 mb-1">Coughing Events / Day — All Animals</p>
      <p className="text-xs text-gray-400 mb-3">Higher rate may indicate CBPP, respiratory infection or dust exposure</p>
      <ResponsiveContainer width="100%" height={180}>
        <BarChart data={data} margin={{ top: 5, right: 10, left: -10, bottom: 10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis dataKey="tag" tick={{ fontSize: 9 }} angle={-45} textAnchor="end" interval={0} />
          <YAxis tick={{ fontSize: 10 }} />
          <ReferenceLine y={8} stroke="#dc2626" strokeDasharray="4 2"
            label={{ value: 'Alert threshold', fontSize: 9, fill: '#dc2626', position: 'insideTopRight' }} />
          <Tooltip formatter={v => [`${v} events/day`, 'Coughing rate']} />
          <Bar dataKey="rate" radius={[3, 3, 0, 0]}>
            {data.map((d, i) => (
              <Cell key={i} fill={d.rate > 8 ? '#dc2626' : d.rate > 4 ? '#f59e0b' : '#16a34a'} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

// ── Activity vs Rumination ────────────────────────────────────────────────────
function ActivityRuminationScatter() {
  const data = COWS.map(c => ({
    x: c.avg_activity_rate,
    y: c.avg_rumination_min,
    tag: c.tag,
    score: urgencyScore(c),
  }));

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-5">
      <p className="text-sm font-semibold text-gray-900 mb-1">Activity vs Rumination</p>
      <p className="text-xs text-gray-400 mb-3">Low rumination + low activity = health concern · colour = urgency</p>
      <ResponsiveContainer width="100%" height={180}>
        <ScatterChart margin={{ top: 5, right: 10, left: -10, bottom: 10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis type="number" dataKey="x" name="Activity %" domain={[40, 95]} tick={{ fontSize: 10 }}
            label={{ value: 'Activity %', position: 'insideBottom', offset: -5, fontSize: 10 }} />
          <YAxis type="number" dataKey="y" name="Rumination min" tick={{ fontSize: 10 }}
            label={{ value: 'Rum. min', angle: -90, position: 'insideLeft', fontSize: 9, offset: 10 }} />
          <ReferenceLine x={60} stroke="#f59e0b" strokeDasharray="4 2" />
          <ReferenceLine y={250} stroke="#f59e0b" strokeDasharray="4 2" />
          <Tooltip cursor={{ strokeDasharray: '3 3' }}
            content={({ payload }) => {
              if (!payload?.length) return null;
              const d = payload[0].payload;
              return (
                <div className="bg-white border border-gray-200 rounded shadow px-3 py-2 text-xs">
                  <p className="font-semibold">Tag {d.tag}</p>
                  <p>Activity: <b>{d.x.toFixed(1)}%</b> · Rumination: <b>{d.y.toFixed(0)} min</b></p>
                </div>
              );
            }}
          />
          <Scatter data={data}>
            {data.map((d, i) => (
              <Cell key={i} fill={d.score >= 14 ? '#dc2626' : d.score >= 7 ? '#f59e0b' : '#16a34a'} fillOpacity={0.8} />
            ))}
          </Scatter>
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}

// ── P4 Status Panel ───────────────────────────────────────────────────────────
function P4Panel() {
  const counts = { Visible: 0, 'Faint, but visible': 0, 'Not visible': 0, 'No test': 0 };
  const cowsWithP4 = new Set();

  P4_READS.forEach(r => cowsWithP4.add(r.cow));
  COWS.forEach(c => {
    const p = P4_MAP[c.tag];
    if (!p) counts['No test']++;
    else {
      const k = p.lft_lower;
      if (counts[k] !== undefined) counts[k]++;
      else counts[k] = 1;
    }
  });

  const barData = Object.entries(counts).filter(([, v]) => v > 0).map(([k, v]) => ({
    label: k === 'Faint, but visible' ? 'Faint' : k,
    full: k,
    count: v,
    color: k === 'Visible' ? '#16a34a' : k === 'Faint, but visible' ? '#f59e0b' : k === 'Not visible' ? '#dc2626' : '#9ca3af',
  }));

  // Animals in estrus (Not visible = low P4)
  const estrus = COWS.filter(c => P4_MAP[c.tag]?.lft_lower === 'Not visible');

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-5">
      <p className="text-sm font-semibold text-gray-900 mb-1">P4 Rapid LFT Status — Latest Results</p>
      <p className="text-xs text-gray-400 mb-3">Visible = luteal · Not visible = estrus window</p>

      <div className="flex gap-3 mb-4">
        {barData.map(b => (
          <div key={b.label} className="flex-1 text-center">
            <div className="text-2xl font-bold" style={{ color: b.color }}>{b.count}</div>
            <div className="text-xs text-gray-500 mt-0.5">{b.label}</div>
          </div>
        ))}
      </div>

      {estrus.length > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-lg px-3 py-2 mb-3">
          <p className="text-xs font-semibold text-red-700 mb-1">Estrus Window — {estrus.length} animal{estrus.length > 1 ? 's' : ''}</p>
          <p className="text-xs text-gray-600">{estrus.map(c => `Tag ${c.tag}`).join(' · ')}</p>
          <p className="text-xs text-gray-400 mt-1">Low P4 detected · AI / breeding action recommended</p>
        </div>
      )}

      <ResponsiveContainer width="100%" height={100}>
        <BarChart data={barData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis dataKey="label" tick={{ fontSize: 10 }} />
          <YAxis tick={{ fontSize: 10 }} />
          <Tooltip formatter={(v, n, p) => [v, p.payload.full]} />
          <Bar dataKey="count" radius={[4, 4, 0, 0]}>
            {barData.map((b, i) => <Cell key={i} fill={b.color} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <p className="mt-2 text-xs text-gray-400">P4 Rapid LFT · {P4_READS.length} total readings</p>
    </div>
  );
}

// ── Disease Alerts from Farm Network ─────────────────────────────────────────
function FarmDiseaseAlerts() {
  const alerts = [...FARMS]
    .filter(f => f.disease_events > 0)
    .sort((a, b) => b.disease_events - a.disease_events)
    .slice(0, 8);

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-5">
      <div className="flex items-center gap-2 mb-3">
        <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
        <p className="text-sm font-semibold text-gray-900">Farm Disease Events — Network Overview</p>
      </div>
      <div className="space-y-2">
        {alerts.map(f => (
          <div key={f.id} className="flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-gray-800">{f.name}</p>
              <p className="text-xs text-gray-400">{f.lga}, {f.state} · Cough idx {f.coughing_index}</p>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-24 bg-gray-100 rounded-full h-2 overflow-hidden">
                <div className="h-full rounded-full" style={{ width: `${Math.min(100, f.disease_events * 8)}%`, background: f.disease_events >= 8 ? '#dc2626' : f.disease_events >= 5 ? '#f59e0b' : '#16a34a' }} />
              </div>
              <span className={`text-xs font-bold w-5 text-right ${f.disease_events >= 8 ? 'text-red-600' : f.disease_events >= 5 ? 'text-amber-600' : 'text-gray-600'}`}>
                {f.disease_events}
              </span>
            </div>
          </div>
        ))}
      </div>
      <p className="mt-3 text-xs text-gray-400">{FARMS.length} farms monitored · Bodit coughing index</p>
    </div>
  );
}

// ── Vaccination Schedule (realistic mock) ─────────────────────────────────────
function VaccinationSchedule() {
  const schedule = [
    { animal: 'COW-10000248', tag: '10000248', vaccine: 'FMD Trivalent',         due: '2025-09-18', status: 'overdue',   notes: 'Booster — 6-month cycle' },
    { animal: 'COW-10000247', tag: '10000247', vaccine: 'CBPP (Mycoplasma)',      due: '2025-09-22', status: 'overdue',   notes: 'Annual — high coughing index flag' },
    { animal: 'COW-10000251', tag: '10000251', vaccine: 'Brucellosis (S19)',      due: '2025-09-28', status: 'due',       notes: 'Heifers only' },
    { animal: 'COW-10000245', tag: '10000245', vaccine: 'Lumpy Skin Disease',     due: '2025-10-05', status: 'upcoming',  notes: 'Annual LSD booster' },
    { animal: 'COW-10000253', tag: '10000253', vaccine: 'Blackleg (Clostridial)', due: '2025-10-12', status: 'upcoming',  notes: '6-month booster' },
    { animal: 'COW-10000249', tag: '10000249', vaccine: 'FMD Trivalent',         due: '2025-10-18', status: 'upcoming',  notes: 'Booster' },
  ];

  const statusStyle = {
    overdue:  'bg-red-100 text-red-700 border-red-200',
    due:      'bg-amber-100 text-amber-700 border-amber-200',
    upcoming: 'bg-blue-50 text-blue-600 border-blue-200',
  };

  return (
    <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
      <div className="px-5 py-3 border-b border-gray-100">
        <p className="text-sm font-semibold text-gray-900">Vaccination Schedule</p>
        <p className="text-xs text-gray-400">Upcoming and overdue — next 30 days</p>
      </div>
      <div className="divide-y divide-gray-50">
        {schedule.map((s, i) => (
          <div key={i} className="px-5 py-3 flex items-center justify-between gap-4">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <p className="text-xs font-semibold text-gray-800">{s.vaccine}</p>
                <span className={`text-xs px-1.5 py-0.5 rounded border font-medium ${statusStyle[s.status]}`}>
                  {s.status}
                </span>
              </div>
              <p className="text-xs text-gray-500 mt-0.5">Tag {s.tag} · {s.notes}</p>
            </div>
            <p className="text-xs text-gray-500 flex-shrink-0 font-medium">{s.due}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Main Dashboard ─────────────────────────────────────────────────────────────
export default function VetDashboard() {
  const urgentCount  = COWS.filter(c => urgencyScore(c) >= 14).length;
  const reviewCount  = COWS.filter(c => urgencyScore(c) >= 7 && urgencyScore(c) < 14).length;
  const avgCough     = (COWS.reduce((s, c) => s + coughRate(c), 0) / COWS.length).toFixed(1);
  const p4Tested     = new Set(P4_READS.map(r => r.cow)).size;
  const overdueVax   = 2;

  return (
    <div className="p-6 space-y-5">
      <div>
        <h1 className="text-xl font-bold text-gray-900">Veterinary Health Dashboard</h1>
        <p className="text-sm text-gray-500 mt-0.5">Bodit sensor data · P4 Rapid LFT · {COWS.length} animals monitored</p>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KPI label="Urgent Cases"       value={urgentCount}   sub="require immediate review"       color={urgentCount > 0 ? 'text-red-600' : 'text-green-700'} />
        <KPI label="Under Review"       value={reviewCount}   sub="monitor closely"                color="text-amber-600" />
        <KPI label="Avg Cough Rate"     value={`${avgCough}/day`} sub="herd average · Bodit sensor" color={parseFloat(avgCough) > 6 ? 'text-red-600' : 'text-gray-900'} />
        <KPI label="Overdue Vaccines"   value={overdueVax}    sub="scheduled this week"            color={overdueVax > 0 ? 'text-amber-600' : 'text-green-700'} />
      </div>

      {/* Priority queue — full width */}
      <PriorityQueue />

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <CoughingChart />
        <ActivityRuminationScatter />
      </div>

      {/* P4 + disease alerts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <P4Panel />
        <FarmDiseaseAlerts />
      </div>

      {/* Vaccination schedule */}
      <VaccinationSchedule />
    </div>
  );
}
