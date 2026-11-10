import { Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider } from './auth/AuthProvider'
import RequireAuth from './auth/RequireAuth'
import RequireAdmin from './auth/RequireAdmin'
import AppShell from './components/AppShell'
import Login from './pages/Login'
import Leads from './pages/Leads'
import Listings from './pages/Listings'
import Team from './pages/Team'
import ComingSoon from './pages/ComingSoon'

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route element={<RequireAuth />}>
          <Route element={<AppShell />}>
            <Route path="/leads/:contactId?" element={<Leads />} />
            <Route path="/listings" element={<Listings />} />
            <Route element={<RequireAdmin />}>
              <Route path="/team" element={<Team />} />
            </Route>
            <Route path="/reports" element={<ComingSoon title="Visits & reports" note="Phase 2. Visits and reports are not built yet." />} />
            <Route path="/" element={<Navigate to="/leads" replace />} />
          </Route>
        </Route>
        <Route path="*" element={<Navigate to="/leads" replace />} />
      </Routes>
    </AuthProvider>
  )
}