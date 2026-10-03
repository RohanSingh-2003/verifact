import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from './components/layout/Layout'
import { DetectPage } from './pages/DetectPage'
import { HistoryPage } from './pages/HistoryPage'
import { MetaQAPage } from './pages/MetaQAPage'
import { SettingsPage } from './pages/SettingsPage'
import { WebAnalysisPage } from './pages/WebAnalysisPage'
import { ThemeProvider } from './theme/ThemeProvider'

export default function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <Layout>
          <Routes>
            <Route path="/" element={<DetectPage />} />
            <Route path="/history" element={<HistoryPage />} />
            <Route path="/metaqa" element={<MetaQAPage />} />
            <Route path="/web-analysis" element={<WebAnalysisPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Layout>
      </BrowserRouter>
    </ThemeProvider>
  )
}
