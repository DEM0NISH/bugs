# Quote to credit risk register

| Risk | Likelihood | Impact | Mitigation | Test coverage |
| --- | --- | --- | --- | --- |
| Discount omitted from a multi-line quote | Medium | High | Recompute discount and total from event values | BT-01 investigation |
| GST rounded per line | Medium | Medium | Apply GST to the discounted subtotal once | Pricing unit tests and BT-02 |
| Retry creates duplicate quote | Medium | High | Persist idempotency key with a uniqueness constraint | Quote persistence and BT-03 |
| Credit reservation exceeds limit | Low | High | Check available credit before confirming | Credit limit API test |
| Cancelled confirmed quote retains reservation | Medium | High | Write a release ledger entry in the same transaction | BT-04 investigation |
| Evidence contains personal or credential data | Low | High | Redact each evidence payload before storage and display | Redaction pattern tests |
