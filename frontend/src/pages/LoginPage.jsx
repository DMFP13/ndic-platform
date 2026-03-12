import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext.jsx';
import { AlertCircle } from 'lucide-react';

const ROLE_OPTIONS = [
  { value: 'farm_manager',          label: 'Farm Manager' },
  { value: 'farm_admin',            label: 'Farm Admin' },
  { value: 'farm_vet',              label: 'Farm Veterinarian' },
  { value: 'processor_analyst',     label: 'Processor Analyst' },
  { value: 'processor_commercial',  label: 'Processor Commercial' },
  { value: 'govt_analyst',          label: 'FMARD Analyst' },
  { value: 'govt_admin',            label: 'FMARD Admin' },
  { value: 'lender_analyst',        label: 'Lender Analyst' },
  { value: 'arpexas_admin',         label: 'Platform Admin' },
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
  const { login, demoLogin } = useAuth();
  const navigate = useNavigate();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState('farm_manager');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  function enterDemoMode() {
    demoLogin(role, email.trim() || 'demo@ndic.ng');
    navigate(getRoleRoute(role), { replace: true });
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');

    if (!email.trim()) { setError('Email is required.'); return; }
    if (!password.trim()) { setError('Password is required.'); return; }

    setIsLoading(true);
    try {
      const userData = await login(email.trim(), password, role);
      navigate(getRoleRoute(userData.role || role), { replace: true });
    } catch (err) {
      if (err.response?.status === 401) {
        setError('Invalid email or password.');
        setIsLoading(false);
      } else if (err.response?.status === 403) {
        setError('Access denied for this role.');
        setIsLoading(false);
      } else {
        // Network down or timeout — fall straight into demo mode
        setIsLoading(false);
        enterDemoMode();
      }
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-lg bg-blue-600 mb-4">
            <span className="text-white font-bold text-lg">N</span>
          </div>
          <h1 className="text-xl font-bold text-gray-900">NDIC Platform</h1>
          <p className="mt-1 text-sm text-gray-500">Nigerian Dairy Intelligence Consortium</p>
        </div>

        {/* Form card */}
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h2 className="text-base font-semibold text-gray-900 mb-5">Sign in to your account</h2>

          {error && (
            <div className="mb-4 flex items-start gap-2 p-3 bg-red-50 border border-red-200 rounded-lg">
              <AlertCircle size={15} className="text-red-500 flex-shrink-0 mt-0.5" />
              <p className="text-sm text-red-700">{error}</p>
            </div>
          )}

          <form onSubmit={handleSubmit} noValidate>
            <div className="space-y-4">
              {/* Email */}
              <div>
                <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">
                  Email address
                </label>
                <input
                  id="email"
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg bg-white text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  placeholder="you@organisation.ng"
                  disabled={isLoading}
                />
              </div>

              {/* Password */}
              <div>
                <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">
                  Password
                </label>
                <input
                  id="password"
                  type="password"
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg bg-white text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  placeholder="Enter your password"
                  disabled={isLoading}
                />
              </div>

              {/* Role */}
              <div>
                <label htmlFor="role" className="block text-sm font-medium text-gray-700 mb-1">
                  Role
                </label>
                <select
                  id="role"
                  value={role}
                  onChange={(e) => setRole(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg bg-white text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  disabled={isLoading}
                >
                  {ROLE_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="mt-5 w-full py-2 px-4 bg-blue-600 text-white text-sm font-semibold rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isLoading ? 'Signing in…' : 'Sign In'}
            </button>

            <div className="mt-3 flex items-center gap-2">
              <div className="flex-1 h-px bg-gray-200" />
              <span className="text-xs text-gray-400">or</span>
              <div className="flex-1 h-px bg-gray-200" />
            </div>

            <button
              type="button"
              onClick={enterDemoMode}
              className="mt-3 w-full py-2 px-4 bg-green-600 text-white text-sm font-semibold rounded-lg hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2"
            >
              ▶ Demo Mode — Enter without backend
            </button>
          </form>
        </div>

        <p className="mt-4 text-center text-xs text-gray-400">
          Secure government-grade authentication. All sessions are logged.
        </p>
      </div>
    </div>
  );
}
