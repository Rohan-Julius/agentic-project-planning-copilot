/**
 * Human-readable text for the raw agent/stage/status/action keywords the backend logs
 * (app/workflow/graph.py, app/workflow/routes.py) — the execution screen must show safe
 * *summaries*, not the system's internal vocabulary (spec §16.4). Every real value the
 * backend can currently emit is mapped explicitly; anything unrecognized (a future action,
 * a typo, a value this file hasn't been updated for yet) falls back to a generic
 * word-splitter rather than leaking the raw keyword onto the screen.
 */

function titleCase(word: string): string {
  return word.length === 0 ? word : word[0].toUpperCase() + word.slice(1).toLowerCase()
}

/** "SOME_FUTURE_ACTION" -> "Some future action" (first word capitalized, rest lowercase). */
function humanizeSnake(raw: string): string {
  const words = raw.toLowerCase().split('_')
  return words.map((word, i) => (i === 0 ? titleCase(word) : word)).join(' ')
}

/** "SomeFutureAgent" -> "Some Future Agent" (every word capitalized — matches how agent
 * names like "RequirementAnalyst" read once split). */
function humanizePascal(raw: string): string {
  const words = raw.match(/[A-Z][a-z0-9]*|[a-z0-9]+/g) ?? [raw]
  return words.map(titleCase).join(' ')
}

const AGENT_LABELS: Record<string, string> = {
  Supervisor: 'Supervisor',
  RequirementAnalyst: 'Requirement Analyst',
  Planning: 'Planning',
  Reviewer: 'Reviewer',
  // "Workflow" is the engine logging its own bookkeeping (gate resume, completion,
  // controlled stop) rather than any one agent acting — "System" reads more honestly than
  // implying an agent named "Workflow" exists.
  Workflow: 'System',
}

export function agentLabel(agent: string): string {
  return AGENT_LABELS[agent] ?? humanizePascal(agent)
}

const STAGE_LABELS: Record<string, string> = {
  supervisor: 'Routing',
  requirement_analyst: 'Requirement analysis',
  planning: 'Planning',
  reviewer: 'Review',
  plan_revision: 'Plan revision',
  clarification_gate: 'Clarification gate',
  final_gate: 'Final approval gate',
  export: 'Export',
  stop_error: 'Stopped',
}

export function stageLabel(stage: string): string {
  return STAGE_LABELS[stage] ?? humanizeSnake(stage)
}

const EVENT_STATUS_LABELS: Record<string, string> = {
  IN_PROGRESS: 'In progress',
  SUCCESS: 'Completed',
  ERROR: 'Error',
}

export function eventStatusLabel(status: string): string {
  return EVENT_STATUS_LABELS[status] ?? humanizeSnake(status)
}

/**
 * The execution log is append-only — a row logged as IN_PROGRESS keeps that recorded
 * status forever, even once a later row logs that same action's SUCCESS/ERROR outcome. So
 * "In progress" (present tense) must only be shown on the one row that's genuinely
 * happening right now (`isLive`); every other IN_PROGRESS row is a superseded historical
 * marker and should read in the past tense instead, or it falsely implies ongoing work.
 */
export function logRowStatusLabel(status: string, isLive: boolean): string {
  if (status === 'IN_PROGRESS' && !isLive) return 'Started'
  return eventStatusLabel(status)
}

// Matches app/workflow/routes.py: `NODE_PLAN_REVISION if revision_count < 1 else
// NODE_FINAL_GATE` — "exactly one bounded revision cycle" (§20.1). Not exposed by the API
// as its own field since it's a fixed rule, not per-project config.
const REVISION_LIMIT = 1

export function revisionStatusLabel(revisionCount: number): string {
  if (revisionCount >= REVISION_LIMIT) {
    return (
      'This plan has already used its one allowed revision cycle. Further review issues ' +
      'go straight to final approval instead of another automatic rewrite.'
    )
  }
  return 'No revisions used yet. One revision cycle is available if this plan needs rework.'
}

const RUN_STATUS_LABELS: Record<string, string> = {
  RUNNING: 'Running',
  WAITING_FOR_HUMAN_INPUT: 'Waiting for your input',
  COMPLETED: 'Completed',
  ERROR: 'Stopped with an error',
}

export function runStatusLabel(status: string): string {
  return RUN_STATUS_LABELS[status] ?? humanizeSnake(status)
}

// Lowercase, human phrasing for each SupervisorAction (spec §7.1) — only ever appears
// after "Recommended: ", so these read as a continuation of that sentence, not a heading.
const SUPERVISOR_ACTION_PHRASES: Record<string, string> = {
  RUN_REQUIREMENT_ANALYST: 'run requirement analysis',
  WAIT_FOR_CLARIFICATIONS: 'wait for clarification answers',
  RUN_PLANNING_AGENT: 'generate the plan',
  RUN_REVIEWER_AGENT: 'review the plan',
  REVISE_PLAN: 'revise the plan',
  WAIT_FOR_FINAL_APPROVAL: 'wait for final approval',
  EXPORT_PLAN: 'export the plan',
  STOP_WITH_ERROR: 'stop due to errors',
}

const REVIEWER_DECISION_LABELS: Record<string, string> = {
  PASS: 'Review passed',
  PASS_WITH_WARNINGS: 'Review passed with warnings',
  REVISION_REQUIRED: 'Revision required',
}

/** `ReviewerReport.decision` (spec §16.7) — same wording `actionLabel` uses for the
 * Reviewer's `DECISION_*` log events, single source of truth for what these three values
 * mean in plain English. */
export function reviewerDecisionLabel(decision: string): string {
  return REVIEWER_DECISION_LABELS[decision] ?? humanizeSnake(decision)
}

const FIXED_ACTION_LABELS: Record<string, string> = {
  EVALUATE_STATE: 'Deciding what to do next',
  ERROR: 'Ran into an error',
  EXTRACT_REQUIREMENTS: 'Extracting requirements from your documents',
  GENERATE_PLAN: 'Generating the project plan',
  REVIEW_PLAN: 'Reviewing the generated plan',
  REVISE_PLAN: 'Revising the plan',
  WORKFLOW_COMPLETE: 'Workflow complete',
  RESUMED: 'Resumed after your input',
  STOP_WITH_ERROR: 'Stopped after repeated errors',
  ABANDONED: 'Manually marked as failed',
  // Only surfaces if a CALL_TOOL event is somehow missing its `tool` value (shouldn't
  // happen — every real backend call site sets one, see app/workflow/events.py
  // log_tool_call) — eventActivityLabel() prefers toolLabel(tool) whenever tool is present.
  CALL_TOOL: 'Called a tool',
}

/**
 * Plain-English sentence for the raw Python tool-function name a CALL_TOOL event's `tool`
 * field carries (app/workflow/events.py log_tool_call, called from the four agent modules).
 * §16.4 requires showing "Tool being called" as a safe execution summary — the raw function
 * name itself (e.g. "search_project_documents") is implementation detail, not a summary, so
 * this is the one place that name ever gets translated for display.
 */
const TOOL_LABELS: Record<string, string> = {
  get_project_information: 'Reading project information',
  search_project_documents: 'Searching your project documents',
  search_company_standards: 'Searching organizational standards',
  find_supporting_evidence: 'Looking for supporting evidence',
  save_requirements: 'Saving extracted requirements',
  save_clarification_questions: 'Saving clarification questions',
  get_clarification_answers: 'Reading clarification answers',
  get_requirements: 'Loading approved requirements',
  save_planning_artifacts: 'Saving the generated plan',
  load_current_plan: 'Loading the current plan',
  validate_project_plan: 'Validating the plan',
  check_traceability: 'Checking requirement traceability',
  save_reviewer_report: 'Saving the review report',
}

export function toolLabel(tool: string): string {
  return TOOL_LABELS[tool] ?? humanizeSnake(tool)
}

/**
 * `action` carries two dynamic prefixes on top of the fixed set (app/workflow/graph.py):
 * `RECOMMEND_{SupervisorAction}` (the Supervisor's advisory recommendation — audit/debug
 * only, never used for navigation) and `DECISION_{ReviewerDecision}` (the Reviewer's
 * verdict). Both need their suffix humanized too, not just stripped.
 */
export function actionLabel(action: string): string {
  if (action in FIXED_ACTION_LABELS) return FIXED_ACTION_LABELS[action]

  if (action.startsWith('RECOMMEND_')) {
    const suffix = action.slice('RECOMMEND_'.length)
    const phrase = SUPERVISOR_ACTION_PHRASES[suffix] ?? humanizeSnake(suffix).toLowerCase()
    return `Recommended: ${phrase}`
  }

  if (action.startsWith('DECISION_')) {
    return reviewerDecisionLabel(action.slice('DECISION_'.length))
  }

  return humanizeSnake(action)
}

/**
 * What AgentExecutionScreen actually renders as "current activity" for one event — usually
 * just `actionLabel(action)`, but a CALL_TOOL event's real content is which tool ran, not
 * the generic "Called a tool" action name, so this prefers `toolLabel(tool)` whenever `tool`
 * is set. Centralized here (rather than left as an inline ternary in the component) so the
 * "tool takes priority over action" rule has one tested definition, not two copies that can
 * drift (the Status heading and each execution-log row both need this same decision).
 */
export function eventActivityLabel(event: { action: string; tool?: string | null }): string {
  if (event.action === 'CALL_TOOL' && event.tool) return toolLabel(event.tool)
  return actionLabel(event.action)
}
