SELECT buyer_id,quote_id,entry_type,amount FROM credit_ledger WHERE quote_id IN (SELECT id FROM quotes WHERE idempotency_key = ?)
