import json
import logging
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request, Response
from pydantic import BaseModel, Field

from quote_service.db import connect, seed
from quote_service.pricing import calculate


class QuoteLine(BaseModel):
    quantity: int = Field(ge=1)
    unit_price: Decimal = Field(ge=0)
    description: str = Field(min_length=1)


class QuoteRequest(BaseModel):
    buyer_id: str
    discount_percent: Decimal = Field(ge=0, le=20)
    lines: list[QuoteLine] = Field(min_length=1)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_app(db_path: str | Path | None = None, log_path: str | Path | None = None) -> FastAPI:
    app = FastAPI(title="Quote Service")
    connection = connect(db_path)
    seed(connection)
    log_file = Path(log_path or os.environ.get("QUOTE_LOG_PATH", ".workspace/quote_service.jsonl"))
    log_file.parent.mkdir(parents=True, exist_ok=True)

    def emit(request_id: str, event: str, data: dict) -> None:
        record = {"ts": now(), "level": "INFO", "request_id": request_id, "event": event, "data": data}
        with log_file.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, default=str) + "\n")

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        emit(request_id, "request.received", {"method": request.method, "path": request.url.path})
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        emit(request_id, "request.completed", {"status_code": response.status_code})
        return response

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/quotes")
    def create_quote(payload: QuoteRequest, response: Response, request: Request, idempotency_key: str = Header(alias="Idempotency-Key")):
        request_id = request.state.request_id
        existing = connection.execute("SELECT quote_id FROM idempotency_keys WHERE key = ?", (idempotency_key,)).fetchone()
        if existing:
            emit(request_id, "idempotency.hit", {"key": idempotency_key, "quote_id": existing["quote_id"]})
            quote = connection.execute("SELECT * FROM quotes WHERE id = ?", (existing["quote_id"],)).fetchone()
            response.status_code = 200
            return dict(quote)
        emit(request_id, "idempotency.miss", {"key": idempotency_key})
        buyer = connection.execute("SELECT id FROM buyers WHERE id = ?", (payload.buyer_id,)).fetchone()
        if not buyer:
            raise HTTPException(404, "Buyer not found")
        line_data = [line.model_dump() for line in payload.lines]
        amounts = calculate(line_data, payload.discount_percent)
        emit(request_id, "pricing.subtotal", {"amount": str(amounts["subtotal"]), "lines": [{"quantity": line.quantity, "unit_price": str(line.unit_price)} for line in payload.lines]})
        emit(request_id, "pricing.discount", {"percent": str(payload.discount_percent), "amount": str(amounts["discount_amount"])})
        emit(request_id, "pricing.tax", {"taxable_amount": str(amounts["taxable_amount"]), "rate": "0.18", "amount": str(amounts["gst_amount"])})
        emit(request_id, "pricing.total", {"amount": str(amounts["total"])})
        quote_id = str(uuid.uuid4())
        created_at = now()
        values = (quote_id, payload.buyer_id, "draft", str(amounts["subtotal"]), str(payload.discount_percent), str(amounts["discount_amount"]), str(amounts["taxable_amount"]), str(amounts["gst_amount"]), str(amounts["total"]), idempotency_key, created_at)
        connection.execute("INSERT INTO quotes VALUES(?,?,?,?,?,?,?,?,?,?,?)", values)
        connection.executemany("INSERT INTO quote_lines(quote_id,quantity,unit_price,description) VALUES(?,?,?,?)", [(quote_id, line.quantity, str(line.unit_price), line.description) for line in payload.lines])
        connection.execute("INSERT INTO idempotency_keys VALUES(?,?,?)", (idempotency_key, quote_id, created_at))
        connection.commit()
        emit(request_id, "quote.persisted", {"quote_id": quote_id, "total": str(amounts["total"])})
        return {"id": quote_id, "buyer_id": payload.buyer_id, "status": "draft", **{key: str(value) for key, value in amounts.items()}, "discount_percent": str(payload.discount_percent), "idempotency_key": idempotency_key}

    @app.get("/quotes/{quote_id}")
    def get_quote(quote_id: str):
        quote = connection.execute("SELECT * FROM quotes WHERE id = ?", (quote_id,)).fetchone()
        if not quote:
            raise HTTPException(404, "Quote not found")
        return dict(quote)

    @app.post("/quotes/{quote_id}/confirm")
    def confirm_quote(quote_id: str, request: Request):
        request_id = request.state.request_id
        quote = connection.execute("SELECT * FROM quotes WHERE id = ?", (quote_id,)).fetchone()
        if not quote:
            raise HTTPException(404, "Quote not found")
        if quote["status"] != "draft":
            raise HTTPException(409, "Quote is not a draft")
        buyer = connection.execute("SELECT * FROM buyers WHERE id = ?", (quote["buyer_id"],)).fetchone()
        total = Decimal(quote["total"])
        if Decimal(buyer["credit_reserved"]) + total > Decimal(buyer["credit_limit"]):
            raise HTTPException(409, "Credit limit exceeded")
        timestamp = now()
        connection.execute("UPDATE buyers SET credit_reserved = ? WHERE id = ?", (str(Decimal(buyer["credit_reserved"]) + total), buyer["id"]))
        connection.execute("UPDATE quotes SET status='confirmed' WHERE id=?", (quote_id,))
        connection.execute("INSERT INTO credit_ledger(buyer_id,quote_id,entry_type,amount,created_at) VALUES(?,?,?,?,?)", (buyer["id"], quote_id, "reserve", str(total), timestamp))
        connection.commit()
        emit(request_id, "credit.reserved", {"quote_id": quote_id, "amount": str(total)})
        return {"id": quote_id, "status": "confirmed", "total": str(total)}

    @app.post("/quotes/{quote_id}/cancel")
    def cancel_quote(quote_id: str, request: Request):
        request_id = request.state.request_id
        quote = connection.execute("SELECT * FROM quotes WHERE id = ?", (quote_id,)).fetchone()
        if not quote:
            raise HTTPException(404, "Quote not found")
        if quote["status"] == "cancelled":
            return {"id": quote_id, "status": "cancelled"}
        if quote["status"] == "confirmed":
            buyer = connection.execute("SELECT * FROM buyers WHERE id = ?", (quote["buyer_id"],)).fetchone()
            pass
        connection.execute("UPDATE quotes SET status='cancelled' WHERE id=?", (quote_id,))
        connection.commit()
        return {"id": quote_id, "status": "cancelled"}

    @app.get("/buyers/{buyer_id}/credit")
    def buyer_credit(buyer_id: str):
        buyer = connection.execute("SELECT id,credit_limit,credit_reserved FROM buyers WHERE id = ?", (buyer_id,)).fetchone()
        if not buyer:
            raise HTTPException(404, "Buyer not found")
        return dict(buyer)

    app.state.connection = connection
    app.state.emit = emit
    return app


app = create_app()
