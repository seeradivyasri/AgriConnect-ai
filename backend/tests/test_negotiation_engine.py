import pytest
from decimal import Decimal
from app.services.negotiation_engine import compute_effective_ceiling, evaluate_ask, round_to_half_step

def test_round_to_half_step():
    assert round_to_half_step(Decimal("39.60")) == Decimal("39.5")
    assert round_to_half_step(Decimal("39.40")) == Decimal("39.0")
    assert round_to_half_step(Decimal("39.90")) == Decimal("39.5")

def test_compute_effective_ceiling():
    # Exact math: 45, 12, "A" -> 39.5
    ep_a = compute_effective_ceiling(Decimal("45"), Decimal("12"), "A")
    assert ep_a == Decimal("39.5")
    
    # Grade B: 45 * 0.88 * 0.90 = 35.64 -> 35.5
    ep_b = compute_effective_ceiling(Decimal("45"), Decimal("12"), "B")
    assert ep_b == Decimal("35.5")

def test_ethical_floor():
    # ask(20) < EP(39.5)*0.60 -> COUNTER 36.0
    ep = Decimal("39.5")
    decision = evaluate_ask(Decimal("20"), Decimal("45"), ep, 1)
    assert decision["action"] == "COUNTER"
    assert decision["counter_price"] == Decimal("36.0")

def test_overbid_r1():
    # ask(50) > EP(39.5), round=1 -> COUNTER 37.5
    ep = Decimal("39.5")
    decision = evaluate_ask(Decimal("50"), Decimal("45"), ep, 1)
    assert decision["action"] == "COUNTER"
    assert decision["counter_price"] == Decimal("37.5")

def test_overbid_r2():
    # ask(50) > EP(39.5), round=2 -> REJECT, ceiling=None
    ep = Decimal("39.5")
    decision = evaluate_ask(Decimal("50"), Decimal("45"), ep, 2)
    assert decision["action"] == "REJECT"
    assert decision["ceiling_shown"] is None

def test_reverse_bid_r2():
    # ask(38) <= EP(39.5), round=2 -> COUNTER 36.5
    ep = Decimal("39.5")
    decision = evaluate_ask(Decimal("38"), Decimal("45"), ep, 2)
    assert decision["action"] == "COUNTER"
    assert decision["counter_price"] == Decimal("36.5")

def test_valid_bid_r1():
    # ask(38) <= EP(39.5), round=1 -> ACCEPT 38.0
    ep = Decimal("39.5")
    decision = evaluate_ask(Decimal("38"), Decimal("45"), ep, 1)
    assert decision["action"] == "ACCEPT"
    assert decision["final_price"] == Decimal("38.0")

def test_round_over_2():
    # round 3 overbid -> HARD REJECT
    ep = Decimal("39.5")
    decision = evaluate_ask(Decimal("50"), Decimal("45"), ep, 3)
    assert decision["action"] == "REJECT"
    assert decision["ceiling_shown"] == Decimal("39.5")
