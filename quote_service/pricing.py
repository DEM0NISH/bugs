from decimal import Decimal, ROUND_HALF_UP


CENT = Decimal("0.01")
GST_RATE = Decimal("0.18")


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def calculate(lines: list[dict], discount_percent: Decimal) -> dict[str, Decimal]:
    line_amounts = [money(Decimal(str(line["quantity"])) * Decimal(str(line["unit_price"]))) for line in lines]
    subtotal = money(sum(line_amounts, Decimal("0.00")))
    discount_amount = money(subtotal * discount_percent / Decimal("100"))
    taxable_amount = money(subtotal - discount_amount)
    gst_amount = money(taxable_amount * GST_RATE)
    return {
        "subtotal": subtotal,
        "discount_amount": discount_amount,
        "taxable_amount": taxable_amount,
        "gst_amount": gst_amount,
        "total": money(taxable_amount + gst_amount),
    }
