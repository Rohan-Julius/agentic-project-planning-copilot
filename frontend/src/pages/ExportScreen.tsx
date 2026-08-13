import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, apiBaseUrl, ApiError } from '../api/client'
import ExportPreviewModal, { type ExportPreviewTarget } from '../components/ExportPreviewModal'
import FileFormatCard from '../components/FileFormatCard'
import type { Project, WorkflowRun } from '../types'

export default function ExportScreen() {
  const { projectId } = useParams<{ projectId: string }>()
  const [project, setProject] = useState<Project | null>(null)
  const [run, setRun] = useState<WorkflowRun | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [previewTarget, setPreviewTarget] = useState<ExportPreviewTarget | null>(null)

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
              ? 'Plan approved. Exports are labeled APPROVED.'
              : 'Plan not yet approved. Exports are labeled DRAFT_PENDING_APPROVAL until you approve it on the reviewer screen.'}
          </p>
        </div>
        <Link className="back-link" to={`/projects/${projectId}/review`}>
          ← Back to review
        </Link>
      </header>

      {loading && <p>Loading…</p>}
      {error && <p className="error">{error}</p>}

      {!loading && projectId && (
        <section className="panel">
          <h2>Download</h2>
          <p className="muted">Click a format to preview it before downloading.</p>
          <div className="file-format-row">
            <FileFormatCard
              format="json"
              label="JSON"
              onClick={() =>
                setPreviewTarget({
                  format: 'json',
                  label: 'JSON',
                  path: `/projects/${projectId}/export/json`,
                  filename: `${projectId}-plan.json`,
                })
              }
            />
            <FileFormatCard
              format="markdown"
              label="Markdown"
              onClick={() =>
                setPreviewTarget({
                  format: 'markdown',
                  label: 'Markdown',
                  path: `/projects/${projectId}/export/markdown`,
                  filename: `${projectId}-plan.md`,
                })
              }
            />
            <FileFormatCard
              format="csv"
              label="Jira CSV"
              onClick={() =>
                setPreviewTarget({
                  format: 'csv',
                  label: 'Jira CSV',
                  path: `/projects/${projectId}/export/jira-csv`,
                  filename: `${projectId}-jira.csv`,
                })
              }
            />
            {/* Zip is a binary bundle (json + markdown + jira csv + reviewer report) — nothing
                sensible to preview as text, so this one stays a direct download link. */}
            <FileFormatCard
              format="zip"
              label="ZIP (all formats + reviewer report)"
              href={`${apiBaseUrl}/projects/${projectId}/export/zip`}
            />
          </div>
        </section>
      )}

      <ExportPreviewModal target={previewTarget} onClose={() => setPreviewTarget(null)} />
    </div>
  )
}
