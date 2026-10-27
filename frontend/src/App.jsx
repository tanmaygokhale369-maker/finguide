import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Layout } from './components/layout/Layout'
import { Dashboard } from './pages/Dashboard'
import { FinancialProfile } from './pages/FinancialProfile'
import { Transactions } from './pages/Transactions'
import { Chat } from './pages/Chat'
import { Recommendations } from './pages/Recommendations'
import { Investments } from './pages/Investments'
import { Settings } from './pages/Settings'
import { NotFound } from './pages/NotFound'
import { Auth } from './pages/Auth'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="auth" element={<Auth />} />
          <Route index element={<Dashboard />} />
          <Route path="profile" element={<FinancialProfile />} />
          <Route path="transactions" element={<Transactions />} />
          <Route path="chat" element={<Chat />} />
          <Route path="recommendations" element={<Recommendations />} />
          <Route path="investments" element={<Investments />} />
          <Route path="settings" element={<Settings />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
