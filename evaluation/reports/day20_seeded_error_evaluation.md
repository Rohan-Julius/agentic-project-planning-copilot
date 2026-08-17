# Day 20 Reviewer Effectiveness — 6 Seeded Errors (spec §24.7)

| Seed | Outcome | Reviewer decision | Duration (s) | Notes |
|---|---|---|---|---|
| story_without_epic | schema_rejected_before_review | None | 0.0 | 1 validation error for ProjectPlan
  Value error, story 'US-001' references unknown epic_id 'EPIC-999-DOES-NOT-EXIST' (every story must belong to an e |
| missing_acceptance_criteria | schema_rejected_before_review | None | 0.0 | 1 validation error for ProjectPlan
stories.0.acceptance_criteria
  List should have at least 1 item after validation, not 0 [type=too_short, input_val |
| invalid_citation | reviewer_ran | REVISION_REQUIRED | 170.9 | {'artifact_id': 'REQ-017', 'issue_type': 'unsupported_claim', 'description': 'The requirement states that a prolonged Stripe outage could block all ne |
| duplicate_story | reviewer_ran | REVISION_REQUIRED | 250.6 | {'artifact_id': 'US-001-DUP', 'issue_type': 'duplicate_stories', 'description': 'A near-identical story [US-001-DUP] exists with the same text and acc |
| unsupported_requirement | reviewer_ran | REVISION_REQUIRED | 295.9 | {'artifact_id': 'US-022', 'issue_type': 'unsupported_claim', 'description': 'The claim that the system will support mobile devices is presented as a f |
| circular_dependency | reviewer_ran | REVISION_REQUIRED | 203.9 | {'artifact_id': 'US-022', 'issue_type': 'unsupported_claim', 'description': 'The story references mobile device support as a feature, but the claim is |