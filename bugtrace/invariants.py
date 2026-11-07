from decimal import Decimal, ROUND_HALF_UP

from bugtrace.models import EvidenceItem, InvariantResult


CENT = Decimal("0.01")
GST_RATE = Decimal("0.18")


def rounded(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def check(items: list[EvidenceItem]) -> list[InvariantResult]:
    results = []
    events = [item for item in items if item.source == "log"]
    pricing = {item.content.get("event"): item for item in events}
    pricing_names = ("pricing.subtotal", "pricing.discount", "pricing.tax", "pricing.total")
    pricing_ids = [pricing[name].id for name in pricing_names if name in pricing]
    if all(name in pricing for name in pricing_names):
        subtotal_event = pricing["pricing.subtotal"].content["data"]
        subtotal = rounded(sum((Decimal(str(line["quantity"])) * Decimal(str(line["unit_price"])) for line in subtotal_event.get("lines", [])), Decimal("0.00")))
        logged_subtotal = Decimal(str(subtotal_event["amount"]))
        discount_event = pricing["pricing.discount"].content["data"]
        discount = rounded(logged_subtotal * Decimal(str(discount_event["percent"])) / Decimal("100"))
        taxable = rounded(logged_subtotal - discount)
        tax_event = pricing["pricing.tax"].content["data"]
        tax = rounded(taxable * Decimal(str(tax_event["rate"])))
        total = rounded(taxable + tax)
        valid = subtotal == logged_subtotal and discount == Decimal(str(discount_event["amount"])) and taxable == Decimal(str(tax_event["taxable_amount"])) and tax == Decimal(str(tax_event["amount"])) and total == Decimal(str(pricing["pricing.total"].content["data"]["amount"]))
        results.append(InvariantResult(invariant_id="pricing_math", passed=valid, summary="Logged line inputs and pricing stages match the specification." if valid else "Logged line inputs or pricing stages do not match the specification.", evidence_ids=pricing_ids))
    query_data = {}
    for item in items:
        if item.source == "sql":
            query_data[item.content.get("query")] = (item.content.get("rows", []), item.id)
    quote_rows, quote_id = query_data.get("quotes.sql", ([], ""))
    line_rows, line_id = query_data.get("quote_lines.sql", ([], ""))
    ledger_rows, ledger_id = query_data.get("credit.sql", ([], ""))
    buyer_rows, buyer_id = query_data.get("buyers.sql", ([], ""))
    if query_data:
        keys = [row.get("idempotency_key") for row in quote_rows]
        unique = len(keys) == len(set(keys))
        results.append(InvariantResult(invariant_id="idempotency_uniqueness", passed=unique, summary="Each idempotency key maps to at most one quote." if unique else "An idempotency key maps to multiple quotes.", evidence_ids=[quote_id] if quote_id else []))
        lines_by_quote = {}
        for row in line_rows:
            lines_by_quote.setdefault(row["quote_id"], []).append(row)
        pricing_valid = True
        for row in quote_rows:
            line_subtotal = rounded(sum((Decimal(str(line["quantity"])) * Decimal(str(line["unit_price"])) for line in lines_by_quote.get(row["id"], [])), Decimal("0.00")))
            stored_subtotal = Decimal(str(row["subtotal"]))
            percent = Decimal(str(row["discount_percent"]))
            discount = rounded(line_subtotal * percent / Decimal("100"))
            taxable = rounded(line_subtotal - discount)
            tax = rounded(taxable * GST_RATE)
            total = rounded(taxable + tax)
            pricing_valid = pricing_valid and line_subtotal == stored_subtotal and discount == Decimal(str(row["discount_amount"])) and taxable == Decimal(str(row["taxable_amount"])) and tax == Decimal(str(row["gst_amount"])) and total == Decimal(str(row["total"]))
        results.append(InvariantResult(invariant_id="stored_pricing_math", passed=pricing_valid, summary="Stored quote columns agree with line items and the specification." if pricing_valid else "Stored quote columns do not agree with line items and the specification.", evidence_ids=[item for item in (quote_id, line_id) if item]))
        buyer_balances = {row["id"]: Decimal(str(row["credit_reserved"])) for row in buyer_rows}
        ledger_balances = {}
        ledger_by_quote = {}
        for row in ledger_rows:
            amount = Decimal(str(row["amount"])) * (Decimal("1") if row["entry_type"] == "reserve" else Decimal("-1"))
            ledger_balances[row["buyer_id"]] = ledger_balances.get(row["buyer_id"], Decimal("0")) + amount
            ledger_by_quote.setdefault(row["quote_id"], set()).add(row["entry_type"])
        balance_valid = all(buyer_balances.get(buyer, Decimal("0")) == amount for buyer, amount in ledger_balances.items())
        cancelled_confirmed = [row["id"] for row in quote_rows if row.get("status") == "cancelled" and "reserve" in ledger_by_quote.get(row["id"], set())]
        releases_present = all("release" in ledger_by_quote.get(quote_id, set()) for quote_id in cancelled_confirmed)
        credit_valid = balance_valid and releases_present
        results.append(InvariantResult(invariant_id="credit_ledger_balance", passed=credit_valid, summary="Reserved credit matches ledger entries and confirmed cancellations release credit." if credit_valid else "Reserved credit and ledger entries do not balance, or a confirmed cancellation has no release.", evidence_ids=[item for item in (buyer_id, ledger_id, quote_id) if item]))
    return results
