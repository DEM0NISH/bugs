SELECT quote_lines.quote_id,quote_lines.quantity,quote_lines.unit_price FROM quote_lines JOIN quotes ON quotes.id=quote_lines.quote_id WHERE quotes.idempotency_key = ?
