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
