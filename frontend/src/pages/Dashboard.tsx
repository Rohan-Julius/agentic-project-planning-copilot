import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import type { Project } from '../types'

export default function Dashboard() {
  const [projects, setProjects] = useState<Project[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api
      .get<Project[]>('/projects')
      .then(setProjects)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="page">
      <header className="page-header">
        <h1>Projects</h1>
        <Link className="button" to="/projects/new">
          + New project
        </Link>
      </header>

      {loading && <p>Loading…</p>}
      {error && <p className="error">Failed to load projects: {error}</p>}
      {!loading && !error && projects.length === 0 && (
        <p>No projects yet. Create one to get started.</p>
      )}

      <ul className="project-list">
        {projects.map((project) => (
          <li key={project.project_id} className="project-card">
            <Link to={`/projects/${project.project_id}/documents`}>
              <h2>{project.name}</h2>
            </Link>
            <p>{project.description || 'No description'}</p>
            <div className="project-meta">
              <span>{project.methodology}</span>
              <span>{project.status}</span>
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}
