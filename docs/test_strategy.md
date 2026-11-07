# Test strategy

Pricing unit tests exercise decimal arithmetic and rounding without HTTP or database setup. API tests cover request validation, status codes, request identifiers, single-request idempotency handling, confirmation, cancellation of drafts and credit limits. SQL evidence checks stored quote columns, idempotency keys and the credit ledger. Pipeline tests cover redaction and malformed log handling. Integration scenarios run against separate seeded service builds and are used by the evaluator.

The baseline quote service suite intentionally uses single-line pricing, round values, unique request keys and draft-only cancellation. Those gaps let the synthetic defect builds remain green while the investigation pipeline detects the scenarios.
