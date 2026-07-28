# Customer Support Assistant — Business Requirements

## 1. Overview
The company wants an AI-assisted customer support tool to help handle incoming customer
questions faster. Meeting notes from two different stakeholder sessions are combined below;
they were not reconciled before this document was written.

## 2. Meeting Notes — Product session (2026-03-02)
- The assistant should be fast and responsive so customers don't get frustrated waiting for
  an answer.
- Customers should be able to reach support through the website chat widget.
- All conversation data must be retained for at least 1 year in case of disputes.
- We're targeting a launch in Q2 alongside the new website redesign.
- Security is important — we should make sure the assistant is secure and doesn't leak
  anything it shouldn't.

## 3. Meeting Notes — Support Ops session (2026-03-09)
- Agents want the assistant to also be available over email and the existing phone IVR
  system, not just chat.
- Compliance told us conversation transcripts need to be retained for 7 years for regulatory
  reasons, not 1 year.
- The assistant should handle the request, but a human agent should always be able to take
  over — need to figure out who exactly gets escalated conversations (is it any agent, a
  specific escalation team, or the customer's original account manager?).
- We can't commit to a Q2 launch — the escalation workflow alone will take longer than that,
  more realistically Q3 or Q4.

## 4. Functional Requirements (as currently understood)
- The assistant must answer common customer questions automatically using existing help
  center content.
- The assistant must be able to hand off a conversation to a human when it cannot help.
- The assistant must log all conversations.

## 5. Non-Functional Requirements (as currently understood)
- The assistant should respond quickly.
- The assistant should be secure.

## 6. Open Items
- Supported channels are not finalized (chat only, or chat + email + phone IVR?).
- Data retention period is disputed (1 year vs. 7 years).
- Launch date is disputed (Q2 vs. Q3/Q4).
- It is not specified which role(s) can use the assistant's admin/configuration tools, or who
  receives escalated conversations.
