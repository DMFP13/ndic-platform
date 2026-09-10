import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext.jsx';

const DEMO_ACCOUNTS = [
  { role: 'farm_manager',         label: 'Farm Manager',      email: 'farm@ndic.ng',      desc: 'Herd health, AI insights, milk yield' },
  { role: 'govt_analyst',         label: 'FMARD Analyst',     email: 'govt@ndic.ng',       desc: 'Disease map, production trends, alerts' },
  { role: 'lender_analyst',       label: 'Lender Analyst',    email: 'lender@ndic.ng',     desc: 'Portfolio risk, collateral valuation' },
  { role: 'processor_analyst',    label: 'Processor Analyst', email: 'processor@ndic.ng',  desc: 'Supply forecast, supplier benchmarking' },
];

function getRoleRoute(role) {
  if (['farm_manager', 'farm_admin', 'farm_vet'].includes(role)) return '/farm';
  if (role === 'processor_analyst' || role === 'processor_commercial') return '/processor';
  if (role === 'govt_analyst' || role === 'govt_admin') return '/government';
  if (role === 'lender_analyst') return '/lender';
  if (role === 'arpexas_admin') return '/government';
  return '/login';
}

export default function LoginPage() {
  const { demoLogin } = useAuth();
  const navigate = useNavigate();
  const [selected, setSelected] = useState('farm_manager');

  function enter(role, email) {
    demoLogin(role, email);
    navigate(getRoleRoute(role), { replace: true });
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-lg bg-blue-600 mb-4">
            <span className="text-white font-bold text-lg">N</span>
          </div>
          <h1 className="text-xl font-bold text-gray-900">NDIC Platform</h1>
          <p className="mt-1 text-sm text-gray-500">Nigerian Dairy Intelligence Consortium</p>
        </div>

        {/* Demo accounts */}
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h2 className="text-base font-semibold text-gray-900 mb-1">Select a demo account</h2>
          <p className="text-xs text-gray-400 mb-4">Each role shows a different view of the platform</p>

          <div className="space-y-2 mb-5">
            {DEMO_ACCOUNTS.map((a) => (
              <button
                key={a.role}
                type="button"
                onClick={() => setSelected(a.role)}
                className={`w-full text-left px-4 py-3 rounded-lg border transition-all ${
                  selected === a.role
                    ? 'border-blue-500 bg-blue-50 ring-1 ring-blue-500'
                    : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-semibold text-gray-900">{a.label}</p>
                    <p className="text-xs text-gray-500 mt-0.5">{a.desc}</p>
                  </div>
                  <span className="text-xs text-gray-400 font-mono">{a.email}</span>
                </div>
              </button>
            ))}
          </div>

          <button
            type="button"
            onClick={() => {
              const acct = DEMO_ACCOUNTS.find((a) => a.role === selected);
              enter(acct.role, acct.email);
            }}
            className="w-full py-2.5 px-4 bg-blue-600 text-white text-sm font-semibold rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-colors"
          >
            Enter Demo →
          </button>
        </div>

        <p className="mt-4 text-center text-xs text-gray-400">
          Demo data only — no real data is stored or transmitted.
        </p>
      </div>
    </div>
  );
}
