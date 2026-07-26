import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, apiBaseUrl, ApiError } from '../api/client'
import type { Project, WorkflowRun } from '../types'

export default function ExportScreen() {
  const { projectId } = useParams<{ projectId: string }>()
  const [project, setProject] = useState<Project | null>(null)
  const [run, setRun] = useState<WorkflowRun | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!projectId) return
    setLoading(true)
    Promise.all([
      api.get<Project>(`/projects/${projectId}`),
      api.get<WorkflowRun>(`/projects/${projectId}/workflow/status`).catch(() => null),
    ])
      .then(([p, r]) => {
        setProject(p)
        setRun(r)
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : (err as Error).message))
      .finally(() => setLoading(false))
  }, [projectId])

  const approved = run?.final_approved ?? false

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>{project?.name ?? 'Export'}</h1>
          <p className="muted">
            {approved
              ? 'Plan approved — exports are labeled APPROVED.'
              : 'Plan not yet approved — exports are labeled DRAFT_PENDING_APPROVAL until you approve it on the reviewer screen.'}
          </p>
        </div>
        <Link className="back-link" to={`/projects/${projectId}/review`}>
          ← Back to review
        </Link>
      </header>

      {loading && <p>Loading…</p>}
      {error && <p className="error">{error}</p>}

      {!loading && (
        <section className="panel">
          <h2>Download</h2>
          <div className="form-actions">
            <a className="button" href={`${apiBaseUrl}/projects/${projectId}/export/json`}>
              JSON
            </a>
            <a className="button" href={`${apiBaseUrl}/projects/${projectId}/export/markdown`}>
              Markdown
            </a>
            <a className="button" href={`${apiBaseUrl}/projects/${projectId}/export/jira-csv`}>
              Jira CSV
            </a>
            <a className="button" href={`${apiBaseUrl}/projects/${projectId}/export/zip`}>
              ZIP (all formats + reviewer report)
            </a>
          </div>
        </section>
      )}
    </div>
  )
}
