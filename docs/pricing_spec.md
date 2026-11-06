# Pricing specification

All money values use decimal arithmetic and round half up to two places.

1. A line amount is quantity multiplied by unit price.
2. Subtotal is the sum of line amounts.
3. A supplier discount from 0 to 20 percent applies to the whole subtotal.
4. GST is 18 percent of the discounted subtotal and is rounded once.
5. Total is the discounted subtotal plus GST.

For two lines of 100 and 10 units at 500.00 each, the subtotal is 55,000.00. A 5 percent discount is 2,750.00. Taxable amount is 52,250.00, GST is 9,405.00 and total is 61,655.00. Without the discount, total is 64,900.00.

For two lines of one unit at 10.25 each with no discount, subtotal is 20.50, GST is 3.69 and total is 24.19. Rounding GST on each line first produces 24.20 and is incorrect.
