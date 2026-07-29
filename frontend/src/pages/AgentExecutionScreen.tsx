import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import type { Project, WorkflowEvent, WorkflowRun } from '../types'

// Keyed by the Supervisor's own `RECOMMEND_<SupervisorAction>` event action (app/workflow/graph.py
// supervisor_node), not by gate stage: a real interrupt never logs an event at the gate's own
// stage (clarification_gate_node/final_gate_node log only *after* resuming, since interrupt()
// runs first), so the last-event-stage would never match while genuinely waiting.
const SUPERVISOR_RECOMMENDATION_LINKS: Record<string, { label: string; to: string }> = {
  RECOMMEND_WAIT_FOR_CLARIFICATIONS: { label: 'Answer clarification questions', to: 'clarifications' },
  RECOMMEND_WAIT_FOR_FINAL_APPROVAL: { label: 'Review the plan and approve', to: 'review' },
}

export default function AgentExecutionScreen() {
  const { projectId } = useParams<{ projectId: string }>()
  const [project, setProject] = useState<Project | null>(null)
  const [run, setRun] = useState<WorkflowRun | null>(null)
  const [events, setEvents] = useState<WorkflowEvent[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!projectId) return
    api
      .get<Project>(`/projects/${projectId}`)
      .then(setProject)
      .catch(() => undefined)

    let cancelled = false
    function poll() {
      Promise.all([
        api.get<WorkflowRun>(`/projects/${projectId}/workflow/status`),
        api.get<WorkflowEvent[]>(`/projects/${projectId}/workflow/events`),
      ])
        .then(([r, e]) => {
          if (cancelled) return
          setRun(r)
          setEvents(e)
          setError(null)
        })
        .catch((err) => {
          if (!cancelled) setError(err instanceof ApiError ? err.message : (err as Error).message)
        })
    }
    poll()
    const interval = setInterval(poll, 3000)
    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [projectId])

  // WorkflowRun.status only updates when a graph invocation *returns* — after a human
  // approves a gate, the backend resumes and keeps running (Planning, Reviewer, ...)
  // without touching `status` until it returns again, so `status` stays stuck at
  // WAITING_FOR_HUMAN_INPUT for that whole stretch. Same issue for `lastSupervisorRecommendation`
  // (the Supervisor isn't re-invoked between the gate and the next node it routes straight
  // to). Neither is trustworthy on its own. What's actually true is only whichever event was
  // logged *last overall* — if that's still the gate recommendation, nothing has happened
  // since and we're genuinely waiting; the moment any newer event lands, the gate has been
  // passed, regardless of what the stale `status`/`lastSupervisorRecommendation` still say.
  const latestEvent = events[events.length - 1]
  const gateLink =
    latestEvent?.agent === 'Supervisor' && latestEvent.action.startsWith('RECOMMEND_')
      ? SUPERVISOR_RECOMMENDATION_LINKS[latestEvent.action]
      : undefined

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>{project?.name ?? 'Agent execution'}</h1>
          <p className="muted">Safe execution summary — never the model's hidden reasoning.</p>
        </div>
        <Link className="back-link" to={`/projects/${projectId}/documents`}>
          ← Back to documents
        </Link>
      </header>

      {error && <p className="error">{error}</p>}
      {!run && !error && <p>No workflow run yet. Start requirement analysis from the document workspace.</p>}

      {run && (
        <>
          <section className="panel">
            <h2>Status: {run.status}</h2>
            <p className="muted">
              Run {run.workflow_run_id} · revision count {run.revision_count} · final approved:{' '}
              {String(run.final_approved)}
            </p>
            {gateLink && (
              <Link className="button" to={`/projects/${projectId}/${gateLink.to}`}>
                {gateLink.label} →
              </Link>
            )}
          </section>

          <section className="panel">
            <h2>Execution log ({events.length})</h2>
            <ul className="event-list">
              {events.map((event, i) => (
                <li key={i} className={`event-row${event.status === 'ERROR' ? ' event-row-error' : ''}`}>
                  <span className="event-agent">{event.agent}</span>
                  <span className="event-action">{event.action}</span>
                  <span className="muted">
                    {event.stage} · {event.status}
                    {event.tool ? ` · tool: ${event.tool}` : ''}
                  </span>
                  {event.error && <p className="error">{event.error}</p>}
                </li>
              ))}
            </ul>
          </section>
        </>
      )}
    </div>
  )
}
