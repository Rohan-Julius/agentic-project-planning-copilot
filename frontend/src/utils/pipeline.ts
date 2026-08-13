import type { WorkflowRun } from '../types'
import { isEventLive } from './runFreshness'

export type PipelineStage = 'documents' | 'clarify' | 'plan' | 'review' | 'export'

export const PIPELINE_STAGES: { stage: PipelineStage; label: string }[] = [
  { stage: 'documents', label: 'Documents' },
  { stage: 'clarify', label: 'Clarify' },
  { stage: 'plan', label: 'Plan' },
  { stage: 'review', label: 'Review' },
  { stage: 'export', label: 'Export' },
]

export type PipelineStatus =
  | { kind: 'stage'; stage: PipelineStage }
  | { kind: 'working' }
  | { kind: 'stalled' }
  | { kind: 'error' }

/**
 * Derives a project's position in the fixed Documents -> Clarify -> Plan ->
 * Review -> Export pipeline (spec §10) from its latest WorkflowRun, using
 * only fields the API already returns. Deliberately does not guess a
 * precise stage when the available fields don't determine one (e.g. an
 * unrecognized pending_gate value) — reports "working" instead.
 *
 * `run` is `null` when the project has no workflow run yet (the backend
 * returns 404 for `/workflow/status` in that case — see
 * `app/api/workflow.py::workflow_status`).
 *
 * `latestEventTimestamp` (the project's latest WorkflowEvent timestamp, or `null` if none)
 * is what tells "working" apart from "stalled" — `WorkflowRun.status` alone can't: nothing
 * on the backend resumes a run automatically if the process running it dies mid-call (see
 * runFreshness.ts), so a dead run stays frozen at RUNNING forever and looks identical to a
 * genuinely active one unless something checks how recently it last actually did anything.
 * Only applies to RUNNING — WAITING_FOR_HUMAN_INPUT is an intentional pause, not something
 * that's supposed to show ongoing activity, so staleness doesn't apply to it.
 */
export function derivePipelineStatus(
  run: WorkflowRun | null,
  latestEventTimestamp: string | null,
  now: number,
): PipelineStatus {
  if (!run) return { kind: 'stage', stage: 'documents' }

  if (run.status === 'ERROR') return { kind: 'error' }

  if (run.status === 'RUNNING') {
    const isLive = latestEventTimestamp !== null && isEventLive(latestEventTimestamp, now)
    return isLive ? { kind: 'working' } : { kind: 'stalled' }
  }

  if (run.status === 'WAITING_FOR_HUMAN_INPUT') {
    if (run.pending_gate === 'clarification_gate') return { kind: 'stage', stage: 'clarify' }
    if (run.pending_gate === 'final_gate') return { kind: 'stage', stage: 'review' }
    return { kind: 'working' }
  }

  if (run.status === 'COMPLETED') {
    return { kind: 'stage', stage: run.final_approved ? 'export' : 'review' }
  }

  return { kind: 'working' }
}

/** Index of `stage` within PIPELINE_STAGES, for rendering done/current/upcoming dots. */
export function stageIndex(stage: PipelineStage): number {
  return PIPELINE_STAGES.findIndex((s) => s.stage === stage)
}
