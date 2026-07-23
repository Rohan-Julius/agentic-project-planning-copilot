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
}
