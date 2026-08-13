import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import HoverButtonContent from '../components/HoverButtonContent'
import type { Project, WorkflowEvent, WorkflowRun } from '../types'
import {
  PIPELINE_STAGES,
  derivePipelineStatus,
  stageIndex,
  type PipelineStatus,
} from '../utils/pipeline'

export default function Dashboard() {
  const [projects, setProjects] = useState<Project[]>([])
  const [runs, setRuns] = useState<Record<string, WorkflowRun | null>>({})
  // Latest-event timestamp per project, only ever populated for projects whose run is
  // RUNNING — that's the only state derivePipelineStatus needs it for (see pipeline.ts:
  // WAITING_FOR_HUMAN_INPUT is an intentional pause, not something staleness applies to).
  const [latestEventAt, setLatestEventAt] = useState<Record<string, string | null>>({})
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false

    api
      .get<Project[]>('/projects')
      .then(async (loaded) => {
        if (cancelled) return
        setProjects(loaded)
        setLoading(false)

        // One-shot fetch of each project's latest workflow status so the
        // tracker reflects real pipeline position instead of inventing one.
        // /workflow/status 404s for a project with no run yet — that's not
        // an error, it just means "still at Documents".
        const entries = await Promise.all(
          loaded.map(async (project) => {
            try {
              const run = await api.get<WorkflowRun>(
                `/projects/${project.project_id}/workflow/status`,
              )
              return [project.project_id, run] as const
            } catch (err) {
              if (err instanceof ApiError && err.status === 404) {
                return [project.project_id, null] as const
              }
              throw err
            }
          }),
        )
        if (!cancelled) setRuns(Object.fromEntries(entries))

        // A RUNNING status alone can't tell "actively working" apart from "the process
        // that was running this died" (see runFreshness.ts) — only fetched for the
        // projects where that distinction actually matters, not every project.
        const runningProjectIds = entries
          .filter(([, run]) => run?.status === 'RUNNING')
          .map(([projectId]) => projectId)
        const freshnessEntries = await Promise.all(
          runningProjectIds.map(async (projectId) => {
            const events = await api
              .get<WorkflowEvent[]>(`/projects/${projectId}/workflow/events`)
              .catch(() => [])
            const latest = events[events.length - 1]
            return [projectId, latest?.timestamp ?? null] as const
          }),
        )
        if (!cancelled) setLatestEventAt(Object.fromEntries(freshnessEntries))
      })
      .catch((err: Error) => {
        if (!cancelled) {
          setError(err.message)
          setLoading(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, [])

  return (
    <div className="page page-wide">
      <header className="page-header">
        <h1 className="dashboard-title">Projects</h1>
        <Link className="button-hover" to="/projects/new">
          <HoverButtonContent>+ New project</HoverButtonContent>
        </Link>
      </header>

      {loading && <p>Loading…</p>}
      {error && <p className="error">Failed to load projects: {error}</p>}
      {!loading && !error && projects.length === 0 && (
        <p>No projects yet. Create one to get started.</p>
      )}

      <ul className="ledger">
        {projects.map((project) => (
          <li key={project.project_id} className="ledger-row">
            <Link to={`/projects/${project.project_id}/documents`} className="ledger-link">
              <div className="ledger-heading">
                <h2>{project.name}</h2>
                <span className="ledger-methodology">{project.methodology}</span>
              </div>
              <p className="ledger-desc muted">{project.description || 'No description'}</p>
              <PipelineTracker
                status={derivePipelineStatus(
                  runs[project.project_id] ?? null,
                  latestEventAt[project.project_id] ?? null,
                  Date.now(),
                )}
              />
            </Link>
          </li>
        ))}
      </ul>
    </div>
  )
}

function PipelineTracker({ status }: { status: PipelineStatus }) {
  if (status.kind === 'error') {
    return <p className="pipeline-flag pipeline-flag-error">Workflow stopped with an error</p>
  }
  if (status.kind === 'stalled') {
    // Distinct from "working" on purpose — WorkflowRun.status alone can't tell "actively
    // executing" apart from "the process running this died and nothing resumed it" (see
    // pipeline.ts). No pulsing dot here either: that motion should mean something is
    // genuinely happening, not linger on a run nothing is actually driving anymore.
    return <p className="pipeline-flag pipeline-flag-stalled">Possibly stalled: no recent activity</p>
  }
  if (status.kind === 'working') {
    return <p className="pipeline-flag pipeline-flag-working">Agents working…</p>
  }

  const current = stageIndex(status.stage)

  return (
    <ol className="pipeline-tracker">
      {PIPELINE_STAGES.map(({ stage, label }, i) => (
        <li
          key={stage}
          className={`pipeline-stage${i < current ? ' is-done' : ''}${
            i === current ? ' is-current' : ''
          }`}
        >
          <span className="pipeline-dot" aria-hidden="true" />
          <span className="pipeline-label">{label}</span>
        </li>
      ))}
    </ol>
  )
}
