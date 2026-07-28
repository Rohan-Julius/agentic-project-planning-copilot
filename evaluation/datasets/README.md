# Evaluation Datasets (spec §23)

Three synthetic project scenarios, each a standalone Markdown requirements document meant to
be uploaded as a single project document and run through the full agentic pipeline.

| Scenario | Directory | Purpose (§23) |
|---|---|---|
| 1. Leave management | `scenario_1_leave_management/` | Standard requirement extraction and planning — few ambiguities, tests the "happy path". |
| 2. E-commerce payment integration | `scenario_2_ecommerce_payments/` | Integrations, dependencies, risks, and non-functional requirements. |
| 3. Ambiguous customer-support assistant | `scenario_3_ambiguous_support/` | Deliberately contains missing roles, an undefined response-time target, conflicting retention periods (1 year vs. 7 years), unspecified channels, vague security requirements, and conflicting launch dates — tests clarification-question generation and contradiction detection. |

`tests/integration/test_pipeline_smoke.py` drives scenario 1 through the entire workflow
(upload → index → analysis → clarification → planning → review → approval → export) as a
smoke test. Days 19–23 (Phase 2) build the full `evaluation/scripts/` harness that runs all
three scenarios against the §24 criteria (extraction coverage, clarification quality,
grounding, plan quality, reviewer effectiveness, repeatability, retrieval).
