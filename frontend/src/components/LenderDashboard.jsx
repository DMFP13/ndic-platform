import React, { useState, useMemo } from 'react';
import {
  BarChart, Bar, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, Cell, ReferenceLine,
} from 'recharts';
import NETWORK from '../data/farm_network.json';

// Lender portfolio = farms 0–13 (14 farms, mix of tiers)
const PORTFOLIO = NETWORK.farms.slice(0, 14);
const MONTHS = ['Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep'];

const GRADE_COLOR = { 'A+': '#15803d', A: '#16a34a', 'B': '#65a30d', 'B-': '#ca8a04', 'C+': '#d97706', C: '#ea580c', 'C-': '#dc2626', D: '#b91c1c', 'D+': '#ef4444', E: '#7f1d1d' };
const GRADE_BG = { 'A+': 'bg-green-100 text-green-900', A: 'bg-green-100 text-green-800', B: 'bg-lime-100 text-lime-800', 'B-': 'bg-yellow-100 text-yellow-800', 'C+': 'bg-amber-100 text-amber-800', C: 'bg-orange-100 text-orange-800', 'C-': 'bg-red-100 text-red-700', D: 'bg-red-100 text-red-700', 'D+': 'bg-red-100 text-red-700', E: 'bg-red-200 text-red-900' };

function KPI({ label, value, sub, color = 'text-blue-700' }) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <p className="text-xs text-gray-500 font-medium">{label}</p>
      <p className={`text-2xl font-bold mt-1 ${color}`}>{value}</p>
      {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
    </div>
  );
}

function RiskRanking() {
  const [sort, setSort] = useState('risk_score');
  const sorted = useMemo(() =>
    [...PORTFOLIO].sort((a, b) => sort === 'risk_score' ? b.risk_score - a.risk_score : a.risk_score - b.risk_score),
    [sort]
  );

  return (
    <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
      <div className="px-5 py-3 border-b border-gray-100 flex items-center justify-between flex-wrap gap-2">
        <p className="text-sm font-semibold text-gray-900">Portfolio — {PORTFOLIO.length} Farms</p>
        <select className="text-xs border border-gray-200 rounded px-2 py-1" value={sort} onChange={e => setSort(e.target.value)}>
          <option value="risk_score">Sort: Best score first</option>
          <option value="asc">Sort: At-risk first</option>
        </select>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-2 text-left text-xs font-semibold text-gray-500">Farm</th>
              <th className="px-4 py-2 text-right text-xs font-semibold text-gray-500">Score</th>
              <th className="px-4 py-2 text-right text-xs font-semibold text-gray-500">Activity %</th>
              <th className="px-4 py-2 text-right text-xs font-semibold text-gray-500">Milk L/cow</th>
              <th className="px-4 py-2 text-right text-xs font-semibold text-gray-500">Loan (₦)</th>
              <th className="px-4 py-2 text-right text-xs font-semibold text-gray-500">Collateral (₦)</th>
              <th className="px-4 py-2 text-right text-xs font-semibold text-gray-500">LTV</th>
              <th className="px-4 py-2 text-right text-xs font-semibold text-gray-500">Disease</th>
              <th className="px-4 py-2 text-center text-xs font-semibold text-gray-500">Grade</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((f, i) => {
              const ltv = ((f.loan_NGN / f.collateral_NGN) * 100).toFixed(0);
              const atRisk = f.risk_score < 60;
              return (
                <tr key={f.id} className={`border-t border-gray-50 ${atRisk ? 'bg-red-50/40' : i % 2 ? 'bg-gray-50/30' : ''}`}>
                  <td className="px-4 py-2">
                    <p className="text-xs font-semibold text-gray-800">{f.name}</p>
                    <p className="text-xs text-gray-400">{f.state}</p>
                  </td>
                  <td className="px-4 py-2 text-right">
                    <span className="font-bold text-sm" style={{ color: GRADE_COLOR[f.risk_grade] || '#374151' }}>{f.risk_score}</span>
                  </td>
                  <td className="px-4 py-2 text-right">
                    <span className={`text-sm font-semibold ${f.avg_activity_rate > 70 ? 'text-green-700' : f.avg_activity_rate > 55 ? 'text-amber-700' : 'text-red-600'}`}>
                      {f.avg_activity_rate.toFixed(1)}%
                    </span>
                  </td>
                  <td className="px-4 py-2 text-right text-sm text-gray-700">{f.avg_milk_yield_L.toFixed(1)}</td>
                  <td className="px-4 py-2 text-right text-sm text-gray-700">{(f.loan_NGN / 1000000).toFixed(1)}M</td>
                  <td className="px-4 py-2 text-right text-sm text-gray-600">{(f.collateral_NGN / 1000000).toFixed(1)}M</td>
                  <td className="px-4 py-2 text-right">
                    <span className={`text-sm font-semibold ${Number(ltv) > 60 ? 'text-red-600' : Number(ltv) > 45 ? 'text-amber-600' : 'text-green-700'}`}>
                      {ltv}%
                    </span>
                  </td>
                  <td className="px-4 py-2 text-right">
                    <span className={`text-sm ${f.disease_events >= 6 ? 'text-red-600 font-semibold' : 'text-gray-600'}`}>{f.disease_events}</span>
                  </td>
                  <td className="px-4 py-2 text-center">
                    <span className={`px-2 py-0.5 rounded text-xs font-bold ${GRADE_BG[f.risk_grade] || 'bg-gray-100 text-gray-600'}`}>{f.risk_grade}</span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="px-5 py-2 text-xs text-gray-400 border-t border-gray-50">
        Risk score derived from: herd activity rate, milk yield trend, disease burden, coughing index · Score &lt;60 = at-risk
      </p>
    </div>
  );
}

function RiskScoreChart() {
  const data = [...PORTFOLIO]
    .sort((a, b) => b.risk_score - a.risk_score)
    .map(f => ({ name: f.name.split(' ').slice(-1)[0], score: f.risk_score, grade: f.risk_grade, activity: f.avg_activity_rate }));

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-5">
      <p className="text-sm font-semibold text-gray-900 mb-1">Portfolio Risk Scores</p>
      <p className="text-xs text-gray-400 mb-3">All {PORTFOLIO.length} financed farms · red line = 60 threshold</p>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={data} margin={{ top: 0, right: 10, left: -20, bottom: 40 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis dataKey="name" tick={{ fontSize: 9 }} angle={-40} textAnchor="end" />
          <YAxis tick={{ fontSize: 10 }} domain={[0, 100]} />
          <Tooltip formatter={(v, n, p) => [v, `Score (${p.payload.grade})`]} />
          <ReferenceLine y={60} stroke="#dc2626" strokeDasharray="4 3" label={{ value: 'At-risk', fontSize: 9, fill: '#dc2626', position: 'right' }} />
          <Bar dataKey="score" name="Risk score" radius={[3, 3, 0, 0]}>
            {data.map((d, i) => (
              <Cell key={i} fill={d.score >= 80 ? '#16a34a' : d.score >= 65 ? '#f59e0b' : '#dc2626'} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function PortfolioTrend() {
  // Sensor-derived: activity rate drives collateral value (herd health = herd value)
  const data = MONTHS.map((m, i) => {
    const totalLoan = PORTFOLIO.reduce((s, f) => s + f.loan_NGN, 0);
    const weightedActivity = PORTFOLIO.reduce((s, f) => {
      // Activity trend: assume slight improvement for high tier, decline for low
      const trend = f.tier === 'high' ? 0.002 * i : f.tier === 'low' ? -0.004 * i : -0.001 * i;
      return s + (f.avg_activity_rate + f.avg_activity_rate * trend);
    }, 0) / PORTFOLIO.length;
    const collateralIndex = (weightedActivity / PORTFOLIO[0].avg_activity_rate) * 100;
    return { month: m, activity: weightedActivity.toFixed(1), collateral_idx: collateralIndex.toFixed(1) };
  });

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-5">
      <p className="text-sm font-semibold text-gray-900 mb-1">Portfolio Health Trend — Activity Rate</p>
      <p className="text-xs text-gray-400 mb-3">Weighted average herd activity across portfolio · proxy for collateral health</p>
      <ResponsiveContainer width="100%" height={170}>
        <LineChart data={data} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis dataKey="month" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 10 }} domain={[60, 80]} unit="%" />
          <Tooltip formatter={(v) => [`${v}%`, 'Portfolio avg activity']} />
          <Line type="monotone" dataKey="activity" name="Avg activity %" stroke="#3b82f6" dot={{ r: 4 }} strokeWidth={2} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function AtRiskAlerts() {
  const at_risk = PORTFOLIO.filter(f => f.risk_score < 65).sort((a,b) => a.risk_score - b.risk_score);
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-5">
      <div className="flex items-center gap-2 mb-3">
        <span className="w-2.5 h-2.5 rounded-full bg-red-500 animate-pulse" />
        <p className="text-sm font-semibold text-gray-900">At-Risk Borrowers</p>
      </div>
      <div className="space-y-2">
        {at_risk.map(f => {
          const ltv = ((f.loan_NGN / f.collateral_NGN) * 100).toFixed(0);
          return (
            <div key={f.id} className="rounded-lg border border-red-200 bg-red-50 px-3 py-2">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-xs font-semibold text-gray-800">{f.name}</p>
                  <p className="text-xs text-gray-500">{f.state} · Score: <b className="text-red-600">{f.risk_score}</b> ({f.risk_grade})</p>
                  <p className="text-xs text-gray-500 mt-0.5">Activity: {f.avg_activity_rate.toFixed(1)}% · Disease: {f.disease_events} events</p>
                  {f.notes && <p className="text-xs text-red-600 mt-0.5">{f.notes.replace('⚠ ', '')}</p>}
                </div>
                <div className="text-right ml-2 flex-shrink-0">
                  <p className="text-xs font-semibold text-gray-700">LTV {ltv}%</p>
                  <p className="text-xs text-gray-500">₦{(f.loan_NGN/1000000).toFixed(1)}M loan</p>
                </div>
              </div>
            </div>
          );
        })}
      </div>
      <p className="mt-2 text-xs text-gray-400">{at_risk.length} of {PORTFOLIO.length} borrowers below threshold</p>
    </div>
  );
}

export default function LenderDashboard() {
  const totalLoan = PORTFOLIO.reduce((s, f) => s + f.loan_NGN, 0);
  const totalCollateral = PORTFOLIO.reduce((s, f) => s + f.collateral_NGN, 0);
  const atRisk = PORTFOLIO.filter(f => f.risk_score < 60).length;
  const avgScore = (PORTFOLIO.reduce((s, f) => s + f.risk_score, 0) / PORTFOLIO.length).toFixed(0);
  const portfolioLTV = ((totalLoan / totalCollateral) * 100).toFixed(1);

  return (
    <div className="p-6 space-y-5">
      <div>
        <h1 className="text-xl font-bold text-gray-900">Lender Portfolio — {NETWORK.region}</h1>
        <p className="text-sm text-gray-500 mt-0.5">
          {PORTFOLIO.length} financed farms · risk scores derived from Bodit sensor data · {NETWORK.period}
        </p>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KPI label="Portfolio Exposure" value={`₦${(totalLoan/1000000).toFixed(1)}M`} sub={`${PORTFOLIO.length} active loans`} color="text-blue-700" />
        <KPI label="Collateral Value" value={`₦${(totalCollateral/1000000).toFixed(1)}M`} sub="sensor-validated herd value" color="text-green-700" />
        <KPI label="Portfolio LTV" value={`${portfolioLTV}%`} sub="lower is safer" color={Number(portfolioLTV) > 50 ? 'text-amber-700' : 'text-green-700'} />
        <KPI label="At-Risk Borrowers" value={atRisk} sub={`score <60 · avg score ${avgScore}`} color={atRisk > 2 ? 'text-red-600' : 'text-amber-600'} />
      </div>

      {/* Risk chart + trend + alerts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <div className="lg:col-span-2 space-y-5">
          <RiskScoreChart />
          <PortfolioTrend />
        </div>
        <AtRiskAlerts />
      </div>

      {/* Portfolio table */}
      <RiskRanking />

      <p className="text-xs text-gray-400 text-center pb-4">
        Risk score = weighted composite of herd activity rate, milk yield, disease burden, coughing index · sensor-derived · {NETWORK.period}
      </p>
    </div>
  );
}
