# Scenario 1 — Leave Management: Manually Identified Major Requirements

1. Employee submits a leave request (start date, end date, leave type: annual/sick/unpaid)
2. System rejects a leave request that overlaps an existing approved request for that employee
3. Employee can cancel a pending (not-yet-approved) leave request
4. Manager views all pending leave requests from their direct reports
5. Manager approves or rejects a pending request, optionally with a comment
6. Employee is notified when their request is approved or rejected
7. Annual leave balance is 20 days/year, accrued monthly at 1.67 days/month
8. Sick leave is tracked separately, requires no pre-approval, but requires manager
   acknowledgement after the fact
9. System prevents an annual leave request that would take balance below zero
10. HR Administrator configures a company-wide public holiday calendar per year
11. Public holidays within a requested leave range are not deducted from balance
12. Manager is notified by email when a new leave request is submitted
13. Employee is notified by email when their request status changes
14. HR generates a report of leave taken per employee for a given date range
15. HR generates a report of current leave balances for all employees
16. (NFR) System supports at least 500 concurrent employee users
17. (NFR) Leave balance calculations must have zero cumulative rounding drift
18. (NFR) All leave request/approval actions are logged for audit, retained 3 years
19. (Constraint) Integrates with existing company SSO (SAML 2.0)
20. (Constraint) Desktop web only for initial release; mobile not required
