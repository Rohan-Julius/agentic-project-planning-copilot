import { describe, expect, it } from 'vitest'
import {
  actionLabel,
  agentLabel,
  eventActivityLabel,
  eventStatusLabel,
  logRowStatusLabel,
  revisionStatusLabel,
  runStatusLabel,
  stageLabel,
  toolLabel,
} from './workflowLabels'

describe('agentLabel', () => {
  it('humanizes every real backend agent key', () => {
    expect(agentLabel('Supervisor')).toBe('Supervisor')
    expect(agentLabel('RequirementAnalyst')).toBe('Requirement Analyst')
    expect(agentLabel('Planning')).toBe('Planning')
    expect(agentLabel('Reviewer')).toBe('Reviewer')
    expect(agentLabel('Workflow')).toBe('System')
  })

  it('falls back to a humanized PascalCase split for an unrecognized agent', () => {
    expect(agentLabel('SomeFutureAgent')).toBe('Some Future Agent')
  })
})

describe('stageLabel', () => {
  it('humanizes every real backend stage key', () => {
    expect(stageLabel('supervisor')).toBe('Routing')
    expect(stageLabel('requirement_analyst')).toBe('Requirement analysis')
    expect(stageLabel('planning')).toBe('Planning')
    expect(stageLabel('reviewer')).toBe('Review')
    expect(stageLabel('plan_revision')).toBe('Plan revision')
    expect(stageLabel('clarification_gate')).toBe('Clarification gate')
    expect(stageLabel('final_gate')).toBe('Final approval gate')
    expect(stageLabel('export')).toBe('Export')
    expect(stageLabel('stop_error')).toBe('Stopped')
  })

  it('falls back to a humanized snake_case split for an unrecognized stage', () => {
    expect(stageLabel('some_future_stage')).toBe('Some future stage')
  })
})

describe('eventStatusLabel', () => {
  it('humanizes every real event status', () => {
    expect(eventStatusLabel('IN_PROGRESS')).toBe('In progress')
    expect(eventStatusLabel('SUCCESS')).toBe('Completed')
    expect(eventStatusLabel('ERROR')).toBe('Error')
  })
})

describe('logRowStatusLabel', () => {
  it('reads "In progress" for the genuinely live row', () => {
    expect(logRowStatusLabel('IN_PROGRESS', true)).toBe('In progress')
  })

  it('reads "Started" (past tense) for a superseded historical IN_PROGRESS row', () => {
    // An append-only log keeps the original "started" row forever even after a later row
    // logs the same action's completion — that row must not still claim to be ongoing.
    expect(logRowStatusLabel('IN_PROGRESS', false)).toBe('Started')
  })

  it('is unaffected by liveness for terminal statuses', () => {
    expect(logRowStatusLabel('SUCCESS', false)).toBe('Completed')
    expect(logRowStatusLabel('SUCCESS', true)).toBe('Completed')
    expect(logRowStatusLabel('ERROR', false)).toBe('Error')
  })
})

describe('revisionStatusLabel', () => {
  it('reports a revision is still available when none have been used', () => {
    expect(revisionStatusLabel(0)).toBe(
      'No revisions used yet. One revision cycle is available if this plan needs rework.',
    )
  })

  it('reports the one allowed revision has been used', () => {
    expect(revisionStatusLabel(1)).toBe(
      'This plan has already used its one allowed revision cycle. Further review issues go straight to final approval instead of another automatic rewrite.',
    )
  })

  it('treats any count above the limit the same as reaching it', () => {
    expect(revisionStatusLabel(2)).toBe(revisionStatusLabel(1))
  })
})

describe('runStatusLabel', () => {
  it('humanizes every real run status', () => {
    expect(runStatusLabel('RUNNING')).toBe('Running')
    expect(runStatusLabel('WAITING_FOR_HUMAN_INPUT')).toBe('Waiting for your input')
    expect(runStatusLabel('COMPLETED')).toBe('Completed')
    expect(runStatusLabel('ERROR')).toBe('Stopped with an error')
  })
})

describe('actionLabel', () => {
  it('humanizes every fixed action', () => {
    expect(actionLabel('EVALUATE_STATE')).toBe('Deciding what to do next')
    expect(actionLabel('ERROR')).toBe('Ran into an error')
    expect(actionLabel('EXTRACT_REQUIREMENTS')).toBe('Extracting requirements from your documents')
    expect(actionLabel('GENERATE_PLAN')).toBe('Generating the project plan')
    expect(actionLabel('REVIEW_PLAN')).toBe('Reviewing the generated plan')
    expect(actionLabel('REVISE_PLAN')).toBe('Revising the plan')
    expect(actionLabel('WORKFLOW_COMPLETE')).toBe('Workflow complete')
    expect(actionLabel('RESUMED')).toBe('Resumed after your input')
    expect(actionLabel('STOP_WITH_ERROR')).toBe('Stopped after repeated errors')
    expect(actionLabel('ABANDONED')).toBe('Manually marked as failed')
  })

  it('humanizes every RECOMMEND_<SupervisorAction> action the Supervisor can log', () => {
    expect(actionLabel('RECOMMEND_RUN_REQUIREMENT_ANALYST')).toBe('Recommended: run requirement analysis')
    expect(actionLabel('RECOMMEND_WAIT_FOR_CLARIFICATIONS')).toBe(
      'Recommended: wait for clarification answers',
    )
    expect(actionLabel('RECOMMEND_RUN_PLANNING_AGENT')).toBe('Recommended: generate the plan')
    expect(actionLabel('RECOMMEND_RUN_REVIEWER_AGENT')).toBe('Recommended: review the plan')
    expect(actionLabel('RECOMMEND_REVISE_PLAN')).toBe('Recommended: revise the plan')
    expect(actionLabel('RECOMMEND_WAIT_FOR_FINAL_APPROVAL')).toBe('Recommended: wait for final approval')
    expect(actionLabel('RECOMMEND_EXPORT_PLAN')).toBe('Recommended: export the plan')
    expect(actionLabel('RECOMMEND_STOP_WITH_ERROR')).toBe('Recommended: stop due to errors')
  })

  it('humanizes every DECISION_<ReviewerDecision> action the Reviewer can log', () => {
    expect(actionLabel('DECISION_PASS')).toBe('Review passed')
    expect(actionLabel('DECISION_PASS_WITH_WARNINGS')).toBe('Review passed with warnings')
    expect(actionLabel('DECISION_REVISION_REQUIRED')).toBe('Revision required')
  })

  it('falls back to a humanized SCREAMING_SNAKE_CASE split for an unrecognized action', () => {
    expect(actionLabel('SOME_FUTURE_ACTION')).toBe('Some future action')
  })
})

describe('toolLabel', () => {
  it('humanizes every real tool name a CALL_TOOL event can carry', () => {
    expect(toolLabel('get_project_information')).toBe('Reading project information')
    expect(toolLabel('search_project_documents')).toBe('Searching your project documents')
    expect(toolLabel('search_company_standards')).toBe('Searching organizational standards')
    expect(toolLabel('find_supporting_evidence')).toBe('Looking for supporting evidence')
    expect(toolLabel('save_requirements')).toBe('Saving extracted requirements')
    expect(toolLabel('save_clarification_questions')).toBe('Saving clarification questions')
    expect(toolLabel('get_clarification_answers')).toBe('Reading clarification answers')
    expect(toolLabel('get_requirements')).toBe('Loading approved requirements')
    expect(toolLabel('save_planning_artifacts')).toBe('Saving the generated plan')
    expect(toolLabel('load_current_plan')).toBe('Loading the current plan')
    expect(toolLabel('validate_project_plan')).toBe('Validating the plan')
    expect(toolLabel('check_traceability')).toBe('Checking requirement traceability')
    expect(toolLabel('save_reviewer_report')).toBe('Saving the review report')
  })

  it('falls back to a humanized snake_case split for an unrecognized tool', () => {
    expect(toolLabel('some_future_tool')).toBe('Some future tool')
  })
})

describe('eventActivityLabel', () => {
  it('shows the tool sentence, not the raw function name, for a CALL_TOOL event', () => {
    expect(eventActivityLabel({ action: 'CALL_TOOL', tool: 'search_project_documents' })).toBe(
      'Searching your project documents',
    )
  })

  it('falls back to actionLabel for a CALL_TOOL event with no tool set', () => {
    expect(eventActivityLabel({ action: 'CALL_TOOL' })).toBe('Called a tool')
    expect(eventActivityLabel({ action: 'CALL_TOOL', tool: null })).toBe('Called a tool')
  })

  it('uses actionLabel for every non-tool-call action', () => {
    expect(eventActivityLabel({ action: 'GENERATE_PLAN' })).toBe('Generating the project plan')
  })
})
