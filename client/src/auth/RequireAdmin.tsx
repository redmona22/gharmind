import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from './useAuth'

export default function RequireAdmin() {
  const { user } = useAuth()
  if (user && user.role !== 'admin' && user.role !== 'owner') {
    return <Navigate to="/leads" replace />
  }
  return <Outlet />
}