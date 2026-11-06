from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from quote_service.main import create_app


@pytest.fixture
def client(tmp_path):
    app = create_app(tmp_path / "quotes.db", tmp_path / "events.jsonl")
    return TestClient(app)


def body(quantity=1, price="100.00", discount=0, buyer="buyer-1"):
    return {"buyer_id": buyer, "discount_percent": discount, "lines": [{"quantity": quantity, "unit_price": price, "description": "sample"}]}


def test_health_is_available(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_request_id_is_echoed(client):
    response = client.post("/quotes", headers={"Idempotency-Key": "one", "X-Request-ID": "trace-one"}, json=body())
    assert response.headers["X-Request-ID"] == "trace-one"


def test_request_id_is_generated_when_missing(client):
    response = client.post("/quotes", headers={"Idempotency-Key": "one"}, json=body())
    assert response.headers["X-Request-ID"]


def test_idempotency_header_is_required(client):
    assert client.post("/quotes", json=body()).status_code == 422


def test_quote_is_persisted_with_expected_values(client):
    response = client.post("/quotes", headers={"Idempotency-Key": "one"}, json=body(price="100.00"))
    assert response.status_code == 200
    assert response.json()["total"] == "118.00"
    stored = client.get(f"/quotes/{response.json()['id']}").json()
    assert stored["subtotal"] == "100.00"


@pytest.mark.parametrize("quantity", [1, 10, 1000])
def test_quantity_boundaries_are_accepted(client, quantity):
    assert client.post("/quotes", headers={"Idempotency-Key": f"qty-{quantity}"}, json=body(quantity=quantity)).status_code == 200


@pytest.mark.parametrize("discount", [0, 5, 20])
def test_allowed_discount_boundaries_are_accepted(client, discount):
    assert client.post("/quotes", headers={"Idempotency-Key": f"discount-{discount}"}, json=body(discount=discount)).status_code == 200


@pytest.mark.parametrize("discount", [-1, 21])
def test_invalid_discount_is_rejected(client, discount):
    assert client.post("/quotes", headers={"Idempotency-Key": f"discount-{discount}"}, json=body(discount=discount)).status_code == 422


@pytest.mark.parametrize("price", ["-0.01", "-10.00"])
def test_negative_price_is_rejected(client, price):
    assert client.post("/quotes", headers={"Idempotency-Key": price}, json=body(price=price)).status_code == 422


def test_empty_lines_are_rejected(client):
    payload = {"buyer_id": "buyer-1", "discount_percent": 0, "lines": []}
    assert client.post("/quotes", headers={"Idempotency-Key": "empty"}, json=payload).status_code == 422


def test_zero_quantity_is_rejected(client):
    assert client.post("/quotes", headers={"Idempotency-Key": "zero"}, json=body(quantity=0)).status_code == 422


def test_unknown_buyer_is_rejected(client):
    assert client.post("/quotes", headers={"Idempotency-Key": "unknown"}, json=body(buyer="missing")).status_code == 404


def test_unknown_quote_is_rejected(client):
    assert client.get("/quotes/missing").status_code == 404


def test_credit_limit_rejects_confirmation(client):
    response = client.post("/quotes", headers={"Idempotency-Key": "large"}, json=body(price="100000.00"))
    assert client.post(f"/quotes/{response.json()['id']}/confirm").status_code == 409


def test_confirmation_reserves_credit(client):
    response = client.post("/quotes", headers={"Idempotency-Key": "confirm"}, json=body())
    quote_id = response.json()["id"]
    assert client.post(f"/quotes/{quote_id}/confirm").json()["status"] == "confirmed"
    credit = client.get("/buyers/buyer-1/credit").json()
    assert Decimal(credit["credit_reserved"]) == Decimal("118.00")


def test_draft_cancellation_succeeds(client):
    response = client.post("/quotes", headers={"Idempotency-Key": "cancel-draft"}, json=body())
    assert client.post(f"/quotes/{response.json()['id']}/cancel").json()["status"] == "cancelled"


def test_unknown_buyer_credit_is_rejected(client):
    assert client.get("/buyers/missing/credit").status_code == 404


def test_request_events_are_written_as_json_lines(client, tmp_path):
    log_path = tmp_path / "events.jsonl"
    test_client = TestClient(create_app(tmp_path / "logs.db", log_path))
    test_client.post("/quotes", headers={"Idempotency-Key": "logs", "X-Request-ID": "logs-request"}, json=body())
    lines = [line for line in log_path.read_text(encoding="utf-8").splitlines() if line]
    assert any('"event": "pricing.total"' in line for line in lines)
    assert any('"request_id": "logs-request"' in line for line in lines)
