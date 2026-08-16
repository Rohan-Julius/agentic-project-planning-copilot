# Scenario 3 — Ambiguous Support Assistant: Manually Identified Major Requirements

Unlike scenarios 1-2, this scenario is deliberately ambiguous/contradictory (§23) — a
competent Requirement Analyst is expected to surface items 6-10 as CONTRADICTIONS or
AMBIGUITIES / clarification questions, not extract them as confident settled requirements.
"Major requirements extracted" for this scenario therefore includes both categories below.

## Clear functional/non-functional requirements (should be extracted directly)
1. The assistant answers common customer questions automatically using help center content
2. The assistant hands off a conversation to a human when it cannot help
3. The assistant logs all conversations
4. (NFR, vague) The assistant should respond quickly — no numeric target given, should be
   flagged as ambiguous/needing a clarification question, not invented
5. (NFR, vague) The assistant should be secure — no concrete security requirement given,
   should be flagged as ambiguous, not invented

## Contradictions the analyst must detect (§7.2 task 11)
6. Supported channels: chat widget only (Product session) vs. chat + email + phone IVR
   (Support Ops session)
7. Data retention period: 1 year (Product session) vs. 7 years (Support Ops / Compliance)
8. Launch date: Q2 (Product session) vs. Q3/Q4 (Support Ops session)

## Ambiguities/missing information the analyst must flag (§7.2 task 12, not invent an answer)
9. Escalation routing is unspecified — any agent, a specific escalation team, or the
   customer's original account manager?
10. It is unspecified which role(s) can use the assistant's admin/configuration tools
