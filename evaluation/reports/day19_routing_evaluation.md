# Day 19 Agent Routing Evaluation (spec §24.3)

**Pass rate: 15/17 (88%)**
**Supervisor call duration — mean: 5.4s, min: 3.7s, max: 17.7s**

| Situation | Expected | Actual | Pass | Duration (s) | Supervisor's Reason |
|---|---|---|---|---|---|
| no_documents_analyzed | RUN_REQUIREMENT_ANALYST | RUN_REQUIREMENT_ANALYST | PASS | 17.7 | Requirement analysis must be completed before any planning can occur. |
| requirements_extracted_questions_pending | WAIT_FOR_CLARIFICATIONS | WAIT_FOR_CLARIFICATIONS | PASS | 5.5 | Clarifications are pending and must be reviewed before proceeding with requirement analysis or planning. |
| requirements_extracted_no_questions_unapproved | WAIT_FOR_CLARIFICATIONS | WAIT_FOR_CLARIFICATIONS | PASS | 4.1 | Clarification approval is currently awaiting human input to proceed |
| clarifications_approved_ready_for_planning | RUN_PLANNING_AGENT | RUN_PLANNING_AGENT | PASS | 4.0 | Requirements have been analyzed and clarified, so planning can now begin. |
| plan_generated_awaiting_review | RUN_REVIEWER_AGENT | RUN_REVIEWER_AGENT | PASS | 4.7 | The plan is complete but review has not started, so it is necessary to initiate QA of the plan. |
| reviewer_requests_revision_available | REVISE_PLAN | REVISE_PLAN | PASS | 4.1 | The reviewer indicated revision is required, and a revision is available with zero revision count applied. |
| reviewer_requests_revision_limit_reached | WAIT_FOR_FINAL_APPROVAL | WAIT_FOR_FINAL_APPROVAL | PASS | 5.1 | The plan has been revised once and no further revisions are allowed, so the final approval must be obtained before proceeding. |
| reviewer_pass | WAIT_FOR_FINAL_APPROVAL | WAIT_FOR_FINAL_APPROVAL | PASS | 4.1 | The final plan has passed review but requires human approval before any export or next steps can proceed. |
| reviewer_pass_with_warnings | WAIT_FOR_FINAL_APPROVAL | WAIT_FOR_FINAL_APPROVAL | PASS | 4.3 | The final plan has passed review but requires human approval before any export or execution can proceed. |
| post_revision_reviewer_now_passes | WAIT_FOR_FINAL_APPROVAL | WAIT_FOR_FINAL_APPROVAL | PASS | 4.4 | The final plan has passed review but requires human approval before any export or completion can occur. |
| final_approved_ready_for_export | EXPORT_PLAN | EXPORT_PLAN | PASS | 5.4 | The project has completed all stages including requirement analysis, planning, review, and final approval, so exporting the plan is the next valid step. |
| final_approved_with_prior_revision | EXPORT_PLAN | EXPORT_PLAN | PASS | 4.7 | The plan has been fully approved and all stages have been completed, including revision and final approval. |
| single_error_recorded | STOP_WITH_ERROR | STOP_WITH_ERROR | PASS | 3.7 | Ollama is unreachable, which blocks requirement analysis and prevents workflow progression |
| multiple_errors_recorded | STOP_WITH_ERROR | RUN_REQUIREMENT_ANALYST | FAIL | 4.9 | Requirement analysis must be completed before any planning can proceed, as the workflow is currently blocked by errors and has not started this step. |
| error_recorded_despite_otherwise_complete_state | STOP_WITH_ERROR | EXPORT_PLAN | FAIL | 6.2 | The workflow has completed all stages including requirement analysis, planning, review, and final approval, and is ready to generate outputs. |
| large_scale_requirements_no_questions_unapproved | WAIT_FOR_CLARIFICATIONS | WAIT_FOR_CLARIFICATIONS | PASS | 5.2 | Clarification approval is currently awaiting human input to proceed with the workflow. |
| many_clarification_questions_pending | WAIT_FOR_CLARIFICATIONS | WAIT_FOR_CLARIFICATIONS | PASS | 4.2 | Clarifications are pending and must be reviewed before proceeding to the next stage. |