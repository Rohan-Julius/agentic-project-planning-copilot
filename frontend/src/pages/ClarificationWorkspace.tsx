import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import type { ClarificationQuestion, Project } from '../types'

const STATUS_OPTIONS: ClarificationQuestion['status'][] = [
  'PENDING',
  'ANSWERED',
  'DEFERRED',
  'NOT_APPLICABLE',
]

export default function ClarificationWorkspace() {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()
  const [project, setProject] = useState<Project | null>(null)
  const [questions, setQuestions] = useState<ClarificationQuestion[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [approving, setApproving] = useState(false)

  function loadQuestions(id: string) {
    return api.get<ClarificationQuestion[]>(`/projects/${id}/clarifications`).then(setQuestions)
  }

  useEffect(() => {
    if (!projectId) return
    setLoading(true)
    Promise.all([api.get<Project>(`/projects/${projectId}`), loadQuestions(projectId)])
      .then(([p]) => setProject(p))
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false))
  }, [projectId])

  function updateQuestion(questionId: string, patch: Partial<ClarificationQuestion>) {
    setQuestions((prev) =>
      prev.map((q) => (q.question_id === questionId ? { ...q, ...patch } : q)),
    )
  }

  async function handleSaveAnswers(event: React.FormEvent) {
    event.preventDefault()
    if (!projectId) return
    setError(null)
    setSaving(true)
    try {
      await api.post(
        `/projects/${projectId}/clarifications/answers`,
        questions.map((q) => ({
          question_id: q.question_id,
          status: q.status,
          user_answer: q.user_answer,
          question: q.question,
        })),
      )
      await loadQuestions(projectId)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : (err as Error).message)
    } finally {
      setSaving(false)
    }
  }

  function handleApprove() {
    if (!projectId) return
    setError(null)
    setApproving(true)
    // Approving resumes the graph synchronously on the backend straight into Planning
    // (several sequential live LLM calls) — it can take minutes, so navigate to the Agent
    // Execution screen immediately rather than awaiting this response, the same reason
    // DocumentWorkspace's "Run requirement analysis" no longer awaits /workflow/start.
    api.post(`/projects/${projectId}/clarifications/approve`, {}).catch((err) => {
      console.error('clarifications/approve request failed', err)
    })
    navigate(`/projects/${projectId}/workflow`)
  }

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>{project?.name ?? 'Clarifications'}</h1>
          <p className="muted">
            Review, answer, defer, or edit clarification questions before planning begins.
          </p>
        </div>
        <Link className="back-link" to={`/projects/${projectId}/documents`}>
          ← Back to documents
        </Link>
      </header>

      {loading && <p>Loading…</p>}
      {error && <p className="error">{error}</p>}

      {!loading && !error && (
        <form className="form" onSubmit={handleSaveAnswers}>
          {questions.length === 0 && (
            <p className="muted">
              No clarification questions were raised — the requirement analysis found nothing
              ambiguous. Planning still waits for your explicit approval before it begins (§11);
              approve below to continue.
            </p>
          )}
          <ul className="clarification-list">
            {questions.map((q) => (
              <li key={q.question_id} className="panel clarification-row">
                <div className="clarification-meta">
                  <span className="clarification-category">{q.category}</span>
                  <span className="clarification-priority">{q.priority} priority</span>
                </div>
                <div className="field">
                  <label htmlFor={`question-${q.question_id}`}>Question</label>
                  <textarea
                    id={`question-${q.question_id}`}
                    rows={2}
                    value={q.question}
                    onChange={(e) => updateQuestion(q.question_id, { question: e.target.value })}
                  />
                </div>
                <p className="muted">Why asked: {q.reason_for_asking}</p>
                {q.source_reference && (
                  <p className="muted">
                    Source: {q.source_reference.document_name}
                    {q.source_reference.page_number ? `, p.${q.source_reference.page_number}` : ''}
                    {q.source_reference.section ? ` — ${q.source_reference.section}` : ''}
                  </p>
                )}
                <div className="field">
                  <label htmlFor={`status-${q.question_id}`}>Status</label>
                  <select
                    id={`status-${q.question_id}`}
                    value={q.status}
                    onChange={(e) =>
                      updateQuestion(q.question_id, {
                        status: e.target.value as ClarificationQuestion['status'],
                      })
                    }
                  >
                    {STATUS_OPTIONS.map((status) => (
                      <option key={status} value={status}>
                        {status}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="field">
                  <label htmlFor={`answer-${q.question_id}`}>Answer</label>
                  <textarea
                    id={`answer-${q.question_id}`}
                    rows={2}
                    value={q.user_answer ?? ''}
                    placeholder="Leave blank if deferred or not applicable"
                    onChange={(e) => updateQuestion(q.question_id, { user_answer: e.target.value })}
                  />
                </div>
              </li>
            ))}
          </ul>

          <div className="form-actions">
            {questions.length > 0 && (
              <button className="button" type="submit" disabled={saving}>
                {saving ? 'Saving…' : 'Save answers'}
              </button>
            )}
            <button className="button" type="button" disabled={approving} onClick={handleApprove}>
              {approving ? 'Approving…' : 'Approve clarifications'}
            </button>
          </div>
        </form>
      )}
    </div>
  )
}
