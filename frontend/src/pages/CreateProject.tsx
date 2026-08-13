import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import HoverButtonContent from '../components/HoverButtonContent'
import type { Project, ProjectCreateInput } from '../types'

/** Split a comma-separated field into a trimmed, non-empty list. */
function splitList(value: string): string[] {
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
}

export default function CreateProject() {
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [businessDomain, setBusinessDomain] = useState('')
  const [duration, setDuration] = useState('')
  const [teamComposition, setTeamComposition] = useState('')
  const [targetPlatforms, setTargetPlatforms] = useState('')
  const [technologyConstraints, setTechnologyConstraints] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    const payload: ProjectCreateInput = {
      name: name.trim(),
      description: description.trim(),
      business_domain: businessDomain.trim(),
      expected_duration_weeks: duration ? Number(duration) : null,
      team_composition: teamComposition.trim(),
      target_platforms: splitList(targetPlatforms),
      technology_constraints: splitList(technologyConstraints),
    }
    try {
      const project = await api.post<Project>('/projects', payload)
      navigate(`/projects/${project.project_id}/documents`)
    } catch (err) {
      setError((err as Error).message)
      setSubmitting(false)
    }
  }

  return (
    <div className="page">
      <header className="page-header">
        <h1>New project</h1>
        <Link className="back-link" to="/">
          ← Back to projects
        </Link>
      </header>

      <form className="form" onSubmit={handleSubmit}>
        <div className="field">
          <label htmlFor="name">Project name *</label>
          <input
            id="name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            autoFocus
          />
        </div>

        <div className="field">
          <label htmlFor="description">Description</label>
          <textarea
            id="description"
            rows={3}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </div>

        <div className="field">
          <label htmlFor="domain">Business domain</label>
          <input
            id="domain"
            value={businessDomain}
            onChange={(e) => setBusinessDomain(e.target.value)}
            placeholder="e.g. HR, e-commerce, support"
          />
        </div>

        <div className="field">
          <label htmlFor="methodology">Methodology</label>
          {/* Fixed to Agile/Scrum by project decision — milestone planning is out of scope. */}
          <input id="methodology" value="Agile / Scrum" readOnly disabled />
          <small className="muted">Fixed for this tool: a sprint plan is always generated.</small>
        </div>

        <div className="field">
          <label htmlFor="duration">Expected duration (weeks)</label>
          <input
            id="duration"
            type="number"
            min={1}
            value={duration}
            onChange={(e) => setDuration(e.target.value)}
          />
        </div>

        <div className="field">
          <label htmlFor="team">Team composition</label>
          <input
            id="team"
            value={teamComposition}
            onChange={(e) => setTeamComposition(e.target.value)}
            placeholder="e.g. 2 backend, 1 frontend, 1 QA"
          />
        </div>

        <div className="field">
          <label htmlFor="platforms">Target platforms</label>
          <input
            id="platforms"
            value={targetPlatforms}
            onChange={(e) => setTargetPlatforms(e.target.value)}
            placeholder="Comma-separated, e.g. Web, iOS, Android"
          />
        </div>

        <div className="field">
          <label htmlFor="constraints">Known technology constraints</label>
          <input
            id="constraints"
            value={technologyConstraints}
            onChange={(e) => setTechnologyConstraints(e.target.value)}
            placeholder="Comma-separated, e.g. PostgreSQL, on-prem only"
          />
        </div>

        {error && <p className="error">Could not create project: {error}</p>}

        <div className="form-actions">
          <button className="button-hover" type="submit" disabled={submitting || !name.trim()}>
            <HoverButtonContent>{submitting ? 'Creating…' : 'Create project'}</HoverButtonContent>
          </button>
        </div>
      </form>
    </div>
  )
}
