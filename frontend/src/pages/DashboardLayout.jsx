import React, { useState, useEffect } from 'react';
import { Outlet, NavLink, useNavigate, useLocation, Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext.jsx';
import {
  LayoutDashboard, Leaf, Factory, Building2, CreditCard,
  LogOut, ChevronLeft, ChevronRight, ClipboardList, Bell,
  X, ChevronRight as Chevron,
} from 'lucide-react';

const ROLE_NAV = {
  farm_manager:         [{ label: 'Farm Dashboard', path: '/farm', icon: Leaf }],
  farm_admin:           [{ label: 'Farm Dashboard', path: '/farm', icon: Leaf }],
  farm_vet:             [{ label: 'Farm Dashboard', path: '/farm', icon: Leaf }],
  processor_analyst:    [{ label: 'Processor Dashboard', path: '/processor', icon: Factory }],
  processor_commercial: [{ label: 'Processor Dashboard', path: '/processor', icon: Factory }],
  govt_analyst:         [{ label: 'Government Dashboard', path: '/government', icon: Building2 }],
  govt_admin:           [{ label: 'Government Dashboard', path: '/government', icon: Building2 }],
  arpexas_admin:        [{ label: 'Government Dashboard', path: '/government', icon: Building2 }],
  lender_analyst:       [{ label: 'Lender Dashboard', path: '/lender', icon: CreditCard }],
};

const ROLE_BADGE = {
  farm_manager:         { label: 'Farm',       className: 'bg-green-100 text-green-800' },
  farm_admin:           { label: 'Farm',       className: 'bg-green-100 text-green-800' },
  farm_vet:             { label: 'Vet',        className: 'bg-teal-100 text-teal-800' },
  processor_analyst:    { label: 'Processor',  className: 'bg-blue-100 text-blue-800' },
  processor_commercial: { label: 'Processor',  className: 'bg-blue-100 text-blue-800' },
  govt_analyst:         { label: 'Government', className: 'bg-purple-100 text-purple-800' },
  govt_admin:           { label: 'Government', className: 'bg-purple-100 text-purple-800' },
  arpexas_admin:        { label: 'Admin',      className: 'bg-red-100 text-red-800' },
  lender_analyst:       { label: 'Lender',     className: 'bg-amber-100 text-amber-800' },
};

function AuditPanel({ onClose }) {
  const [entries, setEntries] = useState([]);
  useEffect(() => {
    const raw = JSON.parse(localStorage.getItem('ndic_audit_log') || '[]');
    setEntries(raw.slice(0, 5));
  }, []);

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-end" onClick={onClose}>
      <div
        className="mt-14 mr-2 w-80 bg-white rounded-lg border border-gray-200 shadow-lg p-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-gray-900">Recent Audit Events</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X size={14} />
          </button>
        </div>
        {entries.length === 0 ? (
          <p className="text-sm text-gray-500">No events recorded.</p>
        ) : (
          <ul className="space-y-2">
            {entries.map((e, i) => (
              <li key={i} className="border-b border-gray-100 pb-2 last:border-0 last:pb-0">
                <p className="text-xs font-medium text-gray-700 capitalize">{e.event}</p>
                <p className="text-xs text-gray-500">{e.user} — {e.role}</p>
                <p className="text-xs text-gray-400">{new Date(e.timestamp).toLocaleString()}</p>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

export default function DashboardLayout() {
  const { user, isAuthenticated, logout, loading } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [auditOpen, setAuditOpen] = useState(false);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <p className="text-sm text-gray-500">Loading…</p>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  const role = user?.role || '';
  const navLinks = ROLE_NAV[role] || [];
  const badge = ROLE_BADGE[role] || { label: role, className: 'bg-gray-100 text-gray-700' };

  const currentLink = navLinks.find((l) => location.pathname.startsWith(l.path));
  const breadcrumb = currentLink?.label || 'Dashboard';

  function handleLogout() {
    logout();
    navigate('/login', { replace: true });
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Top nav */}
      <header className="h-12 bg-white border-b border-gray-200 flex items-center px-4 gap-4 z-10 flex-shrink-0">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded bg-blue-600 flex items-center justify-center">
            <span className="text-white text-xs font-bold">N</span>
          </div>
          <span className="text-sm font-semibold text-gray-900 hidden sm:block">NDIC</span>
        </div>

        <div className="flex items-center gap-1 text-gray-400 text-xs hidden sm:flex">
          <Chevron size={12} />
          <span className="text-gray-600">{breadcrumb}</span>
        </div>

        <div className="ml-auto flex items-center gap-3">
          <button
            onClick={() => setAuditOpen((v) => !v)}
            className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700 px-2 py-1 rounded hover:bg-gray-100"
            title="Audit log"
            aria-label="View recent audit events"
          >
            <ClipboardList size={14} />
            <span className="hidden sm:block">Audit</span>
          </button>

          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-600 hidden sm:block">{user?.email || user?.user_id}</span>
            <span className={`text-xs px-2 py-0.5 rounded font-medium ${badge.className}`}>
              {badge.label}
            </span>
          </div>

          <button
            onClick={handleLogout}
            className="flex items-center gap-1 text-xs text-gray-500 hover:text-red-600 px-2 py-1 rounded hover:bg-red-50"
            aria-label="Sign out"
          >
            <LogOut size={14} />
            <span className="hidden sm:block">Logout</span>
          </button>
        </div>
      </header>

      {auditOpen && <AuditPanel onClose={() => setAuditOpen(false)} />}

      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        <aside className={`bg-white border-r border-gray-200 flex flex-col transition-all duration-200 flex-shrink-0 ${sidebarCollapsed ? 'w-12' : 'w-48'}`}>
          <nav className="flex-1 p-2 space-y-1" aria-label="Main navigation">
            {navLinks.map(({ label, path, icon: Icon }) => (
              <NavLink
                key={path}
                to={path}
                className={({ isActive }) =>
                  `flex items-center gap-2 px-2 py-2 rounded-lg text-xs font-medium transition-colors ${
                    isActive
                      ? 'bg-blue-50 text-blue-700'
                      : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
                  }`
                }
                title={sidebarCollapsed ? label : undefined}
              >
                <Icon size={16} className="flex-shrink-0" />
                {!sidebarCollapsed && <span>{label}</span>}
              </NavLink>
            ))}
          </nav>

          <button
            onClick={() => setSidebarCollapsed((v) => !v)}
            className="m-2 p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 flex items-center justify-center"
            aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {sidebarCollapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
          </button>
        </aside>

        {/* Main content */}
        <main className="flex-1 overflow-auto p-4 md:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
