import React, { useState, useEffect, useCallback, useId } from 'react';
import { Link } from 'react-router-dom';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  BarChart, Bar,
} from 'recharts';
import {
  RefreshCw, ChevronDown, ChevronUp, Activity, Droplets,
  AlertTriangle, CheckCircle, Users, DollarSign,
} from 'lucide-react';
import Card from './shared/Card.jsx';
import MetricCard from './shared/MetricCard.jsx';
import AlertBox from './shared/AlertBox.jsx';
import StatusBadge from './shared/StatusBadge.jsx';
import Spinner from './shared/Spinner.jsx';
import { getFarmDashboard } from '../api/endpoints.js';
import { useAuth } from '../context/AuthContext.jsx';

function SectionError({ onRetry }) {
  return (
    <div className="flex flex-col items-center py-6 gap-2">
      <p className="text-sm text-gray-500">Data unavailable</p>
      <button onClick={onRetry} className="flex items-center gap-1 text-xs text-blue-600 hover:underline">
        <RefreshCw size={12} /> Retry
      </button>
    </div>
  );
}

function HealthBar({ score }) {
  const color = score >= 70 ? 'bg-green-500' : score >= 40 ? 'bg-amber-500' : 'bg-red-500';
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-gray-200 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${score}%` }} />
      </div>
      <span className="text-xs tabular-nums text-gray-700 w-6">{score}</span>
    </div>
  );
}

function ProbBar({ label, value, color }) {
  const pct = Math.round(value * 100);
  return (
    <div className="mb-2">
      <div className="flex justify-between text-xs text-gray-600 mb-0.5">
        <span>{label}</span>
        <span className="tabular-nums font-medium">{pct}%</span>
      </div>
      <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function MiniLineChart({ data, color, height = 60 }) {
  if (!data || data.length === 0) return null;
  const chartData = data.map((v, i) => ({ i, v }));
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={chartData} margin={{ top: 2, right: 2, left: 2, bottom: 2 }}>
        <Line type="monotone" dataKey="v" stroke={color} strokeWidth={1.5} dot={false} />
        <YAxis domain={['auto', 'auto']} hide />
        <XAxis dataKey="i" hide />
      </LineChart>
    </ResponsiveContainer>
  );
}

// Section B: Animal Profiles
function AnimalTable({ animals, onRefetch }) {
  const [statusFilter, setStatusFilter] = useState('all');
  const [expandedId, setExpandedId] = useState(null);

  const filtered = statusFilter === 'all'
    ? animals
    : animals.filter((a) => a.status === statusFilter);

  return (
    <div>
      {/* Filter */}
      <div className="flex gap-2 mb-3 flex-wrap">
        {['all', 'healthy', 'at_risk', 'critical'].map((f) => (
          <button
            key={f}
            onClick={() => setStatusFilter(f)}
            className={`px-2.5 py-1 text-xs rounded-full border font-medium transition-colors ${statusFilter === f ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-gray-600 border-gray-300 hover:bg-gray-50'}`}
          >
            {f === 'all' ? 'All' : f === 'at_risk' ? 'At Risk' : f.charAt(0).toUpperCase() + f.slice(1)}
            {' '}({f === 'all' ? animals.length : animals.filter((a) => a.status === f).length})
          </button>
        ))}
      </div>

      <div className="overflow-x-auto table-scroll">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200">
              <th className="text-left py-2 px-2 text-xs font-semibold text-gray-600">Tag</th>
              <th className="text-left py-2 px-2 text-xs font-semibold text-gray-600">Breed</th>
              <th className="text-left py-2 px-2 text-xs font-semibold text-gray-600">Status</th>
              <th className="text-left py-2 px-2 text-xs font-semibold text-gray-600 w-32">Health Score</th>
              <th className="text-right py-2 px-2 text-xs font-semibold text-gray-600">Yield (L/day)</th>
              <th className="text-left py-2 px-2 text-xs font-semibold text-gray-600">Action</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((animal) => (
              <React.Fragment key={animal.id}>
                <tr
                  className={`border-b border-gray-100 hover:bg-gray-50 cursor-pointer ${expandedId === animal.id ? 'bg-gray-50' : ''}`}
                  onClick={() => setExpandedId(expandedId === animal.id ? null : animal.id)}
                >
                  <td className="py-2 px-2 font-medium text-gray-900">{animal.tag}</td>
                  <td className="py-2 px-2 text-gray-600 capitalize">{animal.breed}</td>
                  <td className="py-2 px-2"><StatusBadge status={animal.status} /></td>
                  <td className="py-2 px-2 w-32"><HealthBar score={animal.health_score} /></td>
                  <td className="py-2 px-2 text-right tabular-nums text-gray-700">{animal.yield}</td>
                  <td className="py-2 px-2">
                    <div className="flex items-center gap-2">
                      <button
                        className="text-xs text-blue-600 hover:underline"
                        onClick={(e) => { e.stopPropagation(); setExpandedId(expandedId === animal.id ? null : animal.id); }}
                      >
                        {expandedId === animal.id ? 'Collapse' : 'Details'}
                      </button>
                      <Link
                        to={`/farm/animals/${animal.id}`}
                        className="text-xs text-purple-600 hover:underline font-medium"
                        onClick={(e) => e.stopPropagation()}
                      >
                        Passport →
                      </Link>
                    </div>
                  </td>
                </tr>
                {expandedId === animal.id && (
                  <tr className="bg-blue-50/40">
                    <td colSpan={6} className="px-4 py-4">
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        {/* Charts */}
                        <div>
                          <p className="text-xs font-semibold text-gray-700 mb-1">Temperature — 7 days (°C)</p>
                          <MiniLineChart data={animal.temp_history} color="#EF4444" height={64} />
                        </div>
                        <div>
                          <p className="text-xs font-semibold text-gray-700 mb-1">Milk Yield — 7 days (L)</p>
                          <MiniLineChart data={animal.yield_history} color="#2563EB" height={64} />
                        </div>
                        {/* AI predictions */}
                        <div>
                          <p className="text-xs font-semibold text-gray-700 mb-2">AI Predictions</p>
                          <ProbBar label="Estrus probability" value={animal.estrus_prob} color="bg-purple-500" />
                          <ProbBar label="Fever probability" value={animal.fever_prob} color="bg-red-500" />
                          <ProbBar label="Mastitis risk" value={animal.mastitis_risk} color="bg-amber-500" />
                        </div>
                      </div>
                      {/* Recommendation */}
                      <div className="mt-3 p-2 bg-white rounded border border-blue-100">
                        <p className="text-xs font-semibold text-gray-700">AI Recommendation</p>
                        <p className="text-xs text-gray-600 mt-0.5">{animal.recommendation}</p>
                      </div>
                      {/* Treatment log */}
                      {animal.treatment_log && animal.treatment_log.length > 0 && (
                        <div className="mt-3">
                          <p className="text-xs font-semibold text-gray-700 mb-1">Treatment Log</p>
                          <div className="space-y-1">
                            {animal.treatment_log.slice(0, 3).map((t, i) => (
                              <div key={i} className="flex gap-3 text-xs text-gray-600">
                                <span className="text-gray-400 flex-shrink-0">{t.date}</span>
                                <span>{t.action}</span>
                                <span className="text-gray-400 ml-auto flex-shrink-0">{t.vet}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// Section C: AI Health Insights
function AIHealthInsights({ animals }) {
  const estrusAnimals = animals.filter((a) => a.estrus_prob > 0.6);
  const feverAnimals = animals.filter((a) => a.fever_prob > 0.5);
  const mastitisAnimals = animals.filter((a) => a.mastitis_risk > 0.4);

  return (
    <div className="space-y-3">
      {estrusAnimals.length > 0 && (
        <AlertBox
          level="info"
          title={`Estrus Detected — ${estrusAnimals.length} animal${estrusAnimals.length > 1 ? 's' : ''}`}
          message={`${estrusAnimals.map((a) => a.tag).join(', ')} — Optimal AI window. Schedule insemination within 12-18 hours for best conception rate.`}
        />
      )}
      {feverAnimals.map((a) => (
        <AlertBox
          key={a.id}
          level={a.fever_prob > 0.8 ? 'critical' : 'warning'}
          title={`Fever Alert — ${a.tag}`}
          message={`${Math.round(a.fever_prob * 100)}% fever probability. ${a.fever_prob > 0.8 ? 'Isolate immediately and begin treatment.' : 'Monitor closely — temperature trending up.'}`}
        />
      ))}
      {mastitisAnimals.length > 0 && (
        <AlertBox
          level="warning"
          title={`Mastitis Risk — ${mastitisAnimals.length} animal${mastitisAnimals.length > 1 ? 's' : ''}`}
          message={`${mastitisAnimals.map((a) => a.tag).join(', ')} — Perform CMT and begin teat dipping protocol immediately.`}
        />
      )}
      {estrusAnimals.length === 0 && feverAnimals.length === 0 && mastitisAnimals.length === 0 && (
        <AlertBox level="success" title="No Active Alerts" message="All monitored indicators are within normal range." />
      )}
    </div>
  );
}

// Section D: Financial Forecast
function FinancialForecast({ data }) {
  if (!data) return null;

  const metrics = [
    { label: 'Cost per Litre', value: `₦${(data.cost_per_liter || 0).toLocaleString()}`, trend: null, color: 'gray' },
    { label: 'Monthly Total Cost', value: `₦${((data.monthly_total_cost || 0) / 1000000).toFixed(2)}M`, trend: null, color: 'gray' },
    { label: 'Projected Revenue', value: `₦${((data.projected_revenue || 0) / 1000000).toFixed(2)}M`, trend: null, color: 'blue' },
    { label: 'Net Margin', value: `${data.net_margin_pct || 0}%`, trend: null, color: 'green' },
  ];

  const sparkData = (data.sparkline || []).map((v, i) => ({ i, v }));

  return (
    <div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
        {metrics.map((m) => (
          <MetricCard key={m.label} {...m} />
        ))}
      </div>
      {sparkData.length > 0 && (
        <div>
          <p className="text-xs text-gray-500 mb-1">Net margin trend — last 6 months (%)</p>
          <ResponsiveContainer width="100%" height={60}>
            <LineChart data={sparkData} margin={{ top: 2, right: 4, left: 4, bottom: 2 }}>
              <Line type="monotone" dataKey="v" stroke="#22C55E" strokeWidth={2} dot={false} />
              <YAxis domain={['auto', 'auto']} hide />
              <XAxis dataKey="i" hide />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}

// Section E: Interventions Log
function InterventionsLog({ interventions }) {
  const [open, setOpen] = useState({ recommended: true, in_progress: false, completed: false });

  const sections = [
    { key: 'recommended', label: 'Recommended', data: interventions.recommended || [], color: 'text-amber-700' },
    { key: 'in_progress', label: 'In Progress', data: interventions.in_progress || [], color: 'text-blue-700' },
    { key: 'completed', label: 'Completed (last 7 days)', data: interventions.completed || [], color: 'text-green-700' },
  ];

  return (
    <div className="space-y-2">
      {sections.map(({ key, label, data, color }) => (
        <div key={key} className="border border-gray-200 rounded-lg overflow-hidden">
          <button
            className="w-full flex items-center justify-between px-4 py-2.5 bg-white hover:bg-gray-50 text-left"
            onClick={() => setOpen((prev) => ({ ...prev, [key]: !prev[key] }))}
          >
            <span className={`text-sm font-semibold ${color}`}>{label} ({data.length})</span>
            {open[key] ? <ChevronUp size={14} className="text-gray-400" /> : <ChevronDown size={14} className="text-gray-400" />}
          </button>
          {open[key] && (
            <div className="border-t border-gray-100">
              {data.length === 0 ? (
                <p className="px-4 py-3 text-sm text-gray-500">No items.</p>
              ) : (
                data.map((item, i) => (
                  <div key={i} className="px-4 py-2 border-b border-gray-100 last:border-0">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <span className="text-xs font-semibold text-gray-800">{item.tag}</span>
                        <span className="text-xs text-gray-500 ml-2">{item.condition}</span>
                      </div>
                      <span className="text-xs text-gray-400 flex-shrink-0">Due: {item.due}</span>
                    </div>
                    <p className="text-xs text-gray-600 mt-0.5">{item.action}</p>
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

// Section F: Climate + Feed
function ClimateSection({ climate }) {
  if (!climate) return null;

  const riskColor = { low: 'text-green-700 bg-green-50', medium: 'text-amber-700 bg-amber-50', high: 'text-red-700 bg-red-50' };
  const barData = (climate.drought_forecast || []).slice(0, 30);

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <span className="text-sm text-gray-700">Current climate risk:</span>
        <span className={`text-xs font-semibold px-2 py-1 rounded ${riskColor[climate.risk_level] || riskColor.medium}`}>
          {(climate.risk_level || 'unknown').toUpperCase()}
        </span>
      </div>
      <p className="text-xs text-gray-600 bg-amber-50 border border-amber-100 rounded p-2">{climate.recommendation}</p>
      <div>
        <p className="text-xs text-gray-500 mb-1">30-day drought risk forecast</p>
        <ResponsiveContainer width="100%" height={100}>
          <BarChart data={barData} margin={{ top: 2, right: 2, left: 2, bottom: 2 }}>
            <XAxis dataKey="day" tick={false} />
            <YAxis domain={[0, 100]} hide />
            <Tooltip
              formatter={(v) => [`${v.toFixed(0)}%`, 'Drought risk']}
              labelFormatter={(l) => `Day ${l}`}
              contentStyle={{ fontSize: 11, padding: '4px 8px' }}
            />
            <Bar dataKey="risk" fill="#F59E0B" radius={[1, 1, 0, 0]} maxBarSize={8} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

// Main FarmDashboard
export default function FarmDashboard() {
  const { user } = useAuth();
  const farmId = user?.org_id || 'farm_001';

  const [dashData, setDashData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  async function loadData() {
    setLoading(true); setError(false);
    try {
      const res = await getFarmDashboard(farmId);
      setDashData(res.data);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadData(); }, [farmId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Spinner size="lg" label="Loading farm data…" />
      </div>
    );
  }

  if (error || !dashData) {
    return <SectionError onRetry={loadData} />;
  }

  const { summary, animals, financials, interventions, climate } = dashData;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-bold text-gray-900">Farm Intelligence Dashboard</h1>
        <p className="text-sm text-gray-500 mt-0.5">Herd health, AI predictions, and financial performance</p>
      </div>

      {/* Section A: Herd Summary */}
      <section aria-label="Herd Summary">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <MetricCard label="Total Animals" value={summary.total_animals} trend={null} icon={Users} color="blue" />
          <MetricCard label="Healthy" value={summary.healthy} trend={summary.health_trend} icon={CheckCircle} color="green" />
          <MetricCard label="At Risk / Critical" value={`${summary.at_risk + summary.critical}`} trend={null} icon={AlertTriangle} color="amber" />
          <MetricCard label="Daily Milk Yield" value={`${summary.daily_milk_yield} L`} trend={summary.yield_trend} icon={Droplets} color="blue" />
        </div>
      </section>

      {/* Section C: AI Health Insights */}
      <section aria-label="AI Health Insights">
        <Card title="AI Health Insights">
          <AIHealthInsights animals={animals} />
        </Card>
      </section>

      {/* Section B: Animal Profiles */}
      <section aria-label="Animal Profiles">
        <Card title="Animal Profiles">
          <AnimalTable animals={animals} onRefetch={loadData} />
        </Card>
      </section>

      {/* Section D: Financial Forecast */}
      <section aria-label="Financial Performance">
        <Card title="Financial Performance">
          <FinancialForecast data={financials} />
        </Card>
      </section>

      {/* Section E + F: Interventions + Climate side by side on lg */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <section aria-label="Interventions Log">
          <Card title="Interventions Log">
            {interventions ? (
              <InterventionsLog interventions={interventions} />
            ) : (
              <p className="text-sm text-gray-500">No interventions data.</p>
            )}
          </Card>
        </section>

        <section aria-label="Climate and Feed Planning">
          <Card title="Climate & Feed Planning">
            {climate ? (
              <ClimateSection climate={climate} />
            ) : (
              <p className="text-sm text-gray-500">No climate data.</p>
            )}
          </Card>
        </section>
      </div>
    </div>
  );
}
