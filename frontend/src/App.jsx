import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext.jsx';
import LoginPage from './pages/LoginPage.jsx';
import DashboardLayout from './pages/DashboardLayout.jsx';
import AnimalPassportPage from './pages/AnimalPassportPage.jsx';
import FarmDashboard from './components/FarmDashboard.jsx';
import ProcessorDashboard from './components/ProcessorDashboard.jsx';
import GovDashboard from './components/GovDashboard.jsx';
import LenderDashboard from './components/LenderDashboard.jsx';
import ResearchDashboard from './components/ResearchDashboard.jsx';
import ResearchCowPassport from './pages/ResearchCowPassport.jsx';

const FARM_ROLES = ['farm_manager', 'farm_admin', 'farm_vet'];
const PASSPORT_READ_ROLES = [
  ...FARM_ROLES,
  'processor_analyst', 'processor_commercial',
  'govt_analyst', 'govt_admin',
  'lender_analyst', 'arpexas_admin',
];

function RoleRoute({ children, allowedRoles }) {
  const { user, isAuthenticated, loading } = useAuth();
  if (loading) return null;
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  if (allowedRoles && !allowedRoles.includes(user?.role)) {
    return <Navigate to="/login" replace />;
  }
  return children;
}

function RootRedirect() {
  const { user, isAuthenticated, loading } = useAuth();
  if (loading) return null;
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  const role = user?.role;
  if (FARM_ROLES.includes(role)) return <Navigate to="/research" replace />;
  if (role === 'processor_analyst' || role === 'processor_commercial') return <Navigate to="/processor" replace />;
  if (role === 'govt_analyst' || role === 'govt_admin' || role === 'arpexas_admin') return <Navigate to="/government" replace />;
  if (role === 'lender_analyst') return <Navigate to="/lender" replace />;
  if (role === 'research_analyst') return <Navigate to="/research" replace />;
  return <Navigate to="/login" replace />;
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<RootRedirect />} />

      {/* Cow passport — readable by all roles, no layout wrapper */}
      <Route
        path="/animals/:animalId"
        element={
          <RoleRoute allowedRoles={PASSPORT_READ_ROLES}>
            <AnimalPassportPage />
          </RoleRoute>
        }
      />
      <Route
        path="/farm/animals/:animalId"
        element={
          <RoleRoute allowedRoles={PASSPORT_READ_ROLES}>
            <AnimalPassportPage />
          </RoleRoute>
        }
      />

      <Route
        path="/farm"
        element={
          <RoleRoute allowedRoles={FARM_ROLES}>
            <DashboardLayout />
          </RoleRoute>
        }
      >
        <Route index element={<FarmDashboard />} />
      </Route>

      <Route
        path="/processor"
        element={
          <RoleRoute allowedRoles={['processor_analyst', 'processor_commercial']}>
            <DashboardLayout />
          </RoleRoute>
        }
      >
        <Route index element={<ProcessorDashboard />} />
      </Route>

      <Route
        path="/government"
        element={
          <RoleRoute allowedRoles={['govt_analyst', 'govt_admin', 'arpexas_admin']}>
            <DashboardLayout />
          </RoleRoute>
        }
      >
        <Route index element={<GovDashboard />} />
      </Route>

      <Route
        path="/lender"
        element={
          <RoleRoute allowedRoles={['lender_analyst']}>
            <DashboardLayout />
          </RoleRoute>
        }
      >
        <Route index element={<LenderDashboard />} />
      </Route>

      <Route
        path="/research"
        element={
          <RoleRoute allowedRoles={['research_analyst', 'farm_manager', 'farm_admin', 'farm_vet']}>
            <DashboardLayout />
          </RoleRoute>
        }
      >
        <Route index element={<ResearchDashboard lat={9.0765} lon={7.3986} locationName="Abuja Region" />} />
        <Route
          path="animals/:cowId"
          element={<ResearchCowPassport />}
        />
      </Route>

      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}
