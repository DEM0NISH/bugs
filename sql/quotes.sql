SELECT id,buyer_id,status,subtotal,discount_percent,discount_amount,taxable_amount,gst_amount,total,idempotency_key FROM quotes WHERE idempotency_key = ?
