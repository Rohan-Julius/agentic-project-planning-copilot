# Day 21 Retrieval Evaluation (spec §24.9)

Total queries: 32
Mean latency: 22.8ms

| Query ID | Category | Query | Results | Correct source? | Citation valid? | Latency (ms) |
|---|---|---|---|---|---|---|
| RQ-001 | direct_requirement | annual leave balance days per year | 5 | True | True | 145.2 |
| RQ-002 | direct_requirement | manager approval of leave requests | 5 | True | True | 37.5 |
| RQ-003 | direct_requirement | public holiday calendar configuration | 5 | True | True | 37.9 |
| RQ-004 | direct_requirement | webhook signature verification | 5 | True | True | 15.8 |
| RQ-005 | direct_requirement | refund amount cannot exceed captured payment | 5 | True | True | 23.5 |
| RQ-006 | direct_requirement | PCI-DSS card data storage | 5 | True | True | 27.8 |
| RQ-007 | direct_requirement | assistant hands off to a human agent | 1 | True | True | 18.5 |
| RQ-008 | direct_requirement | assistant logs all conversations | 1 | True | True | 15.1 |
| RQ-009 | company_standard | when is a story ready for sprint planning | 5 | True | True | 18.3 |
| RQ-010 | company_standard | criteria for marking a story done | 5 | True | True | 16.3 |
| RQ-011 | company_standard | user story format template | 5 | True | True | 13.7 |
| RQ-012 | company_standard | storing payment card data securely | 5 | True | True | 15.9 |
| RQ-013 | company_standard | story point estimation scale | 5 | True | True | 13.5 |
| RQ-014 | company_standard | peer review before code is done | 5 | True | True | 14.5 |
| RQ-015 | multi_document | notifications sent to employees and managers | 5 | True | True | 16.9 |
| RQ-016 | multi_document | payment failure handling and retry | 5 | True | True | 15.4 |
| RQ-017 | multi_document | quality expectations for a story | 5 | True | True | 15.2 |
| RQ-018 | metadata_filtered | definition of ready checklist | 1 | True | True | 15.5 |
| RQ-019 | metadata_filtered | security requirements for authentication | 1 | True | True | 13.8 |
| RQ-020 | metadata_filtered | leave request | 5 | True | True | 28.9 |
| RQ-021 | metadata_filtered | estimation | 1 | True | True | 32.8 |
| RQ-022 | no_answer | cryptocurrency payment support | 5 | None | True | 17.6 |
| RQ-023 | no_answer | employee vacation accrual policy | 5 | None | True | 15.5 |
| RQ-024 | no_answer | database schema migration strategy | 1 | None | True | 14.4 |
| RQ-025 | no_answer | office building floor plan | 5 | None | True | 14.2 |
| RQ-026 | conflicting | conversation data retention period | 1 | True | True | 14.5 |
| RQ-027 | conflicting | supported communication channels | 1 | True | True | 30.1 |
| RQ-028 | conflicting | launch date target | 1 | True | True | 14.0 |
| RQ-029 | document_versions | annual leave balance days | 5 | True | True | 14.4 |
| RQ-030 | document_versions | leave accrual per month | 5 | True | True | 15.4 |
| RQ-031 | document_versions | sick leave tracking | 5 | True | True | 14.4 |
| RQ-032 | document_versions | leave request policy | 5 | True | True | 14.6 |

## By category
- **direct_requirement**: 8 queries, 8 correct-source hits
- **company_standard**: 6 queries, 6 correct-source hits
- **multi_document**: 3 queries, 3 correct-source hits
- **metadata_filtered**: 4 queries, 4 correct-source hits
- **no_answer**: 4 queries, 0 correct-source hits
- **conflicting**: 3 queries, 3 correct-source hits
- **document_versions**: 4 queries, 4 correct-source hits