# Day 20 Repeatability Evaluation (spec §24.8) — scenario 2, 3 independent runs

| Run | Status | Reqs | Epics | Stories | Reviewer decision | Revision? | Valid? | Errors | Traceability | Total agent time |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | COMPLETED | 30 | 17 | 17 | REVISION_REQUIRED | True | False | 1 | 71.0% | 6513.0s (108.5 min) |
| 2 | COMPLETED | 30 | 17 | 16 | PASS_WITH_WARNINGS | False | True | 0 | 86.5% | 3559.8s (59.3 min) |
| 3 | COMPLETED | 32 | 14 | 14 | REVISION_REQUIRED | True | False | 1 | 92.6% | 5846.9s (97.4 min) |

## Per-agent-call durations

### Run 1
- Supervisor (supervisor, EVALUATE_STATE, SUCCESS): 19.9s
- RequirementAnalyst (requirement_analyst, EXTRACT_REQUIREMENTS, SUCCESS): 651.5s
- Supervisor (supervisor, EVALUATE_STATE, SUCCESS): 7.2s
- Planning (planning, GENERATE_PLAN, SUCCESS): 2148.2s
- Supervisor (supervisor, EVALUATE_STATE, SUCCESS): 5.9s
- Reviewer (reviewer, REVIEW_PLAN, SUCCESS): 737.1s
- Supervisor (supervisor, EVALUATE_STATE, SUCCESS): 12.3s
- Planning (plan_revision, REVISE_PLAN, SUCCESS): 2115.4s
- Supervisor (supervisor, EVALUATE_STATE, SUCCESS): 13.9s
- Reviewer (reviewer, REVIEW_PLAN, SUCCESS): 785.6s
- Supervisor (supervisor, EVALUATE_STATE, SUCCESS): 16.0s

### Run 2
- Supervisor (supervisor, EVALUATE_STATE, SUCCESS): 6.3s
- RequirementAnalyst (requirement_analyst, EXTRACT_REQUIREMENTS, SUCCESS): 921.3s
- Supervisor (supervisor, EVALUATE_STATE, SUCCESS): 10.5s
- Planning (planning, GENERATE_PLAN, SUCCESS): 2296.7s
- Supervisor (supervisor, EVALUATE_STATE, SUCCESS): 7.4s
- Reviewer (reviewer, REVIEW_PLAN, SUCCESS): 298.1s
- Supervisor (supervisor, EVALUATE_STATE, SUCCESS): 19.5s

### Run 3
- Supervisor (supervisor, EVALUATE_STATE, SUCCESS): 8.4s
- RequirementAnalyst (requirement_analyst, EXTRACT_REQUIREMENTS, SUCCESS): 1111.4s
- Supervisor (supervisor, EVALUATE_STATE, SUCCESS): 10.8s
- Planning (planning, GENERATE_PLAN, SUCCESS): 1674.6s
- Supervisor (supervisor, EVALUATE_STATE, SUCCESS): 7.6s
- Reviewer (reviewer, REVIEW_PLAN, SUCCESS): 643.4s
- Supervisor (supervisor, EVALUATE_STATE, SUCCESS): 21.3s
- Planning (plan_revision, REVISE_PLAN, SUCCESS): 1990.8s
- Supervisor (supervisor, EVALUATE_STATE, SUCCESS): 10.5s
- Reviewer (reviewer, REVIEW_PLAN, SUCCESS): 352.6s
- Supervisor (supervisor, EVALUATE_STATE, SUCCESS): 15.5s