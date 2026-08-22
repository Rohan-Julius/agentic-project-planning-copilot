import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import HoverButtonContent from '../components/HoverButtonContent'
import type {
  Classification,
  Project,
  ProjectPlan,
  Requirement,
  RequirementImpact,
  SourceReference,
} from '../types'

function Badge({ classification }: { classification: Classification }) {
  return (
    <span className={`badge badge-${classification.toLowerCase()}`}>
      {classification.replace('_', ' ')}
    </span>
  )
}

function Citations({ refs }: { refs: SourceReference[] }) {
  if (refs.length === 0) return null
  return (
    <p className="muted">
      Sources:{' '}
      {refs
        .map(
          (r) =>
            `${r.document_name}${r.page_number ? ` p.${r.page_number}` : ''}${
              r.section ? `, ${r.section}` : ''
            }`,
        )
        .join('; ')}
    </p>
  )
}

function ImpactPanel({ impact }: { impact: RequirementImpact }) {
  const hasAnyImpact =
    impact.epics.length > 0 ||
    impact.stories.length > 0 ||
    impact.technical_tasks.length > 0 ||
    impact.dependencies.length > 0
  if (!hasAnyImpact) {
    return <p className="muted">Nothing traces back to this requirement yet.</p>
  }
  return (
    <div className="artifact-card">
      {impact.epics.length > 0 && (
        <p>Epics: {impact.epics.map((e) => `${e.epic_id} (${e.title})`).join(', ')}</p>
      )}
      {impact.stories.length > 0 && (
        <p>Stories: {impact.stories.map((s) => `${s.story_id} (${s.title})`).join(', ')}</p>
      )}
      {impact.technical_tasks.length > 0 && (
        <p>Tasks: {impact.technical_tasks.map((t) => t.task_id).join(', ')}</p>
      )}
      {impact.dependencies.length > 0 && (
        <p>Dependencies: {impact.dependencies.map((d) => d.dependency_id).join(', ')}</p>
      )}
    </div>
  )
}

export default function PlanningWorkspace() {
  const { projectId } = useParams<{ projectId: string }>()
  const [project, setProject] = useState<Project | null>(null)
  const [plan, setPlan] = useState<ProjectPlan | null>(null)
  const [requirements, setRequirements] = useState<Requirement[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [regeneratingSprintPlan, setRegeneratingSprintPlan] = useState(false)
  const [regeneratingTasksRaid, setRegeneratingTasksRaid] = useState(false)
  const [impactByRequirementId, setImpactByRequirementId] = useState<
    Record<string, RequirementImpact | undefined>
  >({})
  const [expandedImpactIds, setExpandedImpactIds] = useState<Record<string, boolean>>({})
  const [impactLoading, setImpactLoading] = useState<Record<string, boolean>>({})

  useEffect(() => {
    if (!projectId) return
    setLoading(true)
    Promise.all([
      api.get<Project>(`/projects/${projectId}`),
      api.get<ProjectPlan>(`/projects/${projectId}/plan`),
      api.get<Requirement[]>(`/projects/${projectId}/requirements`),
    ])
      .then(([p, pl, reqs]) => {
        setProject(p)
        setPlan(pl)
        setRequirements(reqs)
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : (err as Error).message))
      .finally(() => setLoading(false))
  }, [projectId])

  function handleRegenerateSprintPlan() {
    if (!projectId) return
    setRegeneratingSprintPlan(true)
    api
      .post<ProjectPlan>(`/projects/${projectId}/plan/regenerate/sprint-plan`, {})
      .then(setPlan)
      .catch((err) => setError(err instanceof ApiError ? err.message : (err as Error).message))
      .finally(() => setRegeneratingSprintPlan(false))
  }

  function handleRegenerateTasksRaid() {
    if (!projectId) return
    setRegeneratingTasksRaid(true)
    api
      .post<ProjectPlan>(`/projects/${projectId}/plan/regenerate/tasks-deps-raid`, {})
      .then(setPlan)
      .catch((err) => setError(err instanceof ApiError ? err.message : (err as Error).message))
      .finally(() => setRegeneratingTasksRaid(false))
  }

  function handleToggleImpact(requirementId: string) {
    setExpandedImpactIds((prev) => ({ ...prev, [requirementId]: !prev[requirementId] }))
    if (!projectId || impactByRequirementId[requirementId]) return
    setImpactLoading((prev) => ({ ...prev, [requirementId]: true }))
    api
      .get<RequirementImpact>(`/projects/${projectId}/requirements/${requirementId}/impact`)
      .then((impact) => setImpactByRequirementId((prev) => ({ ...prev, [requirementId]: impact })))
      .catch((err) => setError(err instanceof ApiError ? err.message : (err as Error).message))
      .finally(() => setImpactLoading((prev) => ({ ...prev, [requirementId]: false })))
  }

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>{project?.name ?? 'Plan'}</h1>
          <p className="muted">
            Generated epics, stories, tasks, RAID log, and sprint plan. Review before approval.
          </p>
        </div>
        <div>
          <Link className="back-link" to={`/projects/${projectId}/plan/versions`}>
            Version history →
          </Link>
          <Link className="back-link" to={`/projects/${projectId}/review`}>
            Reviewer findings →
          </Link>
        </div>
      </header>

      {loading && <p>Loading…</p>}
      {error && <p className="error">{error}</p>}
      {!loading && !error && !plan && (
        <p>No plan generated yet. Run the workflow from the document workspace first.</p>
      )}

      {plan && (
        <>
          <section className="panel">
            <h2>Summary</h2>
            <p>{plan.summary.business_problem}</p>
            <p>{plan.summary.proposed_solution}</p>
          </section>

          <section className="panel">
            <h2>Scope</h2>
            <p className="muted">In scope</p>
            <ul>
              {plan.scope.in_scope.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ul>
            <p className="muted">Out of scope</p>
            <ul>
              {plan.scope.out_of_scope.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ul>
          </section>

          <section className="panel">
            <h2>Requirements ({requirements.length})</h2>
            {requirements.length === 0 ? (
              <p className="muted">No requirements extracted.</p>
            ) : (
              requirements.map((req) => (
                <div key={req.requirement_id} className="artifact-card">
                  <div className="artifact-header">
                    <strong>
                      {req.requirement_id}: {req.title}
                    </strong>
                    <Badge classification={req.classification} />
                  </div>
                  <p>{req.description}</p>
                  <p className="muted">
                    Category: {req.category} · Confidence: {req.confidence.toFixed(2)}
                  </p>
                  <Citations refs={req.source_references} />
                  <button
                    className="button-hover"
                    type="button"
                    onClick={() => handleToggleImpact(req.requirement_id)}
                  >
                    <HoverButtonContent>
                      {impactLoading[req.requirement_id]
                        ? 'Loading…'
                        : expandedImpactIds[req.requirement_id]
                          ? 'Hide impact'
                          : 'Show impact'}
                    </HoverButtonContent>
                  </button>
                  {expandedImpactIds[req.requirement_id] &&
                    impactByRequirementId[req.requirement_id] && (
                      <ImpactPanel impact={impactByRequirementId[req.requirement_id]!} />
                    )}
                </div>
              ))
            )}
          </section>

          <section className="panel">
            <h2>Epics ({plan.epics.length})</h2>
            {plan.epics.map((epic) => (
              <div key={epic.epic_id} className="artifact-card">
                <div className="artifact-header">
                  <strong>
                    {epic.epic_id}: {epic.title}
                  </strong>
                  <Badge classification={epic.classification} />
                </div>
                <p>{epic.objective}</p>
                <p className="muted">
                  Priority: {epic.priority} · Business value: {epic.business_value}
                </p>
                <Citations refs={epic.source_references} />
              </div>
            ))}
          </section>

          <section className="panel">
            <h2>User Stories ({plan.stories.length})</h2>
            {plan.stories.map((story) => (
              <div key={story.story_id} className="artifact-card">
                <div className="artifact-header">
                  <strong>
                    {story.story_id}: {story.title}
                  </strong>
                  <Badge classification={story.classification} />
                </div>
                <p>
                  As a {story.persona}, I want {story.story_statement}, so that {story.business_value}.
                </p>
                <p className="muted">
                  Epic: {story.epic_id} · Priority: {story.priority} · Suggested points (unconfirmed):{' '}
                  {story.suggested_story_points ?? 'N/A'}
                </p>
                <ul>
                  {story.acceptance_criteria.map((ac) => (
                    <li key={ac.criterion_id}>
                      Given {ac.given}, when {ac.when}, then {ac.then}.
                    </li>
                  ))}
                </ul>
                <Citations refs={story.source_references} />
              </div>
            ))}
          </section>

          <section className="panel">
            <h2>Technical Tasks ({plan.technical_tasks.length})</h2>
            <p className="muted">Recommendations, not confirmed technical requirements.</p>
            <p className="muted">
              Regenerating also rebuilds Dependencies and the RAID log below, against the
              existing epics/stories — it will require re-approval of the plan before export.
            </p>
            <div className="form-actions">
              <button
                className="button-hover"
                type="button"
                disabled={regeneratingTasksRaid}
                onClick={handleRegenerateTasksRaid}
              >
                <HoverButtonContent>
                  {regeneratingTasksRaid ? 'Regenerating… (this can take a while)' : 'Regenerate tasks, dependencies & RAID'}
                </HoverButtonContent>
              </button>
            </div>
            <ul>
              {plan.technical_tasks.map((task) => (
                <li key={task.task_id}>
                  [{task.category}] {task.description}
                  {task.story_id ? ` (story ${task.story_id})` : ''}
                </li>
              ))}
            </ul>
          </section>

          <section className="panel">
            <h2>Dependencies ({plan.raid.dependencies.length})</h2>
            <ul>
              {plan.raid.dependencies.map((dep) => (
                <li key={dep.dependency_id}>
                  {dep.blocking_item_id} blocks {dep.blocked_item_id} ({dep.dependency_type})
                  {dep.description ? `: ${dep.description}` : ''}
                </li>
              ))}
            </ul>
          </section>

          <section className="panel">
            <h2>RAID Log</h2>
            <p className="muted">Risks</p>
            <ul>
              {plan.raid.risks.map((risk) => (
                <li key={risk.risk_id}>
                  {risk.description} <Badge classification={risk.classification} />
                  <span className="muted">
                    {' '}
                    (probability {risk.probability}, impact {risk.impact}, severity {risk.severity})
                  </span>
                </li>
              ))}
            </ul>
            <p className="muted">Assumptions</p>
            <ul>
              {plan.raid.assumptions.map((a) => (
                <li key={a.assumption_id}>
                  {a.description} <Badge classification={a.classification} />
                </li>
              ))}
            </ul>
            <p className="muted">Issues</p>
            <ul>
              {plan.raid.issues.map((issue) => (
                <li key={issue.issue_id}>
                  {issue.description} ({issue.status})
                </li>
              ))}
            </ul>
          </section>

          <section className="panel">
            <h2>Sprint Plan</h2>
            <p className="muted">
              Regenerating will require re-approval of the plan before export.
            </p>
            <div className="form-actions">
              <button
                className="button-hover"
                type="button"
                disabled={regeneratingSprintPlan}
                onClick={handleRegenerateSprintPlan}
              >
                <HoverButtonContent>
                  {regeneratingSprintPlan ? 'Regenerating… (this can take a while)' : 'Regenerate sprint plan'}
                </HoverButtonContent>
              </button>
            </div>
            {plan.sprint_plan ? (
              <>
                <p className="muted">
                  AI-generated draft. Requires human review. Suggested sprints:{' '}
                  {plan.sprint_plan.suggested_sprint_count}
                </p>
                {plan.sprint_plan.sprints.map((sprint) => (
                  <div key={sprint.sprint_number} className="artifact-card">
                    <strong>
                      Sprint {sprint.sprint_number}: {sprint.sprint_goal}
                    </strong>
                    <p className="muted">
                      {sprint.story_point_total} points: {sprint.story_ids.join(', ') || 'no stories assigned'}
                    </p>
                  </div>
                ))}
                {plan.sprint_plan.unscheduled_story_ids.length > 0 && (
                  <p className="muted">Unscheduled: {plan.sprint_plan.unscheduled_story_ids.join(', ')}</p>
                )}
              </>
            ) : (
              <p className="muted">No sprint plan generated.</p>
            )}
          </section>

          <section className="panel">
            <h2>Traceability Matrix ({plan.traceability.rows.length} requirements)</h2>
            <table className="traceability-table">
              <thead>
                <tr>
                  <th>Requirement</th>
                  <th>Epic</th>
                  <th>Story</th>
                  <th>Acceptance Criteria</th>
                </tr>
              </thead>
              <tbody>
                {plan.traceability.rows.map((row) => (
                  <tr key={row.requirement_id}>
                    <td>{row.requirement_id}</td>
                    <td>{row.epic_id ?? 'N/A'}</td>
                    <td>{row.story_id ?? 'N/A'}</td>
                    <td>{row.acceptance_criterion_ids.join(', ') || 'N/A'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </>
      )}
    </div>
  )
}
