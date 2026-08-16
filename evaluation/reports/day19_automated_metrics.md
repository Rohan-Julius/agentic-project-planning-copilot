# Day 19 Automated Metrics (spec §24.1, §24.2, §24.4)

## scenario_1_leave_management
- Workflow status: WAITING_FOR_HUMAN_INPUT
- Requirements extracted: 28
- By category: {'functional': 18, 'non_functional': 6, 'integration': 2, 'constraint': 2}
- By classification: {'SOURCE_BACKED': 19, 'ASSUMPTION': 2, 'CLARIFICATION_BACKED': 7}
- SOURCE_BACKED citation rate: 100%
- Clarification questions: 7
  - By category: {'functional': 4, 'non_functional': 2, 'security': 1}
  - By priority: {'High': 5, 'Medium': 2}
- Tool calls (in order): ['get_project_information', 'search_project_documents', 'search_company_standards', 'save_requirements', 'save_clarification_questions']
- Unpermitted tool calls (§20.2 finding if non-empty): []
- Agent call durations:
  - Supervisor (supervisor, EVALUATE_STATE, SUCCESS): 11.2s
  - RequirementAnalyst (requirement_analyst, EXTRACT_REQUIREMENTS, SUCCESS): 766.1s
  - Supervisor (supervisor, EVALUATE_STATE, SUCCESS): 25.3s

## scenario_2_ecommerce_payments
- Workflow status: WAITING_FOR_HUMAN_INPUT
- Requirements extracted: 31
- By category: {'functional': 17, 'non_functional': 5, 'constraint': 5, 'security': 1, 'integration': 2, 'data': 1}
- By classification: {'SOURCE_BACKED': 21, 'CLARIFICATION_BACKED': 5, 'ASSUMPTION': 3, 'AI_RECOMMENDATION': 2}
- SOURCE_BACKED citation rate: 100%
- Clarification questions: 5
  - By category: {'non_functional': 1, 'functional': 4}
  - By priority: {'High': 3, 'Medium': 2}
- Tool calls (in order): ['get_project_information', 'search_project_documents', 'search_company_standards', 'save_requirements', 'save_clarification_questions']
- Unpermitted tool calls (§20.2 finding if non-empty): []
- Agent call durations:
  - Supervisor (supervisor, EVALUATE_STATE, SUCCESS): 12.6s
  - RequirementAnalyst (requirement_analyst, EXTRACT_REQUIREMENTS, SUCCESS): 1147.0s
  - Supervisor (supervisor, EVALUATE_STATE, SUCCESS): 17.8s

## scenario_3_ambiguous_support
- Workflow status: WAITING_FOR_HUMAN_INPUT
- Requirements extracted: 18
- By category: {'functional': 6, 'non_functional': 3, 'data': 3, 'constraint': 1, 'security': 2, 'business_rule': 2, 'integration': 1}
- By classification: {'SOURCE_BACKED': 11, 'ASSUMPTION': 2, 'CLARIFICATION_BACKED': 5}
- SOURCE_BACKED citation rate: 100%
- Clarification questions: 5
  - By category: {'security': 1, 'non_functional': 1, 'integration': 1, 'data': 1, 'business_rule': 1}
  - By priority: {'High': 5}
- Tool calls (in order): ['get_project_information', 'search_project_documents', 'search_company_standards', 'save_requirements', 'save_clarification_questions']
- Unpermitted tool calls (§20.2 finding if non-empty): []
- Agent call durations:
  - Supervisor (supervisor, EVALUATE_STATE, SUCCESS): 6.0s
  - RequirementAnalyst (requirement_analyst, EXTRACT_REQUIREMENTS, SUCCESS): 656.8s
  - Supervisor (supervisor, EVALUATE_STATE, SUCCESS): 9.0s
