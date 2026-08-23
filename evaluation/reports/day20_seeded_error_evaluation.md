# Day 20 Reviewer Effectiveness — 6 Seeded Errors (spec §24.7)

| Seed | Outcome | Reviewer decision | Duration (s) | Notes |
|---|---|---|---|---|
| story_without_epic | schema_rejected_before_review | None | 0.0 | 1 validation error for ProjectPlan
  Value error, story 'US-001' references unknown epic_id 'EPIC-999-DOES-NOT-EXIST' (every story must belong to an e |
| missing_acceptance_criteria | schema_rejected_before_review | None | 0.0 | 1 validation error for ProjectPlan
stories.0.acceptance_criteria
  List should have at least 1 item after validation, not 0 [type=too_short, input_val |
| invalid_citation | reviewer_ran | REVISION_REQUIRED | 60.5 | traceability_gaps=1; structural_errors=1 |
| duplicate_story | reviewer_ran | REVISION_REQUIRED | 113.9 | duplicate_stories=1; traceability_gaps=2; structural_errors=1 |
| unsupported_requirement | reviewer_ran | PASS_WITH_WARNINGS | 75.1 | traceability_gaps=1 |
| circular_dependency | reviewer_ran | PASS_WITH_WARNINGS | 142.9 | weak_acceptance_criteria=3; traceability_gaps=1 |