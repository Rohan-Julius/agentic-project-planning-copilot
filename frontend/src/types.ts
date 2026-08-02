export interface Project {
  project_id: string
  name: string
  description: string
  business_domain: string
  methodology: string
  expected_duration_weeks: number | null
  team_composition: string
  target_platforms: string[]
  technology_constraints: string[]
  status: string
}

export interface ProjectCreateInput {
  name: string
  description: string
  business_domain: string
  expected_duration_weeks: number | null
  team_composition: string
  target_platforms: string[]
  technology_constraints: string[]
}

export interface ProjectDocument {
  document_id: string
  project_id: string
  document_name: string
  document_type: string
  source_type: string
  document_version: string
  status: string
}

export interface SourceReference {
  document_name: string
  page_number: number | null
  section: string | null
  chunk_id: string
}

export interface ClarificationQuestion {
  question_id: string
  category: string
  question: string
  reason_for_asking: string
  related_requirement_id: string | null
  source_reference: SourceReference | null
  priority: 'Highest' | 'High' | 'Medium' | 'Low'
  status: 'PENDING' | 'ANSWERED' | 'DEFERRED' | 'NOT_APPLICABLE'
  user_answer: string | null
}

export interface WorkflowRun {
  workflow_run_id: string
  project_id: string
  status: string
  revision_count: number
  final_approved: boolean
  started_at: string
  ended_at: string | null
  pending_gate: string | null
}

export interface IndexResult {
  indexed_document_ids: string[]
  chunk_count: number
  errors: Record<string, string>
}

export type Classification =
  | 'SOURCE_BACKED'
  | 'CLARIFICATION_BACKED'
  | 'ASSUMPTION'
  | 'AI_RECOMMENDATION'

export interface ProjectSummary {
  business_problem: string
  proposed_solution: string
  objectives: string[]
  target_users: string[]
  expected_benefits: string[]
  success_criteria: string[]
  major_constraints: string[]
}

export interface Scope {
  in_scope: string[]
  out_of_scope: string[]
  future_scope: string[]
  assumptions: string[]
  constraints: string[]
}

export interface AcceptanceCriterion {
  criterion_id: string
  given: string
  when: string
  then: string
}

export interface Epic {
  epic_id: string
  title: string
  objective: string
  business_value: string
  description: string
  priority: 'Highest' | 'High' | 'Medium' | 'Low'
  dependencies: string[]
  risks: string[]
  classification: Classification
  source_references: SourceReference[]
}

export interface UserStory {
  story_id: string
  epic_id: string
  title: string
  persona: string
  story_statement: string
  business_value: string
  priority: 'Highest' | 'High' | 'Medium' | 'Low'
  acceptance_criteria: AcceptanceCriterion[]
  dependencies: string[]
  assumptions: string[]
  suggested_story_points: number | null
  confidence: number
  classification: Classification
  source_references: SourceReference[]
}

export interface TechnicalTask {
  task_id: string
  story_id: string | null
  category: string
  description: string
  is_recommendation: boolean
}

export interface Dependency {
  dependency_id: string
  blocking_item_id: string
  blocked_item_id: string
  dependency_type: 'BLOCKS' | 'REQUIRES' | 'RELATES_TO'
  description: string
  suggested_resolution: string
}

export interface Risk {
  risk_id: string
  description: string
  probability: 'Low' | 'Medium' | 'High'
  impact: 'Low' | 'Medium' | 'High'
  severity: 'Low' | 'Medium' | 'High'
  mitigation: string
  contingency: string
  classification: Classification
  source_references: SourceReference[]
}

export interface Assumption {
  assumption_id: string
  description: string
  classification: Classification
  source_references: SourceReference[]
}

export interface Issue {
  issue_id: string
  description: string
  status: string
  source_references: SourceReference[]
}

export interface RaidLog {
  risks: Risk[]
  assumptions: Assumption[]
  issues: Issue[]
  dependencies: Dependency[]
}

export interface Sprint {
  sprint_number: number
  sprint_goal: string
  story_ids: string[]
  story_point_total: number
}

export interface SprintPlan {
  is_ai_generated_draft: boolean
  suggested_sprint_count: number
  sprints: Sprint[]
  dependency_considerations: string[]
  unscheduled_story_ids: string[]
}

export interface TraceabilityRow {
  requirement_id: string
  source_references: SourceReference[]
  epic_id: string | null
  story_id: string | null
  acceptance_criterion_ids: string[]
}

export interface TraceabilityMatrix {
  rows: TraceabilityRow[]
}

export interface ProjectPlan {
  summary: ProjectSummary
  scope: Scope
  epics: Epic[]
  stories: UserStory[]
  technical_tasks: TechnicalTask[]
  raid: RaidLog
  sprint_plan: SprintPlan | null
  traceability: TraceabilityMatrix
}

export interface ReviewerIssue {
  artifact_id: string
  issue_type: string
  description: string
  recommended_action: string
}

export interface ReviewerReport {
  decision: 'PASS' | 'PASS_WITH_WARNINGS' | 'REVISION_REQUIRED'
  missing_requirements: string[]
  unsupported_claims: ReviewerIssue[]
  duplicate_stories: ReviewerIssue[]
  missing_acceptance_criteria: ReviewerIssue[]
  weak_acceptance_criteria: ReviewerIssue[]
  traceability_gaps: ReviewerIssue[]
  dependency_issues: ReviewerIssue[]
  warnings: string[]
  revision_instructions: ReviewerIssue[]
}

export interface WorkflowEvent {
  workflow_run_id: string
  timestamp: string
  agent: string
  stage: string
  action: string
  tool: string | null
  status: string
  result_count: number | null
  duration_ms: number | null
  error: string | null
}
