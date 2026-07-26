import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import './index.css'
import Dashboard from './pages/Dashboard'
import CreateProject from './pages/CreateProject'
import DocumentWorkspace from './pages/DocumentWorkspace'
import ClarificationWorkspace from './pages/ClarificationWorkspace'
import PlanningWorkspace from './pages/PlanningWorkspace'
import ReviewerScreen from './pages/ReviewerScreen'
import AgentExecutionScreen from './pages/AgentExecutionScreen'
import ExportScreen from './pages/ExportScreen'

const router = createBrowserRouter([
  { path: '/', element: <Dashboard /> },
  { path: '/projects/new', element: <CreateProject /> },
  { path: '/projects/:projectId/documents', element: <DocumentWorkspace /> },
  { path: '/projects/:projectId/clarifications', element: <ClarificationWorkspace /> },
  { path: '/projects/:projectId/plan', element: <PlanningWorkspace /> },
  { path: '/projects/:projectId/review', element: <ReviewerScreen /> },
  { path: '/projects/:projectId/workflow', element: <AgentExecutionScreen /> },
  { path: '/projects/:projectId/export', element: <ExportScreen /> },
])

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>,
)
