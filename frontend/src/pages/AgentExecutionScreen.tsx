import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import type { Project, WorkflowEvent, WorkflowRun } from '../types'

// Keyed by `WorkflowRun.pending_gate` (app/api/workflow.py `/workflow/status`, backed by
// engine.get_pending_gate_stage reading the interrupt's own `{"stage": ...}` payload) — a
// deterministic signal, not the Supervisor's advisory `RECOMMEND_*` recommendation. That
// recommendation is a separate LLM call that proved unreliable at picking the right action
// for more than one state transition (found live, twice) and is kept in the execution log
// purely for audit/debugging, never for navigation.
// final_gate routes to /plan first, not straight to /review — the intended flow is
// Execution screen → Plan (read the full generated plan) → Reviewer findings → Approve.
// PlanningWorkspace's own header already links forward to /review ("Reviewer findings →"),
// so this just makes that the entry point instead of skipping straight to approval.
const GATE_LINKS: Record<string, { label: string; to: string }> = {
  clarification_gate: { label: 'Answer clarification questions', to: 'clarifications' },
  final_gate: { label: 'Review the plan and approve', to: 'plan' },
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
  // WAITING_FOR_HUMAN_INPUT for that whole stretch. What's actually true mid-run is only
  // whichever event was logged *last overall* — if it's IN_PROGRESS, the graph is still
  // working regardless of what the stale `status` says.
  const latestEvent = events[events.length - 1]

  const gateLink = run?.pending_gate ? GATE_LINKS[run.pending_gate] : undefined

  // `run.status` is stale mid-run (see comment above) — while the latest event is still
  // IN_PROGRESS, the graph is actively executing regardless of what `run.status` says, so
  // show that instead of the misleading gate status (e.g. "WAITING_FOR_HUMAN_INPUT" while
  // Planning is genuinely mid-generation).
  const displayStatus =
    run && latestEvent?.status === 'IN_PROGRESS'
      ? `RUNNING — ${latestEvent.agent}: ${latestEvent.action}`
      : run?.status

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
            <h2>Status: {displayStatus}</h2>
            <p className="muted">
              Run {run.workflow_run_id} · revision count {run.revision_count} · final approved:{' '}
              {String(run.final_approved)}
            </p>
            {gateLink && (
              <Link className="button" to={`/projects/${projectId}/${gateLink.to}`}>
                {gateLink.label} →
              </Link>
            )}
            {run.status === 'COMPLETED' && (
              <Link className="button" to={`/projects/${projectId}/export`}>
                View export →
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
