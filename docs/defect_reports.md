# Synthetic defect reports

## BT-01 Supplier discount omitted

Steps: create a quote with two lines of 100 and 10 units at 500.00 and a 5 percent discount. Expected total is 61,655.00. Actual total is 64,900.00. The pricing event sequence is evidence. Severity: high.

## BT-02 GST rounded by line

Steps: create a quote with two lines of one unit at 10.25 and no discount. Expected total is 24.19. Actual total is 24.20. Pricing events identify the tax mismatch. Severity: medium.

## BT-03 Retry creates a second quote

Steps: submit a quote, then retry the same body with the same Idempotency-Key. Expected: the original quote is returned. Actual: a second quote is persisted. The request events and stored quote rows are evidence. Severity: high.

## BT-04 Credit is not released on cancellation

Steps: create and confirm a quote, then cancel it. Expected: reserved credit returns to its prior balance and a release row is written. Actual: the reservation remains. The credit balance and ledger rows are evidence. Severity: high.
