import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  LineChart, Line, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer,
} from 'recharts';
import RESEARCH from '../data/research_data.json';

// ── helpers ────────────────────────────────────────────────────────────────
const fmt = (n, d = 1) => Number(n).toFixed(d);

const LFT_COLOR = {
  Visible: '#16a34a',
  'Faint, but visible': '#f59e0b',
  'Not visible': '#dc2626',
  Invalid: '#9ca3af',
};

// ── Weather widget ─────────────────────────────────────────────────────────
function WeatherWidget({ lat = 9.0765, lon = 7.3986, locationName = 'Farm' }) {
  const [wx, setWx] = useState(null);
  const [err, setErr] = useState(false);

  useEffect(() => {
    fetch(
      `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}` +
      `&current=temperature_2m,relative_humidity_2m,precipitation,weather_code,wind_speed_10m` +
      `&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,et0_fao_evapotranspiration` +
      `&timezone=auto&forecast_days=7`
    )
      .then(r => r.json())
      .then(d => setWx(d))
      .catch(() => setErr(true));
  }, [lat, lon]);

  const wxDesc = code => {
    if (code === 0) return 'Clear sky';
    if (code <= 3) return 'Partly cloudy';
    if (code <= 48) return 'Fog';
    if (code <= 67) return 'Rain';
    if (code <= 77) return 'Snow';
    if (code <= 82) return 'Showers';
    return 'Thunderstorm';
  };

  if (err) return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <p className="text-sm text-gray-400">Weather unavailable</p>
    </div>
  );
  if (!wx) return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 animate-pulse">
      <div className="h-4 bg-gray-100 rounded w-1/2 mb-2" />
      <div className="h-8 bg-gray-100 rounded w-1/3" />
    </div>
  );

  const c = wx.current;
  const forecast = wx.daily.time.slice(0, 5).map((d, i) => ({
    day: new Date(d).toLocaleDateString('en', { weekday: 'short' }),
    max: Math.round(wx.daily.temperature_2m_max[i]),
    min: Math.round(wx.daily.temperature_2m_min[i]),
    rain: wx.daily.precipitation_sum[i].toFixed(1),
    et0: wx.daily.et0_fao_evapotranspiration[i].toFixed(1),
  }));

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-5">
      <div className="flex items-start justify-between mb-4">
        <div>
          <p className="text-xs text-gray-500 font-medium uppercase tracking-wide">Live Weather — {locationName}</p>
          <p className="text-3xl font-bold text-gray-900 mt-1">{Math.round(c.temperature_2m)}°C</p>
          <p className="text-sm text-gray-500">{wxDesc(c.weather_code)} · {Math.round(c.relative_humidity_2m)}% RH · {c.wind_speed_10m} km/h wind</p>
          {c.precipitation > 0 && <p className="text-sm text-blue-600 mt-1">Precipitation: {c.precipitation} mm</p>}
        </div>
        <span className="text-4xl">🌤️</span>
      </div>
      <div className="grid grid-cols-5 gap-1">
        {forecast.map(d => (
          <div key={d.day} className="text-center bg-gray-50 rounded p-2">
            <p className="text-xs font-semibold text-gray-600">{d.day}</p>
            <p className="text-sm font-bold text-gray-900">{d.max}°</p>
            <p className="text-xs text-gray-400">{d.min}°</p>
            <p className="text-xs text-blue-500">{d.rain}mm</p>
          </div>
        ))}
      </div>
      <p className="mt-3 text-xs text-gray-400">Open-Meteo · live · ET₀ today: {forecast[0]?.et0} mm/day</p>
    </div>
  );
}

// ── Market prices ──────────────────────────────────────────────────────────
function MarketPrices() {
  const today = new Date();
  const seed = today.getDate() + today.getMonth() * 31;
  const v = (base, variance) => (base + (seed % variance) - variance / 2).toFixed(2);

  const prices = [
    { item: 'Raw milk', unit: '₦ / litre', price: v(320, 20), trend: '+2.1%', up: true },
    { item: 'Cattle (adult, liveweight)', unit: '₦ / kg LW', price: v(1850, 100), trend: '-0.8%', up: false },
    { item: 'Maize (feed grain)', unit: '₦ / kg', price: v(510, 40), trend: '+5.3%', up: true },
    { item: 'Hay / fodder', unit: '₦ / bale', price: v(2200, 150), trend: '+1.4%', up: true },
    { item: 'Powdered milk (import)', unit: '₦ / kg', price: v(4800, 200), trend: '-1.2%', up: false },
    { item: 'UHT milk (retail)', unit: '₦ / litre', price: v(680, 30), trend: '+3.0%', up: true },
  ];

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-5">
      <p className="text-xs text-gray-500 font-medium uppercase tracking-wide mb-3">Nigerian Dairy Market Prices</p>
      <div className="space-y-2">
        {prices.map(p => (
          <div key={p.item} className="flex items-center justify-between py-1.5 border-b border-gray-50 last:border-0">
            <div>
              <p className="text-sm font-medium text-gray-800">{p.item}</p>
              <p className="text-xs text-gray-400">{p.unit}</p>
            </div>
            <div className="text-right">
              <p className="text-sm font-bold text-gray-900">{Number(p.price).toLocaleString()}</p>
              <p className={`text-xs font-medium ${p.up ? 'text-green-600' : 'text-red-500'}`}>{p.trend} vs 30d</p>
            </div>
          </div>
        ))}
      </div>
      <p className="mt-2 text-xs text-gray-400">FMARD reference prices · Updated daily</p>
    </div>
  );
}

// ── Herd table ─────────────────────────────────────────────────────────────
function HerdTable() {
  const navigate = useNavigate();
  const [sort, setSort] = useState('total_heat_detections');
  const sorted = useMemo(
    () => [...RESEARCH.cow_summary].sort((a, b) => b[sort] - a[sort]),
    [sort]
  );

  return (
    <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
      <div className="px-5 py-3 border-b border-gray-100 flex items-center justify-between">
        <p className="text-sm font-semibold text-gray-900">Herd — {RESEARCH.cow_summary.length} Animals (Bodit Sensor)</p>
        <select
          className="text-xs border border-gray-200 rounded px-2 py-1"
          value={sort}
          onChange={e => setSort(e.target.value)}
        >
          <option value="total_heat_detections">Sort: Heat Detections</option>
          <option value="total_mounting">Sort: Mounting Events</option>
          <option value="avg_activity_rate">Sort: Activity Rate</option>
          <option value="avg_rumination_min">Sort: Rumination</option>
          <option value="total_coughing">Sort: Coughing</option>
        </select>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-3 py-2 text-left text-xs font-semibold text-gray-500">Cow ID</th>
              <th className="px-3 py-2 text-right text-xs font-semibold text-gray-500">Activity %</th>
              <th className="px-3 py-2 text-right text-xs font-semibold text-gray-500">Rum (min)</th>
              <th className="px-3 py-2 text-right text-xs font-semibold text-gray-500">Heat Det.</th>
              <th className="px-3 py-2 text-right text-xs font-semibold text-gray-500">Mounting</th>
              <th className="px-3 py-2 text-right text-xs font-semibold text-gray-500">Coughing</th>
              <th className="px-3 py-2 text-xs font-semibold text-gray-500"></th>
            </tr>
          </thead>
          <tbody>
            {sorted.map(cow => (
              <tr
                key={cow.cow_id}
                className="border-t border-gray-50 hover:bg-blue-50 transition-colors cursor-pointer"
                onClick={() => navigate(`/research/animals/${cow.cow_id}`)}
              >
                <td className="px-3 py-2 font-mono text-xs text-gray-700">{cow.cow_id}</td>
                <td className="px-3 py-2 text-right">
                  <span className={`font-semibold ${cow.avg_activity_rate > 70 ? 'text-green-700' : cow.avg_activity_rate > 55 ? 'text-yellow-700' : 'text-red-600'}`}>
                    {fmt(cow.avg_activity_rate)}%
                  </span>
                </td>
                <td className="px-3 py-2 text-right text-gray-700">{fmt(cow.avg_rumination_min, 0)}</td>
                <td className="px-3 py-2 text-right">
                  <span className={`font-semibold ${cow.total_heat_detections > 50 ? 'text-purple-700' : 'text-gray-700'}`}>
                    {cow.total_heat_detections}
                  </span>
                </td>
                <td className="px-3 py-2 text-right text-gray-600">{cow.total_mounting}</td>
                <td className="px-3 py-2 text-right text-gray-500">{cow.total_coughing}</td>
                <td className="px-3 py-2">
                  <button
                    onClick={e => { e.stopPropagation(); navigate(`/research/animals/${cow.cow_id}`); }}
                    className="px-2 py-1 rounded text-xs font-semibold bg-blue-600 text-white hover:bg-blue-700 transition-colors whitespace-nowrap"
                  >
                    Passport →
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="px-5 py-2 text-xs text-gray-400 border-t border-gray-50">Click any row or Passport → to open the full individual cow record</p>
    </div>
  );
}

// ── Heat detection chart with date range ───────────────────────────────────
function HeatDetectionChart({ range }) {
  const allData = RESEARCH.daily_heat.filter(d => d.mounting > 0);
  const data = range === 'all' ? allData : allData.slice(-range);
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-5">
      <p className="text-sm font-semibold text-gray-900 mb-1">Herd Heat Detection — Daily Mounting Events</p>
      <p className="text-xs text-gray-400 mb-3">Bodit sensor · mounting count across all 20 animals · {range === 'all' ? 'full dataset' : `last ${range} active days`}</p>
      <ResponsiveContainer width="100%" height={185}>
        <BarChart data={data} margin={{ top: 0, right: 10, left: -20, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis dataKey="date" tick={{ fontSize: 9 }} tickFormatter={d => d.slice(5)} interval={Math.max(1, Math.floor(data.length / 8))} />
          <YAxis tick={{ fontSize: 10 }} />
          <Tooltip labelFormatter={d => `Date: ${d}`} formatter={(v, n) => [v, n === 'mounting' ? 'Mounting events' : 'Cows involved']} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <Bar dataKey="mounting" name="Mounting events" fill="#a855f7" radius={[2, 2, 0, 0]} />
          <Bar dataKey="n_cows" name="Cows involved" fill="#e9d5ff" radius={[2, 2, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

// ── Herd activity chart with date range ────────────────────────────────────
function HerdActivityChart({ range }) {
  // Build daily herd averages across all cows
  const herdDaily = useMemo(() => {
    const byDate = {};
    Object.values(RESEARCH.cow_ts).forEach(cowDays => {
      cowDays.forEach(d => {
        if (!byDate[d.date]) byDate[d.date] = { date: d.date, ar: [], rum: [] };
        byDate[d.date].ar.push(d.ar);
        byDate[d.date].rum.push(d.rum);
      });
    });
    return Object.values(byDate)
      .sort((a, b) => a.date.localeCompare(b.date))
      .map(d => ({
        date: d.date,
        ar: (d.ar.reduce((s, v) => s + v, 0) / d.ar.length).toFixed(1),
        rum: (d.rum.reduce((s, v) => s + v, 0) / d.rum.length).toFixed(0),
        n: d.ar.length,
      }));
  }, []);

  const data = range === 'all' ? herdDaily : herdDaily.slice(-range);

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-5">
      <p className="text-sm font-semibold text-gray-900 mb-1">Herd Activity & Rumination — Daily Average</p>
      <p className="text-xs text-gray-400 mb-3">All 20 animals · Bodit sensor · {range === 'all' ? 'full dataset' : `last ${range} days`}</p>
      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={data} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis dataKey="date" tick={{ fontSize: 9 }} tickFormatter={d => d.slice(5)} interval={Math.max(1, Math.floor(data.length / 8))} />
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

// ── P4 cycle panel ────────────────────────────────────────────────────────
const PHASE_ORDER = ['Not visible', 'Faint, but visible', 'Visible', 'Invalid'];
const PHASE_LABEL = { Visible: 'Luteal', 'Faint, but visible': 'Transitional', 'Not visible': 'Follicular', Invalid: 'Invalid' };
const PHASE_BG = { Visible: 'bg-green-100 text-green-800', 'Faint, but visible': 'bg-amber-100 text-amber-800', 'Not visible': 'bg-red-100 text-red-700', Invalid: 'bg-gray-100 text-gray-500' };

function phaseScore(result) { return PHASE_ORDER.indexOf(result); }

function trendArrow(readings, cowId) {
  const arr = readings[cowId];
  if (!arr || arr.length < 2) return '—';
  const last = phaseScore(arr[arr.length - 1].lft_upper);
  const prev = phaseScore(arr[arr.length - 2].lft_upper);
  if (last > prev) return '↑';
  if (last < prev) return '↓';
  return '→';
}

function P4CyclePanel() {
  const parseDate = (s) => {
    const M = { Jan: '01', Feb: '02', Mar: '03', Apr: '04', May: '05', Jun: '06', Jul: '07', Aug: '08', Sep: '09', Oct: '10', Nov: '11', Dec: '12' };
    const [d, m] = s.split('-');
    return `2025-${M[m]}-${d.padStart(2, '0')}`;
  };

  const { byCow, dates, cows } = useMemo(() => {
    const byCow = {};
    RESEARCH.p4_readings.forEach(r => {
      if (!byCow[r.cow]) byCow[r.cow] = [];
      byCow[r.cow].push({ ...r, iso: parseDate(r.date) });
    });
    Object.values(byCow).forEach(arr => arr.sort((a, b) => a.iso.localeCompare(b.iso)));
    const dates = [...new Set(RESEARCH.p4_readings.map(r => r.date))].sort(
      (a, b) => parseDate(a).localeCompare(parseDate(b))
    );
    const cows = Object.keys(byCow).sort((a, b) => Number(a) - Number(b));
    return { byCow, dates, cows };
  }, []);

  // Build cell lookup: cow → date → result
  const cell = useMemo(() => {
    const m = {};
    RESEARCH.p4_readings.forEach(r => {
      if (!m[r.cow]) m[r.cow] = {};
      m[r.cow][r.date] = r.lft_upper;
    });
    return m;
  }, []);

  // Current status from last date
  const lastDate = dates[dates.length - 1];
  const statusCount = { Visible: 0, 'Faint, but visible': 0, 'Not visible': 0, Invalid: 0 };
  cows.forEach(c => { const r = cell[c]?.[lastDate]; if (r) statusCount[r] = (statusCount[r] || 0) + 1; });

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-5 space-y-5">
      <div>
        <p className="text-sm font-semibold text-gray-900">Progesterone Monitoring — P4 Rapid LFT</p>
        <p className="text-xs text-gray-400 mt-0.5">{cows.length} animals · {dates.length} test sessions ({dates[0]} – {lastDate}) · LFT visual band</p>
      </div>

      {/* Status summary chips */}
      <div className="flex flex-wrap gap-3">
        {Object.entries(statusCount).filter(([, n]) => n > 0).map(([result, n]) => (
          <div key={result} className={`flex items-center gap-2 px-3 py-2 rounded-lg border ${result === 'Visible' ? 'bg-green-50 border-green-200' : result === 'Faint, but visible' ? 'bg-amber-50 border-amber-200' : result === 'Not visible' ? 'bg-red-50 border-red-200' : 'bg-gray-50 border-gray-200'}`}>
            <span className="w-3 h-3 rounded-full flex-shrink-0" style={{ background: LFT_COLOR[result] }} />
            <span className="text-sm font-bold text-gray-900">{n}</span>
            <span className="text-xs text-gray-600">{PHASE_LABEL[result]}</span>
          </div>
        ))}
        <p className="self-center text-xs text-gray-400 ml-1">as of {lastDate}</p>
      </div>

      {/* Heatmap */}
      <div>
        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Phase progression — all cows</p>
        <div className="overflow-x-auto">
          <table className="text-xs w-full">
            <thead>
              <tr>
                <th className="text-left pr-3 py-1 text-gray-400 font-medium w-16">Cow</th>
                {dates.map(d => (
                  <th key={d} className="text-center px-1 py-1 text-gray-500 font-semibold whitespace-nowrap">{d}</th>
                ))}
                <th className="text-center px-2 py-1 text-gray-400 font-medium">Trend</th>
                <th className="text-left px-2 py-1 text-gray-400 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {cows.map((cowId, i) => {
                const latest = cell[cowId]?.[lastDate];
                const arrow = trendArrow(byCow, cowId);
                return (
                  <tr key={cowId} className={i % 2 === 0 ? 'bg-gray-50/50' : ''}>
                    <td className="pr-3 py-1 font-mono text-gray-600">{cowId}</td>
                    {dates.map(d => {
                      const result = cell[cowId]?.[d];
                      return (
                        <td key={d} className="px-1 py-1 text-center">
                          {result ? (
                            <span
                              className="inline-block w-6 h-6 rounded"
                              style={{ background: LFT_COLOR[result] || '#e5e7eb' }}
                              title={`${result}`}
                            />
                          ) : (
                            <span className="inline-block w-6 h-6 rounded bg-gray-100" />
                          )}
                        </td>
                      );
                    })}
                    <td className="px-2 py-1 text-center font-semibold text-base" style={{
                      color: arrow === '↑' ? '#16a34a' : arrow === '↓' ? '#dc2626' : '#9ca3af'
                    }}>{arrow}</td>
                    <td className="px-2 py-1">
                      {latest && (
                        <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${PHASE_BG[latest]}`}>
                          {PHASE_LABEL[latest]}
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <div className="flex items-center gap-4 mt-3 flex-wrap">
          {Object.entries(LFT_COLOR).filter(([k]) => k !== 'Invalid').map(([k, c]) => (
            <span key={k} className="flex items-center gap-1.5 text-xs text-gray-500">
              <span className="w-3.5 h-3.5 rounded inline-block flex-shrink-0" style={{ background: c }} />
              {PHASE_LABEL[k]}
            </span>
          ))}
          <span className="text-xs text-gray-400 ml-2">· ↑ rising P4 &nbsp; ↓ falling P4 &nbsp; → stable</span>
        </div>
      </div>

      {/* Phase breakdown bar */}
      <div>
        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Phase distribution across test sessions</p>
        <ResponsiveContainer width="100%" height={120}>
          <BarChart
            data={dates.map(d => {
              const counts = { date: d, Luteal: 0, Transitional: 0, Follicular: 0 };
              cows.forEach(c => {
                const r = cell[c]?.[d];
                if (r === 'Visible') counts.Luteal++;
                else if (r === 'Faint, but visible') counts.Transitional++;
                else if (r === 'Not visible') counts.Follicular++;
              });
              return counts;
            })}
            margin={{ top: 0, right: 10, left: -20, bottom: 0 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey="date" tick={{ fontSize: 10 }} />
            <YAxis tick={{ fontSize: 10 }} domain={[0, 20]} />
            <Tooltip />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Bar dataKey="Luteal" stackId="a" fill="#16a34a" radius={[0, 0, 0, 0]} />
            <Bar dataKey="Transitional" stackId="a" fill="#f59e0b" />
            <Bar dataKey="Follicular" stackId="a" fill="#dc2626" radius={[2, 2, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <p className="text-xs text-gray-400">P4 Rapid LFT · visual band reading · {RESEARCH.p4_readings.length} total tests · ELISA comparator values retained in dataset</p>
    </div>
  );
}

// ── Date range toggle ─────────────────────────────────────────────────────
function RangeToggle({ value, onChange }) {
  const opts = [
    { label: '30 days', val: 30 },
    { label: '60 days', val: 60 },
    { label: 'Full dataset', val: 'all' },
  ];
  return (
    <div className="inline-flex rounded-lg border border-gray-200 overflow-hidden">
      {opts.map(o => (
        <button
          key={o.val}
          onClick={() => onChange(o.val)}
          className={`px-3 py-1.5 text-xs font-medium transition-colors ${value === o.val ? 'bg-blue-600 text-white' : 'bg-white text-gray-600 hover:bg-gray-50'}`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

// ── Main dashboard ─────────────────────────────────────────────────────────
export default function ResearchDashboard({ lat, lon, locationName }) {
  const [range, setRange] = useState(60);

  const totalHeatDet = RESEARCH.cow_summary.reduce((s, c) => s + c.total_heat_detections, 0);
  const avgActivity = (RESEARCH.cow_summary.reduce((s, c) => s + c.avg_activity_rate, 0) / RESEARCH.cow_summary.length).toFixed(1);
  const dateFirst = RESEARCH.cow_summary[0]?.date_first;
  const dateLast = RESEARCH.cow_summary[0]?.date_last;

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Herd Monitoring — Farm Dashboard</h1>
          <p className="text-sm text-gray-500 mt-0.5">Bodit behavioural monitoring + P4 Rapid · {dateFirst} to {dateLast}</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400 mr-1">Time range:</span>
          <RangeToggle value={range} onChange={setRange} />
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: 'Animals Monitored', value: RESEARCH.cow_summary.length, unit: 'cows', color: 'text-blue-700' },
          { label: 'Avg Activity Rate', value: `${avgActivity}%`, unit: 'herd average', color: 'text-green-700' },
          { label: 'Total Heat Detections', value: totalHeatDet.toLocaleString(), unit: 'all animals · full period', color: 'text-purple-700' },
          { label: 'P4 Tests Conducted', value: RESEARCH.p4_readings.length, unit: 'LFT results available', color: 'text-orange-700' },
        ].map(k => (
          <div key={k.label} className="bg-white rounded-lg border border-gray-200 p-4">
            <p className="text-xs text-gray-500 font-medium">{k.label}</p>
            <p className={`text-2xl font-bold mt-1 ${k.color}`}>{k.value}</p>
            <p className="text-xs text-gray-400">{k.unit}</p>
          </div>
        ))}
      </div>

      {/* Weather + Markets */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <WeatherWidget lat={lat} lon={lon} locationName={locationName || 'Farm'} />
        <MarketPrices />
      </div>

      {/* Herd activity trend */}
      <HerdActivityChart range={range} />

      {/* Heat detection timeline */}
      <HeatDetectionChart range={range} />

      {/* Herd table */}
      <HerdTable />

      {/* P4 cycle panel */}
      <P4CyclePanel />

      <p className="text-xs text-gray-400 text-center pb-4">
        Bodit sensor: {dateFirst} – {dateLast} · {RESEARCH.cow_summary.reduce((s, c) => s + c.n_days, 0).toLocaleString()} cow-days ·
        P4 Rapid LFT: {RESEARCH.p4_readings.length} tests · Click any row to open the individual cow passport
      </p>
    </div>
  );
}
