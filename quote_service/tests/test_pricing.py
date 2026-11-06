from decimal import Decimal

import pytest

from quote_service.pricing import calculate, money


@pytest.mark.parametrize(("quantity", "price", "discount", "total"), [(1, "10.00", "0", "11.80"), (1, "10.00", "20", "9.44"), (3, "15.50", "10", "49.38"), (2, "100.00", "5", "224.20")])
def test_pricing_round_number_cases(quantity, price, discount, total):
    result = calculate([{"quantity": quantity, "unit_price": price}], Decimal(discount))
    assert result["total"] == Decimal(total)


@pytest.mark.parametrize("value,expected", [("1.005", "1.01"), ("1.004", "1.00"), ("-1.005", "-1.01")])
def test_money_uses_half_up(value, expected):
    assert money(Decimal(value)) == Decimal(expected)


