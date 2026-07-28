# Leave Management System — Business Requirements

## 1. Overview
HR wants a system for employees to request leave, managers to approve or reject requests,
and HR to track leave balances and generate basic reports. This replaces the current
spreadsheet-based process.

## 2. Actors
- **Employee**: submits leave requests, views their own leave balance and history.
- **Manager**: approves or rejects leave requests submitted by their direct reports.
- **HR Administrator**: configures the holiday calendar, adjusts leave balances, and runs
  reports.

## 3. Functional Requirements

### 3.1 Leave requests
- An employee must be able to submit a leave request specifying a start date, end date, and
  leave type (annual, sick, unpaid).
- The system must reject a leave request if the requested dates overlap an existing approved
  request for the same employee.
- An employee must be able to cancel a pending (not-yet-approved) leave request.

### 3.2 Manager approval
- A manager must be able to view all pending leave requests from their direct reports.
- A manager must be able to approve or reject a pending leave request, optionally with a
  comment.
- The employee must receive a notification when their request is approved or rejected.

### 3.3 Leave balance
- Each employee has an annual leave balance of 20 days per calendar year, accrued monthly
  (1.67 days/month).
- Sick leave is tracked separately from annual leave and does not require pre-approval, but
  does require manager acknowledgement after the fact.
- The system must prevent an employee from submitting an annual leave request that would take
  their balance below zero.

### 3.4 Holiday calendar
- HR Administrators must be able to configure a company-wide public holiday calendar per
  year.
- Public holidays falling within a requested leave range must not be deducted from the
  employee's leave balance.

### 3.5 Notifications
- The system must notify a manager by email when a new leave request is submitted by one of
  their direct reports.
- The system must notify an employee by email when their request status changes.

### 3.6 Reporting
- HR Administrators must be able to generate a report of leave taken per employee for a given
  date range.
- HR Administrators must be able to generate a report of current leave balances for all
  employees.

## 4. Non-Functional Requirements
- The system must support at least 500 concurrent employee users.
- Leave balance calculations must be accurate to within 0 days of discrepancy (no rounding
  errors that accumulate over a year).
- All leave request and approval actions must be logged for audit purposes, retained for 3
  years.

## 5. Constraints
- The system must integrate with the existing company Single Sign-On (SAML 2.0) for
  authentication.
- The system must be accessible via desktop web browser; mobile is not required for the
  initial release.

## 6. Assumptions
- Public holidays are the same for all employees in the initial release (no per-region
  calendars).
- Leave requests are always submitted by the employee themselves, not on their behalf by a
  manager or HR.
