import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext.jsx';

const DEMO_ACCOUNTS = [
  { role: 'research_analyst', label: 'Farm Manager',        email: 'farm@ndic.ng',      desc: 'Herd health, AI insights, milk yield' },
  { role: 'processor_analyst',label: 'Processor Analyst',   email: 'processor@ndic.ng', desc: 'Supply forecast, supplier benchmarking' },
  { role: 'farm_vet',         label: 'Veterinary Officer',   email: 'vet@ndic.ng',       desc: 'Priority health queue, P4 monitoring, vaccinations' },
  { role: 'govt_analyst',     label: 'Government (FMARD)',  email: 'govt@ndic.ng',      desc: 'Regional map, disease outbreaks, production trends' },
  { role: 'research_analyst', label: 'Research Dashboard',  email: 'research@ndic.ng',  desc: 'Bodit sensors · P4 Rapid · live weather & markets' },
];

function getRoleRoute(role) {
  if (['farm_manager', 'farm_admin', 'farm_vet'].includes(role)) return '/farm';
  if (role === 'processor_analyst' || role === 'processor_commercial') return '/processor';
  if (role === 'govt_analyst' || role === 'govt_admin') return '/government';
  if (role === 'lender_analyst') return '/lender';
  if (role === 'farm_vet') return '/vet';
  if (role === 'arpexas_admin') return '/government';
  if (role === 'research_analyst') return '/research';
  return '/login';
}

export default function LoginPage() {
  const { demoLogin } = useAuth();
  const navigate = useNavigate();
  const [selected, setSelected] = useState('farm@ndic.ng');

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
                onClick={() => setSelected(a.email)}
                className={`w-full text-left px-4 py-3 rounded-lg border transition-all ${
                  selected === a.email
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
              const acct = DEMO_ACCOUNTS.find((a) => a.email === selected);
              enter(acct.role, acct.email);
            }}
            className="w-full py-2.5 px-4 bg-blue-600 text-white text-sm font-semibold rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-colors"
          >
            Enter Demo →
          </button>
        </div>

        <div className="mt-4 flex items-start gap-2 px-1">
          <div className="w-1.5 h-1.5 rounded-full bg-green-500 flex-shrink-0 mt-1.5" />
          <p className="text-xs text-gray-400 leading-relaxed">
            All sessions are cryptographically logged. Data access is role-scoped and immutably audited in accordance with NDIC governance policy.
          </p>
        </div>
      </div>
    </div>
  );
}
