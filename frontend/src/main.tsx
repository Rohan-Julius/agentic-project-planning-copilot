import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import './index.css'
import Dashboard from './pages/Dashboard'
import CreateProject from './pages/CreateProject'
import DocumentWorkspace from './pages/DocumentWorkspace'

const router = createBrowserRouter([
  { path: '/', element: <Dashboard /> },
  { path: '/projects/new', element: <CreateProject /> },
  { path: '/projects/:projectId/documents', element: <DocumentWorkspace /> },
])

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>,
)
