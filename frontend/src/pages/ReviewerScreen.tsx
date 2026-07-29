import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import type { Project, ReviewerIssue, ReviewerReport } from '../types'

function IssueList({ title, issues }: { title: string; issues: ReviewerIssue[] }) {
  if (issues.length === 0) return null
  return (
    <div className="panel">
      <h2>
        {title} ({issues.length})
      </h2>
      <ul>
        {issues.map((issue, i) => (
          <li key={i}>
            <strong>{issue.artifact_id}</strong> — {issue.issue_type}: {issue.description}
            <p className="muted">Recommended: {issue.recommended_action}</p>
          </li>
        ))}
      </ul>
    </div>
  )
}

export default function ReviewerScreen() {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()
  const [project, setProject] = useState<Project | null>(null)
  const [report, setReport] = useState<ReviewerReport | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [approving, setApproving] = useState(false)

  useEffect(() => {
    if (!projectId) return
    setLoading(true)
    Promise.all([
      api.get<Project>(`/projects/${projectId}`),
      api.get<ReviewerReport>(`/projects/${projectId}/review`),
    ])
      .then(([p, r]) => {
        setProject(p)
        setReport(r)
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : (err as Error).message))
      .finally(() => setLoading(false))
  }, [projectId])

  function handleApprove() {
    if (!projectId) return
    setError(null)
    setApproving(true)
    // Approving resumes the graph synchronously on the backend — navigate to the Agent
    // Execution screen immediately rather than awaiting this response (same reasoning as
    // DocumentWorkspace's workflow/start and ClarificationWorkspace's clarifications/approve).
    api.post(`/projects/${projectId}/plan/approve`, {}).catch((err) => {
      console.error('plan/approve request failed', err)
    })
    navigate(`/projects/${projectId}/workflow`)
  }

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>{project?.name ?? 'Reviewer findings'}</h1>
          <p className="muted">Independent quality-control findings on the generated plan.</p>
        </div>
        <Link className="back-link" to={`/projects/${projectId}/plan`}>
          ← Back to plan
        </Link>
      </header>

      {loading && <p>Loading…</p>}
      {error && <p className="error">{error}</p>}
      {!loading && !error && !report && <p>No review has run yet.</p>}

      {report && (
        <>
          <section className="panel">
            <h2>Decision: {report.decision}</h2>
            {report.warnings.length > 0 && (
              <>
                <p className="muted">Warnings (accepted by proceeding to approval):</p>
                <ul>
                  {report.warnings.map((w, i) => (
                    <li key={i}>{w}</li>
                  ))}
                </ul>
              </>
            )}
            {report.missing_requirements.length > 0 && (
              <>
                <p className="muted">Missing requirements:</p>
                <ul>
                  {report.missing_requirements.map((m, i) => (
                    <li key={i}>{m}</li>
                  ))}
                </ul>
              </>
            )}
          </section>

          <IssueList title="Unsupported claims" issues={report.unsupported_claims} />
          <IssueList title="Duplicate stories" issues={report.duplicate_stories} />
          <IssueList title="Missing acceptance criteria" issues={report.missing_acceptance_criteria} />
          <IssueList title="Weak acceptance criteria" issues={report.weak_acceptance_criteria} />
          <IssueList title="Traceability gaps" issues={report.traceability_gaps} />
          <IssueList title="Dependency issues" issues={report.dependency_issues} />
          <IssueList title="Revision instructions" issues={report.revision_instructions} />

          <section className="panel">
            <h2>Final approval</h2>
            <p className="muted">
              Approving is a human decision — the system never auto-approves a plan, even when
              the reviewer decision is PASS.
            </p>
            <div className="form-actions">
              <button className="button" type="button" disabled={approving} onClick={handleApprove}>
                {approving ? 'Approving…' : 'Approve plan'}
              </button>
            </div>
          </section>
        </>
      )}
    </div>
  )
}
