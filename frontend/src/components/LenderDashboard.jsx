import React, { useState, useEffect, useCallback } from 'react';
import {
  TrendingUp, TrendingDown, Minus, RefreshCw, X,
  ChevronDown, ChevronUp, AlertTriangle, DollarSign, CreditCard, Shield,
} from 'lucide-react';
import Card from './shared/Card.jsx';
import MetricCard from './shared/MetricCard.jsx';
import AlertBox from './shared/AlertBox.jsx';
import StatusBadge from './shared/StatusBadge.jsx';
import Spinner from './shared/Spinner.jsx';
import { getLenderPortfolio } from '../api/endpoints.js';
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

function TrendIcon({ trend }) {
  if (trend === 'up') return <TrendingUp size={13} className="text-green-600" />;
  if (trend === 'down') return <TrendingDown size={13} className="text-red-600" />;
  return <Minus size={13} className="text-gray-400" />;
}

const SORT_KEYS = ['health_score', 'risk', 'loan_amount', 'trend'];
const SORT_LABELS = { health_score: 'Health Score', risk: 'Risk Level', loan_amount: 'Loan Amount', trend: 'Trend' };
const RISK_ORDER = { low: 1, medium: 2, high: 3 };
const TREND_ORDER = { up: 1, stable: 2, down: 3 };

// Section B: Loan Performance Table
function LoanTable({ loans, onLoanClick, selectedLoanId }) {
  const [sortKey, setSortKey] = useState('health_score');
  const [sortDir, setSortDir] = useState('desc');

  function handleSort(key) {
    if (sortKey === key) {
      setSortDir((d) => d === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(key);
      setSortDir('desc');
    }
  }

  const sorted = [...loans].sort((a, b) => {
    let av, bv;
    if (sortKey === 'risk') {
      av = RISK_ORDER[a.risk] || 0;
      bv = RISK_ORDER[b.risk] || 0;
    } else if (sortKey === 'trend') {
      av = TREND_ORDER[a.trend] || 0;
      bv = TREND_ORDER[b.trend] || 0;
    } else {
      av = a[sortKey] ?? 0;
      bv = b[sortKey] ?? 0;
    }
    if (av < bv) return sortDir === 'asc' ? -1 : 1;
    if (av > bv) return sortDir === 'asc' ? 1 : -1;
    return 0;
  });

  function SortHeader({ k, label }) {
    const active = sortKey === k;
    return (
      <th
        className="text-left py-2 px-2 text-xs font-semibold text-gray-600 cursor-pointer select-none hover:text-gray-900"
        onClick={() => handleSort(k)}
      >
        <span className="flex items-center gap-1">
          {label}
          {active && (sortDir === 'asc' ? <ChevronUp size={11} /> : <ChevronDown size={11} />)}
        </span>
      </th>
    );
  }

  return (
    <div className="overflow-x-auto table-scroll">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-200">
            <th className="text-left py-2 px-2 text-xs font-semibold text-gray-600">Farm</th>
            <th className="text-left py-2 px-2 text-xs font-semibold text-gray-600">Location</th>
            <SortHeader k="loan_amount" label="Loan (NGN)" />
            <SortHeader k="health_score" label="Health Score" />
            <SortHeader k="risk" label="Risk" />
            <SortHeader k="trend" label="Trend" />
            <th className="text-left py-2 px-2 text-xs font-semibold text-gray-600">Maturity</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((loan) => (
            <tr
              key={loan.id}
              className={`border-b border-gray-100 hover:bg-gray-50 cursor-pointer ${selectedLoanId === loan.id ? 'bg-blue-50' : ''}`}
              onClick={() => onLoanClick(loan)}
            >
              <td className="py-2 px-2 font-medium text-gray-900">{loan.farm}</td>
              <td className="py-2 px-2 text-gray-500 text-xs">{loan.location}</td>
              <td className="py-2 px-2 tabular-nums text-gray-700">
                ₦{((loan.loan_amount || 0) / 1000000).toFixed(2)}M
              </td>
              <td className="py-2 px-2">
                <div className="flex items-center gap-2">
                  <div className="w-16 h-1.5 bg-gray-200 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full ${loan.health_score >= 70 ? 'bg-green-500' : loan.health_score >= 40 ? 'bg-amber-500' : 'bg-red-500'}`}
                      style={{ width: `${loan.health_score}%` }}
                    />
                  </div>
                  <span className="text-xs tabular-nums text-gray-700">{loan.health_score}</span>
                </div>
              </td>
              <td className="py-2 px-2"><StatusBadge status={loan.risk} /></td>
              <td className="py-2 px-2"><TrendIcon trend={loan.trend} /></td>
              <td className="py-2 px-2 text-xs text-gray-500">{loan.maturity}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// Section C: Collateral Assessment Panel
function CollateralPanel({ loan, onClose }) {
  if (!loan) return null;

  const ltv = loan.collateral_value > 0
    ? Math.round((loan.loan_amount / loan.collateral_value) * 100)
    : 0;

  const ltvColor = ltv < 70 ? 'text-green-700' : ltv < 90 ? 'text-amber-700' : 'text-red-700';

  return (
    <div
      className="fixed inset-y-0 right-0 z-40 w-80 bg-white border-l border-gray-200 shadow-lg flex flex-col"
      style={{ transition: 'transform 0.2s ease-out' }}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
        <div>
          <h3 className="text-sm font-semibold text-gray-900">{loan.farm}</h3>
          <p className="text-xs text-gray-500">{loan.loan_type} — {loan.location}</p>
        </div>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600 p-1">
          <X size={16} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Valuation */}
        <div className="bg-gray-50 rounded-lg border border-gray-200 p-3">
          <p className="text-xs font-semibold text-gray-700 mb-2">Collateral Valuation</p>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div>
              <p className="text-gray-500">Collateral Value</p>
              <p className="font-semibold text-gray-900">₦{((loan.collateral_value || 0) / 1000000).toFixed(2)}M</p>
            </div>
            <div>
              <p className="text-gray-500">Loan Principal</p>
              <p className="font-semibold text-gray-900">₦{((loan.loan_amount || 0) / 1000000).toFixed(2)}M</p>
            </div>
            <div>
              <p className="text-gray-500">LTV Ratio</p>
              <p className={`font-bold text-base ${ltvColor}`}>{ltv}%</p>
            </div>
            <div>
              <p className="text-gray-500">Valuation Confidence</p>
              <p className="font-semibold text-gray-900">{loan.valuation_confidence || 0}%</p>
            </div>
          </div>
          {/* Confidence bar */}
          <div className="mt-2">
            <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full ${(loan.valuation_confidence || 0) >= 80 ? 'bg-green-500' : (loan.valuation_confidence || 0) >= 60 ? 'bg-amber-500' : 'bg-red-500'}`}
                style={{ width: `${loan.valuation_confidence || 0}%` }}
              />
            </div>
            <p className="text-xs text-gray-400 mt-0.5">Model confidence in valuation</p>
          </div>
        </div>

        {/* Animal breakdown */}
        {loan.animals && (
          <div>
            <p className="text-xs font-semibold text-gray-700 mb-2">Animal Breakdown</p>
            <div className="grid grid-cols-2 gap-2">
              {Object.entries(loan.animals).map(([type, count]) => (
                <div key={type} className="bg-white border border-gray-200 rounded p-2 text-center">
                  <p className="text-lg font-bold text-gray-900">{count}</p>
                  <p className="text-xs text-gray-500 capitalize">{type}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Health alerts */}
        {loan.health_alerts && loan.health_alerts.length > 0 && (
          <div>
            <p className="text-xs font-semibold text-gray-700 mb-2">Health Alerts</p>
            <div className="space-y-2">
              {loan.health_alerts.map((alert, i) => (
                <AlertBox key={i} level="warning" message={alert} />
              ))}
            </div>
          </div>
        )}

        {loan.health_alerts && loan.health_alerts.length === 0 && (
          <AlertBox level="success" title="No Health Alerts" message="Collateral herd is in good health. No risk factors detected." />
        )}
      </div>
    </div>
  );
}

// Section D: Early Warning Alerts
function EarlyWarningSection({ warnings }) {
  const [expandedIdx, setExpandedIdx] = useState(null);

  const categories = ['Health Decline', 'Climate Risk', 'Maturity Risk'];

  return (
    <div className="space-y-4">
      {categories.map((cat) => {
        const catWarnings = warnings.filter((w) => w.category === cat);
        if (catWarnings.length === 0) return null;
        return (
          <div key={cat}>
            <p className="text-xs font-semibold text-gray-700 mb-2">{cat}</p>
            <div className="space-y-2">
              {catWarnings.map((w, i) => {
                const key = `${cat}-${i}`;
                return (
                  <div key={key}>
                    <button
                      className="w-full text-left"
                      onClick={() => setExpandedIdx(expandedIdx === key ? null : key)}
                    >
                      <AlertBox
                        level={w.severity}
                        title={w.farm}
                        message={expandedIdx === key ? w.detail : `${w.detail.substring(0, 80)}…`}
                      />
                    </button>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// Section E: Loan Pipeline
function LoanPipeline({ pipeline }) {
  if (!pipeline || pipeline.length === 0) return <p className="text-sm text-gray-500">No pipeline opportunities.</p>;

  return (
    <div className="space-y-3">
      {pipeline.map((item, i) => (
        <div key={i} className="border border-gray-200 rounded-lg p-3">
          <div className="flex items-start justify-between gap-2">
            <div>
              <p className="text-sm font-semibold text-gray-900">{item.farm}</p>
              <p className="text-xs text-gray-500">{item.location}</p>
            </div>
            <span className={`text-xs px-2 py-0.5 rounded font-medium flex-shrink-0 ${item.opportunity === 'new_loan' ? 'bg-blue-100 text-blue-800' : 'bg-green-100 text-green-800'}`}>
              {item.opportunity === 'new_loan' ? 'New Loan' : 'Refinance'}
            </span>
          </div>
          <p className="mt-2 text-xs text-gray-600">{item.recommended_modification}</p>
          <div className="mt-2 flex items-center gap-3 text-xs text-gray-500">
            <span>Health score: <span className="font-medium text-gray-700">{item.health_score}</span></span>
            {item.current_loan > 0 && (
              <span>Current exposure: <span className="font-medium text-gray-700">₦{(item.current_loan / 1000000).toFixed(2)}M</span></span>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

// Main LenderDashboard
export default function LenderDashboard() {
  const { user } = useAuth();
  const lenderId = user?.org_id || 'lender_001';

  const [portfolioData, setPortfolioData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [selectedLoan, setSelectedLoan] = useState(null);

  async function loadData() {
    setLoading(true); setError(false);
    try {
      const res = await getLenderPortfolio(lenderId);
      setPortfolioData(res.data);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadData(); }, [lenderId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Spinner size="lg" label="Loading portfolio data…" />
      </div>
    );
  }

  if (error || !portfolioData) {
    return <SectionError onRetry={loadData} />;
  }

  const { total_loans, total_collateral_ngn, at_risk_loans, overall_risk, loans, pipeline, early_warnings } = portfolioData;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-bold text-gray-900">Lender Intelligence Dashboard</h1>
        <p className="text-sm text-gray-500 mt-0.5">Portfolio health, collateral assessment, and early warnings</p>
      </div>

      {/* Section A: Portfolio Summary */}
      <section aria-label="Portfolio Summary">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <MetricCard label="Total Active Loans" value={total_loans} trend={null} icon={CreditCard} color="blue" />
          <MetricCard label="Total Collateral" value={`₦${((total_collateral_ngn || 0) / 1000000).toFixed(1)}M`} trend={null} icon={Shield} color="green" />
          <MetricCard label="At-Risk Loans" value={at_risk_loans} trend={null} icon={AlertTriangle} color="amber" />
          <MetricCard label="Portfolio Risk" value={(overall_risk || 'N/A').toUpperCase()} trend={null} icon={DollarSign} color={overall_risk === 'low' ? 'green' : overall_risk === 'high' ? 'red' : 'amber'} />
        </div>
      </section>

      {/* Section B: Loan Performance Table */}
      <section aria-label="Loan Performance">
        <Card title="Loan Performance — Click a row to view collateral details">
          {loans && loans.length > 0 ? (
            <LoanTable
              loans={loans}
              onLoanClick={(loan) => setSelectedLoan(selectedLoan?.id === loan.id ? null : loan)}
              selectedLoanId={selectedLoan?.id}
            />
          ) : (
            <p className="text-sm text-gray-500">No loans in portfolio.</p>
          )}
        </Card>
      </section>

      {/* Section D & E: Warnings + Pipeline */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <section aria-label="Early Warning Alerts">
          <Card title="Early Warning Alerts">
            {early_warnings && early_warnings.length > 0 ? (
              <EarlyWarningSection warnings={early_warnings} />
            ) : (
              <AlertBox level="success" title="No Active Warnings" message="All portfolio farms are within acceptable risk thresholds." />
            )}
          </Card>
        </section>

        <section aria-label="Loan Pipeline">
          <Card title="Loan Pipeline & Opportunities">
            <LoanPipeline pipeline={pipeline} />
          </Card>
        </section>
      </div>

      {/* Section C: Collateral Assessment Panel (slide-in) */}
      {selectedLoan && (
        <>
          {/* Overlay */}
          <div
            className="fixed inset-0 z-30 bg-black/20"
            onClick={() => setSelectedLoan(null)}
          />
          <CollateralPanel
            loan={selectedLoan}
            onClose={() => setSelectedLoan(null)}
          />
        </>
      )}
    </div>
  );
}
