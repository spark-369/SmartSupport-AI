import { BrowserRouter, Route, Routes } from 'react-router-dom'

import { AppShell } from '@/components/layout/AppShell'
import { ProtectedRoute } from '@/components/layout/ProtectedRoute'
import DashboardPage from '@/pages/DashboardPage'
import LoginPage from '@/pages/LoginPage'
import RegisterPage from '@/pages/RegisterPage'
import ProductDetailPage from '@/pages/ProductDetailPage'
import ChatPage from '@/pages/ChatPage'
import SettingsPage from '@/pages/SettingsPage'
import SearchPage from '@/pages/SearchPage'
import InsightsPage from '@/pages/InsightsPage'
import TicketsPage from '@/pages/TicketsPage'
import NotFoundPage from '@/pages/NotFoundPage'

export default function App() {
  return (
    <BrowserRouter
      future={{
        v7_startTransition: true,
        v7_relativeSplatPath: true,
      }}
    >
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />

        <Route element={<ProtectedRoute />}>
          <Route element={<AppShell />}>
            <Route index element={<DashboardPage />} />
            <Route path="/products/:productId" element={<ProductDetailPage />} />
            <Route path="/chat" element={<ChatPage />} />
            <Route path="/search" element={<SearchPage />} />
            <Route path="/insights" element={<InsightsPage />} />
            <Route path="/tickets" element={<TicketsPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Route>
        </Route>

        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </BrowserRouter>
  )
}
