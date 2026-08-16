# Scenario 2 — E-Commerce Payments: Manually Identified Major Requirements

1. Customer creates an order and initiates payment for the order total
2. Stripe is the integrated payment provider for card payments
3. A payment record is created in a "pending" state before redirecting to the provider
4. A webhook endpoint receives asynchronous payment status callbacks from Stripe
5. Incoming webhook callbacks are verified via the provider's signature scheme before trust
6. Webhook handling is idempotent — no double-crediting on duplicate/out-of-order delivery
7. A failed payment marks the order "payment failed"; the customer can retry with the same order
8. The provider's failure reason code is recorded for every failed payment attempt
9. A Support Agent can issue a full or partial refund for a completed payment
10. A refund must not exceed the original captured payment amount
11. The customer is notified by email when a refund is issued
12. Every payment state transition is recorded in an immutable, timestamped, actor-attributed
    audit log
13. (NFR) Webhook processing completes within 2 seconds under normal load
14. (NFR) Payment audit log retained 7 years for financial compliance
15. (NFR) System is resilient to Stripe being temporarily unreachable — orders not lost
16. (Constraint) Only Stripe is in scope; no other payment providers required
17. (Constraint) No raw card numbers are stored (PCI-DSS scope reduction via Stripe-hosted entry)
