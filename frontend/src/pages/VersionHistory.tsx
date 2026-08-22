import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import type { Dependency, Epic, PlanVersionSummary, ProjectPlan, TechnicalTask, UserStory } from '../types'
import { diffById } from '../utils/versionDiff'

export default function VersionHistory() {
  const { projectId } = useParams<{ projectId: string }>()
  const [versions, setVersions] = useState<PlanVersionSummary[]>([])
  const [selectedA, setSelectedA] = useState<string>('')
  const [selectedB, setSelectedB] = useState<string>('')
  const [planA, setPlanA] = useState<ProjectPlan | null>(null)
  const [planB, setPlanB] = useState<ProjectPlan | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!projectId) return
    api
      .get<PlanVersionSummary[]>(`/projects/${projectId}/plan/versions`)
      .then((vs) => {
        setVersions(vs)
        if (vs.length >= 2) {
          setSelectedA(vs[1].version_id)
          setSelectedB(vs[0].version_id)
        } else if (vs.length === 1) {
          setSelectedA(vs[0].version_id)
          setSelectedB(vs[0].version_id)
        }
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : (err as Error).message))
      .finally(() => setLoading(false))
  }, [projectId])

  useEffect(() => {
    if (!projectId || !selectedA || !selectedB) return
    Promise.all([
      api.get<ProjectPlan>(`/projects/${projectId}/plan/versions/${selectedA}`),
      api.get<ProjectPlan>(`/projects/${projectId}/plan/versions/${selectedB}`),
    ])
      .then(([a, b]) => {
        setPlanA(a)
        setPlanB(b)
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : (err as Error).message))
  }, [projectId, selectedA, selectedB])

  function summarize<T>(label: string, previous: T[], next: T[], idKey: (item: T) => string) {
    const diff = diffById(previous, next, idKey)
    if (diff.added.length === 0 && diff.removed.length === 0 && diff.modified.length === 0) {
      return (
        <p key={label} className="muted">
          {label}: no changes ({diff.unchanged.length} unchanged)
        </p>
      )
    }
    return (
      <div key={label} className="panel">
        <h3>{label}</h3>
        {diff.added.length > 0 && <p>+{diff.added.length} added</p>}
        {diff.removed.length > 0 && <p>-{diff.removed.length} removed</p>}
        {diff.modified.length > 0 && <p>~{diff.modified.length} modified</p>}
      </div>
    )
  }

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>Plan version history</h1>
          <p className="muted">Compare any two versions of this project's plan.</p>
        </div>
        <Link className="back-link" to={`/projects/${projectId}/plan`}>
          Planning workspace →
        </Link>
      </header>

      {loading && <p>Loading…</p>}
      {error && <p className="error">{error}</p>}

      {!loading && !error && versions.length === 0 && <p>No plan versions yet.</p>}

      {versions.length > 0 && (
        <>
          <div className="panel">
            <label>
              Compare
              <select value={selectedA} onChange={(e) => setSelectedA(e.target.value)}>
                {versions.map((v) => (
                  <option key={v.version_id} value={v.version_id}>
                    v{v.version_number} ({v.generated_at})
                  </option>
                ))}
              </select>
            </label>
            <label>
              with
              <select value={selectedB} onChange={(e) => setSelectedB(e.target.value)}>
                {versions.map((v) => (
                  <option key={v.version_id} value={v.version_id}>
                    v{v.version_number} ({v.generated_at}){v.is_current ? ' — current' : ''}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {planA && planB && (
            <>
              {summarize('Epics', planA.epics, planB.epics, (e: Epic) => e.epic_id)}
              {summarize('Stories', planA.stories, planB.stories, (s: UserStory) => s.story_id)}
              {summarize(
                'Technical tasks', planA.technical_tasks, planB.technical_tasks,
                (t: TechnicalTask) => t.task_id,
              )}
              {summarize(
                'Dependencies', planA.raid.dependencies, planB.raid.dependencies,
                (d: Dependency) => d.dependency_id,
              )}
            </>
          )}
        </>
      )}
    </div>
  )
}
