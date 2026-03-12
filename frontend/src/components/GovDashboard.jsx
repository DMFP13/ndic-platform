import React, { useState, useEffect, useCallback } from 'react';
import { MapContainer, TileLayer, CircleMarker, Popup, Rectangle } from 'react-leaflet';
import L from 'leaflet';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine,
} from 'recharts';
import {
  AlertTriangle, CheckCircle, RefreshCw, ChevronDown, ChevronUp,
  Activity, TrendingUp, Users, Droplets,
} from 'lucide-react';
import Card from './shared/Card.jsx';
import MetricCard from './shared/MetricCard.jsx';
import AlertBox from './shared/AlertBox.jsx';
import StatusBadge from './shared/StatusBadge.jsx';
import Spinner from './shared/Spinner.jsx';
import {
  getDiseaseSurveillance, getProductionTrends, getPolicyAnalytics, getEarlyWarnings, getClimateRiskMap,
} from '../api/endpoints.js';

// Leaflet icon fix
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
});

const OUTBREAK_COLORS = {
  confirmed: '#EF4444',
  suspected: '#F59E0B',
  resolved: '#6B7280',
};

const RISK_COLORS = {
  high: { color: '#EF4444', fillOpacity: 0.25 },
  medium: { color: '#F59E0B', fillOpacity: 0.2 },
  low: { color: '#22C55E', fillOpacity: 0.18 },
};

function outbreakRadius(animals) {
  const n = animals || 0;
  return Math.min(24, Math.max(8, 8 + (n / 150) * 16));
}

function SectionError({ onRetry }) {
  return (
    <div className="flex flex-col items-center justify-center py-8 gap-3">
      <p className="text-sm text-gray-500">Data unavailable</p>
      <button
        onClick={onRetry}
        className="flex items-center gap-1 text-xs text-blue-600 hover:underline"
      >
        <RefreshCw size={12} /> Retry
      </button>
    </div>
  );
}

// Section A: Disease Surveillance Map
function DiseaseSurveillanceMap() {
  const [outbreaks, setOutbreaks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [timelineFilter, setTimelineFilter] = useState('30d');
  const [riskMode, setRiskMode] = useState('drought');
  const [climateRegions, setClimateRegions] = useState([]);
  const [viewMode, setViewMode] = useState('disease'); // 'disease' | 'climate'

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(false);
    try {
      const [dRes, cRes] = await Promise.all([
        getDiseaseSurveillance(timelineFilter),
        getClimateRiskMap(),
      ]);
      setOutbreaks(Array.isArray(dRes.data) ? dRes.data : []);
      setClimateRegions(Array.isArray(cRes.data) ? cRes.data : []);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, [timelineFilter]);

  useEffect(() => { fetchData(); }, [fetchData]);

  return (
    <Card
      title="Disease Surveillance & Climate Risk"
      action={
        <div className="flex items-center gap-2">
          <div className="flex rounded border border-gray-200 overflow-hidden">
            {['disease', 'climate'].map((m) => (
              <button
                key={m}
                onClick={() => setViewMode(m)}
                className={`px-2 py-1 text-xs font-medium ${viewMode === m ? 'bg-blue-600 text-white' : 'bg-white text-gray-600 hover:bg-gray-50'}`}
              >
                {m === 'disease' ? 'Disease' : 'Climate'}
              </button>
            ))}
          </div>
          {viewMode === 'disease' && (
            <div className="flex rounded border border-gray-200 overflow-hidden">
              {[['7d', '7 Days'], ['30d', '30 Days'], ['all', 'All Active']].map(([v, l]) => (
                <button
                  key={v}
                  onClick={() => setTimelineFilter(v)}
                  className={`px-2 py-1 text-xs font-medium ${timelineFilter === v ? 'bg-blue-600 text-white' : 'bg-white text-gray-600 hover:bg-gray-50'}`}
                >
                  {l}
                </button>
              ))}
            </div>
          )}
          {viewMode === 'climate' && (
            <div className="flex rounded border border-gray-200 overflow-hidden">
              {[['drought', 'Drought'], ['flood', 'Flood']].map(([v, l]) => (
                <button
                  key={v}
                  onClick={() => setRiskMode(v)}
                  className={`px-2 py-1 text-xs font-medium ${riskMode === v ? 'bg-blue-600 text-white' : 'bg-white text-gray-600 hover:bg-gray-50'}`}
                >
                  {l}
                </button>
              ))}
            </div>
          )}
        </div>
      }
    >
      {loading ? (
        <Spinner />
      ) : error ? (
        <SectionError onRetry={fetchData} />
      ) : (
        <div>
          <div style={{ height: 400 }} className="rounded-lg overflow-hidden border border-gray-200">
            <MapContainer center={[9.082, 8.675]} zoom={6} style={{ height: '100%', width: '100%' }} scrollWheelZoom={false}>
              <TileLayer
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />
              {viewMode === 'disease' && outbreaks.map((o) => (
                <CircleMarker
                  key={o.id}
                  center={[o.lat, o.lng]}
                  radius={outbreakRadius(o.animals_affected)}
                  pathOptions={{
                    color: OUTBREAK_COLORS[o.status] || '#6B7280',
                    fillColor: OUTBREAK_COLORS[o.status] || '#6B7280',
                    fillOpacity: 0.5,
                    weight: 2,
                  }}
                >
                  <Popup>
                    <div className="text-xs space-y-1">
                      <p className="font-semibold">{o.disease}</p>
                      <p>Location: {o.location}</p>
                      <p>Animals affected: {o.animals_affected}</p>
                      <p>Status: <span className={o.status === 'confirmed' ? 'text-red-600 font-medium' : o.status === 'suspected' ? 'text-amber-600 font-medium' : 'text-gray-500'}>{o.status}</span></p>
                      <p>Date: {o.date}</p>
                    </div>
                  </Popup>
                </CircleMarker>
              ))}
              {viewMode === 'climate' && climateRegions.map((r, i) => {
                const riskKey = riskMode === 'drought' ? r.droughtRisk : r.floodRisk;
                const style = RISK_COLORS[riskKey] || RISK_COLORS.low;
                return (
                  <Rectangle
                    key={i}
                    bounds={r.bounds}
                    pathOptions={{ color: style.color, fillColor: style.color, fillOpacity: style.fillOpacity, weight: 1 }}
                  >
                    <Popup>
                      <div className="text-xs">
                        <p className="font-semibold">{r.region}</p>
                        <p>Drought risk: <span className="font-medium">{r.droughtRisk}</span></p>
                        <p>Flood risk: <span className="font-medium">{r.floodRisk}</span></p>
                      </div>
                    </Popup>
                  </Rectangle>
                );
              })}
            </MapContainer>
          </div>

          {viewMode === 'disease' && (
            <div className="mt-3 flex items-center gap-4 text-xs text-gray-600">
              <span className="font-medium">Legend:</span>
              {Object.entries(OUTBREAK_COLORS).map(([k, c]) => (
                <span key={k} className="flex items-center gap-1">
                  <span className="inline-block w-3 h-3 rounded-full" style={{ backgroundColor: c }} />
                  <span className="capitalize">{k}</span>
                </span>
              ))}
              <span className="text-gray-400">(bubble size = animals affected)</span>
            </div>
          )}
          {viewMode === 'climate' && (
            <div className="mt-3 flex items-center gap-4 text-xs text-gray-600">
              <span className="font-medium">Legend:</span>
              {[['low', '#22C55E'], ['medium', '#F59E0B'], ['high', '#EF4444']].map(([k, c]) => (
                <span key={k} className="flex items-center gap-1">
                  <span className="inline-block w-3 h-3 rounded" style={{ backgroundColor: c, opacity: 0.7 }} />
                  <span className="capitalize">{k} {riskMode} risk</span>
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </Card>
  );
}

// Section B: National Herd Health Snapshot
function HerdHealthSnapshot({ data, loading, error, onRetry }) {
  if (loading) return <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4"><Spinner /></div>;
  if (error || !data) return <SectionError onRetry={onRetry} />;

  const metrics = [
    { label: 'Total Animals', value: (data.total_animals || 0).toLocaleString(), trend: data.total_trend, icon: Users, color: 'blue' },
    { label: 'Healthy', value: `${data.healthy_pct || 0}%`, trend: data.healthy_trend, icon: CheckCircle, color: 'green' },
    { label: 'At Risk', value: `${data.at_risk_pct || 0}%`, trend: data.at_risk_trend, icon: AlertTriangle, color: 'amber' },
    { label: 'Under Treatment', value: `${data.treated_pct || 0}%`, trend: data.treated_trend, icon: Activity, color: 'red' },
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      {metrics.map((m) => (
        <MetricCard key={m.label} {...m} />
      ))}
    </div>
  );
}

// Section C: Regional Production Trends
function ProductionTrendsChart({ data, loading, error, onRetry }) {
  if (loading) return <Spinner />;
  if (error || !data) return <SectionError onRetry={onRetry} />;

  const nationalAvg = data.length > 0 ? Math.round(data.reduce((s, d) => s + d.liters, 0) / data.length) : 0;

  const CustomTooltip = ({ active, payload, label }) => {
    if (!active || !payload?.length) return null;
    return (
      <div className="bg-white border border-gray-200 rounded p-2 text-xs shadow-sm">
        <p className="font-semibold text-gray-900">{label}</p>
        <p className="text-blue-700">{(payload[0]?.value || 0).toLocaleString()} L/day</p>
      </div>
    );
  };

  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={data} layout="vertical" margin={{ left: 8, right: 24, top: 4, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f0f0f0" />
        <XAxis type="number" tick={{ fontSize: 11, fill: '#6B7280' }} tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} />
        <YAxis dataKey="state" type="category" tick={{ fontSize: 11, fill: '#374151' }} width={56} />
        <Tooltip content={<CustomTooltip />} />
        <ReferenceLine x={nationalAvg} stroke="#93C5FD" strokeDasharray="4 2" label={{ value: 'Nat. avg', position: 'insideTopRight', fontSize: 10, fill: '#93C5FD' }} />
        <Bar dataKey="liters" fill="#2563EB" radius={[0, 3, 3, 0]} maxBarSize={22} />
      </BarChart>
    </ResponsiveContainer>
  );
}

// Section E: Early Warning Alerts
function EarlyWarnings({ data, loading, error, onRetry }) {
  const [expanded, setExpanded] = useState(null);

  if (loading) return <Spinner />;
  if (error || !data) return <SectionError onRetry={onRetry} />;

  const sorted = [...data].sort((a, b) => {
    const order = { critical: 0, warning: 1, info: 2 };
    return (order[a.severity] ?? 3) - (order[b.severity] ?? 3);
  });

  return (
    <div className="overflow-x-auto table-scroll">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-200">
            <th className="text-left py-2 px-2 text-xs font-semibold text-gray-600 w-8"></th>
            <th className="text-left py-2 px-2 text-xs font-semibold text-gray-600">Alert</th>
            <th className="text-left py-2 px-2 text-xs font-semibold text-gray-600">Location</th>
            <th className="text-left py-2 px-2 text-xs font-semibold text-gray-600">Date</th>
            <th className="text-left py-2 px-2 text-xs font-semibold text-gray-600">Status</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((w) => (
            <React.Fragment key={w.id}>
              <tr
                className="border-b border-gray-100 hover:bg-gray-50 cursor-pointer"
                onClick={() => setExpanded(expanded === w.id ? null : w.id)}
              >
                <td className="py-2 px-2">
                  {w.status === 'resolved' ? (
                    <CheckCircle size={14} className="text-gray-400" />
                  ) : (
                    <AlertTriangle size={14} className={w.severity === 'critical' ? 'text-red-500' : w.severity === 'warning' ? 'text-amber-500' : 'text-blue-400'} />
                  )}
                </td>
                <td className="py-2 px-2">
                  <span className="font-medium text-gray-900">{w.title}</span>
                </td>
                <td className="py-2 px-2 text-gray-600">{w.location}</td>
                <td className="py-2 px-2 text-gray-500 text-xs">{w.date}</td>
                <td className="py-2 px-2">
                  <StatusBadge status={w.status || w.severity} />
                </td>
              </tr>
              {expanded === w.id && (
                <tr className="bg-gray-50">
                  <td colSpan={5} className="px-4 py-3">
                    <p className="text-xs text-gray-700 mb-1">{w.description}</p>
                    <p className="text-xs font-medium text-blue-700">Recommended action: {w.action}</p>
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

// Section F: Policy Analytics
function PolicyAnalyticsSection({ data, loading, error, onRetry }) {
  if (loading) return <Spinner />;
  if (error || !data) return <SectionError onRetry={onRetry} />;

  const metrics = [
    { label: 'Herd Growth YoY', value: `${data.herd_growth_yoy || 0}%`, trend: data.herd_growth_trend, icon: TrendingUp, color: 'green' },
    { label: 'Productivity (L/head/day)', value: data.productivity_l_per_head || 0, trend: data.productivity_trend, icon: Droplets, color: 'blue' },
    { label: 'Mortality Rate', value: `${data.mortality_rate || 0}%`, trend: data.mortality_trend, icon: Activity, color: 'red' },
    { label: 'Zebu % of Herd', value: `${data.zebu_percent || 0}%`, trend: data.zebu_trend, icon: Users, color: 'amber' },
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
      {metrics.map((m) => (
        <MetricCard key={m.label} {...m} />
      ))}
    </div>
  );
}

// Main GovDashboard
export default function GovDashboard() {
  const [policyData, setPolicyData] = useState(null);
  const [policyLoading, setPolicyLoading] = useState(true);
  const [policyError, setPolicyError] = useState(false);

  const [productionData, setProductionData] = useState(null);
  const [productionLoading, setProductionLoading] = useState(true);
  const [productionError, setProductionError] = useState(false);

  const [warningsData, setWarningsData] = useState(null);
  const [warningsLoading, setWarningsLoading] = useState(true);
  const [warningsError, setWarningsError] = useState(false);

  async function loadPolicy() {
    setPolicyLoading(true); setPolicyError(false);
    try {
      const res = await getPolicyAnalytics();
      setPolicyData(res.data);
    } catch { setPolicyError(true); }
    finally { setPolicyLoading(false); }
  }

  async function loadProduction() {
    setProductionLoading(true); setProductionError(false);
    try {
      const res = await getProductionTrends();
      setProductionData(Array.isArray(res.data) ? res.data : []);
    } catch { setProductionError(true); }
    finally { setProductionLoading(false); }
  }

  async function loadWarnings() {
    setWarningsLoading(true); setWarningsError(false);
    try {
      const res = await getEarlyWarnings();
      setWarningsData(Array.isArray(res.data) ? res.data : []);
    } catch { setWarningsError(true); }
    finally { setWarningsLoading(false); }
  }

  useEffect(() => {
    loadPolicy();
    loadProduction();
    loadWarnings();
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-bold text-gray-900">Government Intelligence Dashboard</h1>
        <p className="text-sm text-gray-500 mt-0.5">National herd health, disease surveillance, and policy analytics — FMARD</p>
      </div>

      {/* Section B: Herd Snapshot */}
      <section aria-label="National Herd Health Snapshot">
        <h2 className="text-sm font-semibold text-gray-700 mb-3">National Herd Health Snapshot</h2>
        <HerdHealthSnapshot
          data={policyData}
          loading={policyLoading}
          error={policyError}
          onRetry={loadPolicy}
        />
      </section>

      {/* Section A: Disease Surveillance Map */}
      <section aria-label="Disease Surveillance Map">
        <DiseaseSurveillanceMap />
      </section>

      {/* Section C: Regional Production Trends */}
      <section aria-label="Regional Production Trends">
        <Card title="Regional Production Trends" className="">
          {productionLoading ? (
            <Spinner />
          ) : productionError ? (
            <SectionError onRetry={loadProduction} />
          ) : (
            <ProductionTrendsChart data={productionData} loading={false} error={false} onRetry={loadProduction} />
          )}
        </Card>
      </section>

      {/* Section E: Early Warning Alerts */}
      <section aria-label="Early Warning Alerts">
        <Card title="Early Warning Alerts">
          <EarlyWarnings
            data={warningsData}
            loading={warningsLoading}
            error={warningsError}
            onRetry={loadWarnings}
          />
        </Card>
      </section>

      {/* Section F: Policy Analytics */}
      <section aria-label="Policy Analytics">
        <Card title="Policy Analytics">
          <PolicyAnalyticsSection
            data={policyData}
            loading={policyLoading}
            error={policyError}
            onRetry={loadPolicy}
          />
        </Card>
      </section>
    </div>
  );
}
