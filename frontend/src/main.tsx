import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import '@fontsource/ibm-plex-sans/400.css'
import '@fontsource/ibm-plex-sans/500.css'
import '@fontsource/ibm-plex-sans/700.css'
import '@fontsource/ibm-plex-serif/400.css'
import '@fontsource/ibm-plex-serif/400-italic.css'
import '@fontsource/ibm-plex-mono/400.css'
import '@fontsource/ibm-plex-mono/500.css'
import './index.css'
import AppShell from './components/AppShell'
import Dashboard from './pages/Dashboard'
import About from './pages/About'
import Standards from './pages/Standards'
import CreateProject from './pages/CreateProject'
import DocumentWorkspace from './pages/DocumentWorkspace'
import ClarificationWorkspace from './pages/ClarificationWorkspace'
import PlanningWorkspace from './pages/PlanningWorkspace'
import VersionHistory from './pages/VersionHistory'
import ReviewerScreen from './pages/ReviewerScreen'
import AgentExecutionScreen from './pages/AgentExecutionScreen'
import ExportScreen from './pages/ExportScreen'

const router = createBrowserRouter([
  {
    element: <AppShell />,
    children: [
      { path: '/', element: <Dashboard /> },
      { path: '/about', element: <About /> },
      { path: '/standards', element: <Standards /> },
      { path: '/projects/new', element: <CreateProject /> },
      { path: '/projects/:projectId/documents', element: <DocumentWorkspace /> },
      { path: '/projects/:projectId/clarifications', element: <ClarificationWorkspace /> },
      { path: '/projects/:projectId/plan', element: <PlanningWorkspace /> },
      { path: '/projects/:projectId/plan/versions', element: <VersionHistory /> },
      { path: '/projects/:projectId/review', element: <ReviewerScreen /> },
      { path: '/projects/:projectId/workflow', element: <AgentExecutionScreen /> },
      { path: '/projects/:projectId/export', element: <ExportScreen /> },
    ],
  },
])

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>,
)
