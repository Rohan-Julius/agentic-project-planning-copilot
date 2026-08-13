import { describe, expect, it } from 'vitest'
import { derivePipelineStatus, stageIndex } from './pipeline'
import type { WorkflowRun } from '../types'

const NOW = new Date('2026-08-07T12:00:00Z').getTime()
const FRESH_TIMESTAMP = '2026-08-07T11:59:58Z'
const STALE_TIMESTAMP = '2026-08-05T22:33:45Z' // the actual stuck run found live this session

function makeRun(overrides: Partial<WorkflowRun>): WorkflowRun {
  return {
    workflow_run_id: 'run-1',
    project_id: 'proj-1',
    status: 'RUNNING',
    revision_count: 0,
    final_approved: false,
    started_at: '2026-08-05T00:00:00Z',
    ended_at: null,
    pending_gate: null,
    ...overrides,
  }
}

describe('derivePipelineStatus', () => {
  it('returns the documents stage when no run exists yet', () => {
    expect(derivePipelineStatus(null, null, NOW)).toEqual({ kind: 'stage', stage: 'documents' })
  })

  it('reports working while a run is actively RUNNING with a recent event', () => {
    const run = makeRun({ status: 'RUNNING' })
    expect(derivePipelineStatus(run, FRESH_TIMESTAMP, NOW)).toEqual({ kind: 'working' })
  })

  it('reports stalled when RUNNING but the latest event is stale — the actual dashboard bug', () => {
    // Same blind spot the Agent Execution screen had: WorkflowRun.status alone can't tell
    // "actively working" apart from "the process that was running this died," since nothing
    // resumes an orphaned run automatically (see runFreshness.ts).
    const run = makeRun({ status: 'RUNNING' })
    expect(derivePipelineStatus(run, STALE_TIMESTAMP, NOW)).toEqual({ kind: 'stalled' })
  })

  it('reports stalled when RUNNING and there is no event data to prove it is live', () => {
    // No event timestamp at all must not default to "working" — that's the exact failure
    // mode being fixed, just via a missing value instead of an old one.
    const run = makeRun({ status: 'RUNNING' })
    expect(derivePipelineStatus(run, null, NOW)).toEqual({ kind: 'stalled' })
  })

  it('reports error when the run status is ERROR', () => {
    expect(derivePipelineStatus(makeRun({ status: 'ERROR' }), null, NOW)).toEqual({ kind: 'error' })
  })

  it('maps the clarification gate to the clarify stage regardless of event freshness', () => {
    // WAITING_FOR_HUMAN_INPUT is an intentional pause, not "should be active right now" —
    // staleness only applies to RUNNING.
    const run = makeRun({ status: 'WAITING_FOR_HUMAN_INPUT', pending_gate: 'clarification_gate' })
    expect(derivePipelineStatus(run, STALE_TIMESTAMP, NOW)).toEqual({ kind: 'stage', stage: 'clarify' })
  })

  it('maps the final gate to the review stage', () => {
    const run = makeRun({ status: 'WAITING_FOR_HUMAN_INPUT', pending_gate: 'final_gate' })
    expect(derivePipelineStatus(run, null, NOW)).toEqual({ kind: 'stage', stage: 'review' })
  })

  it('falls back to working for an unrecognized pending gate rather than guessing', () => {
    const run = makeRun({ status: 'WAITING_FOR_HUMAN_INPUT', pending_gate: 'some_future_gate' })
    expect(derivePipelineStatus(run, null, NOW)).toEqual({ kind: 'working' })
  })

  it('maps a completed, approved run to export', () => {
    const run = makeRun({ status: 'COMPLETED', final_approved: true })
    expect(derivePipelineStatus(run, null, NOW)).toEqual({ kind: 'stage', stage: 'export' })
  })

  it('maps a completed, not-yet-approved run to review', () => {
    const run = makeRun({ status: 'COMPLETED', final_approved: false })
    expect(derivePipelineStatus(run, null, NOW)).toEqual({ kind: 'stage', stage: 'review' })
  })
})

describe('stageIndex', () => {
  it('orders stages Documents -> Clarify -> Plan -> Review -> Export', () => {
    expect(stageIndex('documents')).toBe(0)
    expect(stageIndex('clarify')).toBe(1)
    expect(stageIndex('plan')).toBe(2)
    expect(stageIndex('review')).toBe(3)
    expect(stageIndex('export')).toBe(4)
  })
})
