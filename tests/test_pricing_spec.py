from decimal import Decimal

from quote_service.pricing import calculate


def test_documented_worked_example():
    result = calculate([{"quantity": 100, "unit_price": "500.00"}, {"quantity": 10, "unit_price": "500.00"}], Decimal("5"))
    assert result["subtotal"] == Decimal("55000.00")
    assert result["discount_amount"] == Decimal("2750.00")
    assert result["taxable_amount"] == Decimal("52250.00")
    assert result["gst_amount"] == Decimal("9405.00")
    assert result["total"] == Decimal("61655.00")
