import React, { useState, useEffect, useCallback, useId } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  Area, AreaChart, ReferenceLine,
} from 'recharts';
import { RefreshCw, ChevronDown, ChevronUp, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import Card from './shared/Card.jsx';
import MetricCard from './shared/MetricCard.jsx';
import AlertBox from './shared/AlertBox.jsx';
import StatusBadge from './shared/StatusBadge.jsx';
import Spinner from './shared/Spinner.jsx';
import { getSupplyForecast, getBenchmarking, getCostAnalysis } from '../api/endpoints.js';
import { useAuth } from '../context/AuthContext.jsx';

function SectionError({ onRetry }) {
  return (
    <div className="flex flex-col items-center py-8 gap-2">
      <p className="text-sm text-gray-500">Data unavailable</p>
      <button onClick={onRetry} className="flex items-center gap-1 text-xs text-blue-600 hover:underline">
        <RefreshCw size={12} /> Retry
      </button>
    </div>
  );
}

// Section A: Supply Forecast
function SupplyForecast({ forecastData }) {
  const gradientId = useId();

  if (!forecastData || forecastData.length === 0) return null;

  const first = forecastData[0]?.forecast || 0;
  const last = forecastData[forecastData.length - 1]?.forecast || 0;
  const changePct = first > 0 ? (((last - first) / first) * 100).toFixed(1) : 0;
  const insight = changePct > 0
    ? `Forecast trending up ${changePct}% over the 30-day window.`
    : changePct < 0
    ? `Forecast trending down ${Math.abs(changePct)}% — consider supplier outreach.`
    : 'Forecast stable over the 30-day window.';

  const CustomTooltip = ({ active, payload, label }) => {
    if (!active || !payload?.length) return null;
    return (
      <div className="bg-white border border-gray-200 rounded p-2 text-xs shadow-sm">
        <p className="font-semibold text-gray-700 mb-1">Day {label}</p>
        {payload.map((p) => (
          <p key={p.dataKey} style={{ color: p.color }}>{p.name}: {(p.value || 0).toLocaleString()} L</p>
        ))}
      </div>
    );
  };

  return (
    <div>
      <p className="text-xs text-blue-700 bg-blue-50 border border-blue-100 rounded px-3 py-1.5 mb-3 font-medium">{insight}</p>
      <ResponsiveContainer width="100%" height={240}>
        <AreaChart data={forecastData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id={`${gradientId}-ci`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#BFDBFE" stopOpacity={0.5} />
              <stop offset="95%" stopColor="#BFDBFE" stopOpacity={0.05} />
            </linearGradient>
            <linearGradient id={`${gradientId}-hist`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#E5E7EB" stopOpacity={0.5} />
              <stop offset="95%" stopColor="#E5E7EB" stopOpacity={0.1} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#F3F4F6" />
          <XAxis dataKey="day" tick={{ fontSize: 10, fill: '#9CA3AF' }} tickFormatter={(v) => `D${v}`} interval={4} />
          <YAxis tick={{ fontSize: 10, fill: '#9CA3AF' }} tickFormatter={(v) => `${(v / 1000).toFixed(1)}k`} />
          <Tooltip content={<CustomTooltip />} />
          <Area type="monotone" dataKey="upper" stackId="ci" stroke="none" fill={`url(#${gradientId}-ci)`} name="Upper bound" />
          <Area type="monotone" dataKey="lower" stackId="ci" stroke="none" fill="white" name="Lower bound" />
          <Area type="monotone" dataKey="historical" stroke="#9CA3AF" strokeWidth={1.5} fill={`url(#${gradientId}-hist)`} strokeDasharray="4 2" name="Historical" dot={false} connectNulls={false} />
          <Line type="monotone" dataKey="forecast" stroke="#2563EB" strokeWidth={2} dot={false} name="Forecast" />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

// Section B: Supply Sources Table
function SupplySourcesTable({ suppliers }) {
  const [expandedRow, setExpandedRow] = useState(null);

  if (!suppliers || suppliers.length === 0) return <p className="text-sm text-gray-500">No supplier data.</p>;

  return (
    <div className="overflow-x-auto table-scroll">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-200">
            <th className="text-left py-2 px-2 text-xs font-semibold text-gray-600">Supplier</th>
            <th className="text-left py-2 px-2 text-xs font-semibold text-gray-600">Location</th>
            <th className="text-right py-2 px-2 text-xs font-semibold text-gray-600">Daily Avg (L)</th>
            <th className="text-left py-2 px-2 text-xs font-semibold text-gray-600">Health</th>
            <th className="text-right py-2 px-2 text-xs font-semibold text-gray-600">Trend</th>
          </tr>
        </thead>
        <tbody>
          {suppliers.map((s) => (
            <React.Fragment key={s.id}>
              <tr
                className="border-b border-gray-100 hover:bg-gray-50 cursor-pointer"
                onClick={() => setExpandedRow(expandedRow === s.id ? null : s.id)}
              >
                <td className="py-2 px-2 font-medium text-gray-900">{s.name}</td>
                <td className="py-2 px-2 text-gray-500">{s.location}</td>
                <td className="py-2 px-2 text-right tabular-nums text-gray-700">{(s.daily_avg || 0).toLocaleString()}</td>
                <td className="py-2 px-2">
                  <span className={`inline-flex items-center gap-1 text-xs font-medium ${s.health_status === 'healthy' ? 'text-green-700' : 'text-amber-700'}`}>
                    <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${s.health_status === 'healthy' ? 'bg-green-500' : 'bg-amber-500'}`} />
                    {s.health_status === 'healthy' ? 'Healthy' : 'At Risk'}
                  </span>
                </td>
                <td className="py-2 px-2 text-right">
                  <span className={`text-xs font-medium ${s.trend > 0 ? 'text-green-600' : s.trend < 0 ? 'text-red-600' : 'text-gray-500'}`}>
                    {s.trend > 0 ? '↑' : s.trend < 0 ? '↓' : '→'} {s.trend > 0 ? '+' : ''}{s.trend}%
                  </span>
                </td>
              </tr>
              {expandedRow === s.id && s.quality_grade && (
                <tr className="bg-gray-50">
                  <td colSpan={5} className="px-4 py-3">
                    <p className="text-xs font-semibold text-gray-700 mb-2">Quality Grade Distribution</p>
                    <div className="flex items-center gap-2">
                      {Object.entries(s.quality_grade).map(([grade, pct]) => (
                        <div key={grade} className="flex-1">
                          <div className="flex justify-between text-xs text-gray-600 mb-1">
                            <span>Grade {grade}</span>
                            <span>{pct}%</span>
                          </div>
                          <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                            <div
                              className={`h-full rounded-full ${grade === 'A' ? 'bg-green-500' : grade === 'B' ? 'bg-blue-400' : 'bg-amber-400'}`}
                              style={{ width: `${pct}%` }}
                            />
                          </div>
                        </div>
                      ))}
                    </div>
                  </td>
                </tr>
              )}
            </React.Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// Section C: Benchmarking
function BenchmarkingSection({ data }) {
  if (!data) return null;

  const rows = [
    { label: 'Daily Volume (L)', your: data.your_metrics?.daily_volume, peer: data.peer_median?.daily_volume, best: data.best_in_class?.daily_volume, higherIsBetter: true },
    { label: 'Avg Quality Grade', your: data.your_metrics?.avg_quality_grade, peer: data.peer_median?.avg_quality_grade, best: data.best_in_class?.avg_quality_grade, higherIsBetter: true },
    { label: 'Price Paid (NGN/L)', your: data.your_metrics?.price_paid, peer: data.peer_median?.price_paid, best: data.best_in_class?.price_paid, higherIsBetter: false },
  ];

  function getColor(your, peer, higherIsBetter) {
    if (typeof your !== 'number' || typeof peer !== 'number') return 'text-gray-700';
    const better = higherIsBetter ? your >= peer : your <= peer;
    return better ? 'text-green-700 font-semibold' : 'text-red-700 font-semibold';
  }

  return (
    <div>
      <div className="grid grid-cols-3 gap-0 mb-2">
        {['Your Metrics', 'Peer Median', 'Best in Class'].map((h) => (
          <div key={h} className="text-center text-xs font-semibold text-gray-600 py-1.5 border-b border-gray-200">{h}</div>
        ))}
      </div>
      {rows.map((row) => (
        <div key={row.label} className="grid grid-cols-3 gap-0 border-b border-gray-100 last:border-0">
          <div className="col-span-3 text-xs text-gray-500 pt-2 pb-0.5 px-1">{row.label}</div>
          <div className={`text-sm py-1 px-1 text-center ${getColor(row.your, row.peer, row.higherIsBetter)}`}>
            {typeof row.your === 'number' ? row.your.toLocaleString() : row.your}
          </div>
          <div className="text-sm py-1 px-1 text-center text-gray-700">
            {typeof row.peer === 'number' ? row.peer.toLocaleString() : row.peer}
          </div>
          <div className="text-sm py-1 px-1 text-center text-blue-700 font-medium">
            {typeof row.best === 'number' ? row.best.toLocaleString() : row.best}
          </div>
        </div>
      ))}
      {data.interpretation && (
        <p className="mt-3 text-xs text-gray-600 bg-gray-50 rounded p-2 border border-gray-100">{data.interpretation}</p>
      )}
    </div>
  );
}

// Section D: Cost Analysis Chart
function CostAnalysisChart({ data }) {
  const gradientId = useId();
  if (!data || !data.price_trend) return null;

  const CustomTooltip = ({ active, payload, label }) => {
    if (!active || !payload?.length) return null;
    return (
      <div className="bg-white border border-gray-200 rounded p-2 text-xs shadow-sm">
        <p className="font-semibold text-gray-700 mb-1">{label}</p>
        {payload.map((p) => (
          <p key={p.dataKey} style={{ color: p.color }}>
            {p.name}: ₦{(p.value || 0).toLocaleString()}/L
          </p>
        ))}
      </div>
    );
  };

  return (
    <ResponsiveContainer width="100%" height={220}>
      <AreaChart data={data.price_trend} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id={`${gradientId}-spread`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#BFDBFE" stopOpacity={0.5} />
            <stop offset="95%" stopColor="#BFDBFE" stopOpacity={0.05} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#F3F4F6" />
        <XAxis dataKey="month" tick={{ fontSize: 10, fill: '#9CA3AF' }} />
        <YAxis tick={{ fontSize: 10, fill: '#9CA3AF' }} tickFormatter={(v) => `₦${v}`} />
        <Tooltip content={<CustomTooltip />} />
        <Area type="monotone" dataKey="import_parity" stroke="#93C5FD" strokeWidth={1.5} fill={`url(#${gradientId}-spread)`} name="Import parity" dot={false} />
        <Line type="monotone" dataKey="your_price" stroke="#2563EB" strokeWidth={2} dot={false} name="Your avg price" />
      </AreaChart>
    </ResponsiveContainer>
  );
}

// Main ProcessorDashboard
export default function ProcessorDashboard() {
  const { user } = useAuth();
  const processorId = user?.org_id || 'proc_001';

  const [supplyData, setSupplyData] = useState(null);
  const [supplyLoading, setSupplyLoading] = useState(true);
  const [supplyError, setSupplyError] = useState(false);

  const [benchmarkData, setBenchmarkData] = useState(null);
  const [benchmarkLoading, setBenchmarkLoading] = useState(true);
  const [benchmarkError, setBenchmarkError] = useState(false);

  const [costData, setCostData] = useState(null);
  const [costLoading, setCostLoading] = useState(true);
  const [costError, setCostError] = useState(false);

  async function loadSupply() {
    setSupplyLoading(true); setSupplyError(false);
    try {
      const res = await getSupplyForecast(processorId);
      setSupplyData(res.data);
    } catch { setSupplyError(true); }
    finally { setSupplyLoading(false); }
  }

  async function loadBenchmark() {
    setBenchmarkLoading(true); setBenchmarkError(false);
    try {
      const res = await getBenchmarking(processorId);
      setBenchmarkData(res.data);
    } catch { setBenchmarkError(true); }
    finally { setBenchmarkLoading(false); }
  }

  async function loadCost() {
    setCostLoading(true); setCostError(false);
    try {
      const res = await getCostAnalysis(processorId);
      setCostData(res.data);
    } catch { setCostError(true); }
    finally { setCostLoading(false); }
  }

  useEffect(() => {
    loadSupply();
    loadBenchmark();
    loadCost();
  }, [processorId]);

  const suppliers = supplyData?.suppliers || [];
  const forecast = supplyData?.forecast || [];
  const risks = costData?.risks || [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-bold text-gray-900">Processor Intelligence Dashboard</h1>
        <p className="text-sm text-gray-500 mt-0.5">Supply forecast, benchmarking, and cost analysis</p>
      </div>

      {/* Section A: Supply Forecast */}
      <section aria-label="Supply Forecast">
        <Card title="30-Day Supply Forecast">
          {supplyLoading ? (
            <Spinner />
          ) : supplyError ? (
            <SectionError onRetry={loadSupply} />
          ) : (
            <SupplyForecast forecastData={forecast} />
          )}
        </Card>
      </section>

      {/* Section B: Supply Sources */}
      <section aria-label="Supply Sources">
        <Card title="Supply Sources">
          {supplyLoading ? (
            <Spinner />
          ) : supplyError ? (
            <SectionError onRetry={loadSupply} />
          ) : (
            <SupplySourcesTable suppliers={suppliers} />
          )}
        </Card>
      </section>

      {/* Section C & D: Benchmarking + Cost */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <section aria-label="Benchmarking">
          <Card title="Benchmarking">
            {benchmarkLoading ? (
              <Spinner />
            ) : benchmarkError ? (
              <SectionError onRetry={loadBenchmark} />
            ) : (
              <BenchmarkingSection data={benchmarkData} />
            )}
          </Card>
        </section>

        <section aria-label="Price vs Import Parity">
          <Card title="Price vs Import Parity (12 months)">
            {costLoading ? (
              <Spinner />
            ) : costError ? (
              <SectionError onRetry={loadCost} />
            ) : (
              <CostAnalysisChart data={costData} />
            )}
          </Card>
        </section>
      </div>

      {/* Section E: Supply Risk */}
      <section aria-label="Supply Risk Alerts">
        <Card title="Supply Risk Alerts">
          {costLoading ? (
            <Spinner />
          ) : costError ? (
            <SectionError onRetry={loadCost} />
          ) : risks.length === 0 ? (
            <p className="text-sm text-gray-500">No active risks detected.</p>
          ) : (
            <div className="space-y-3">
              {risks.map((r, i) => (
                <AlertBox
                  key={i}
                  level={r.level}
                  title={r.name}
                  message={`${r.description}${r.affected_suppliers?.length ? ` Affected: ${r.affected_suppliers.join(', ')}.` : ''}`}
                />
              ))}
            </div>
          )}
        </Card>
      </section>
    </div>
  );
}
