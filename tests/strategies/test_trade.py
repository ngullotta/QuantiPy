import time
from uuid import uuid4

import pytest
from blankly.exchanges.orders.market_order import MarketOrder
from blankly.exchanges.orders.order import Order

from quantipy.trade import TradeManager
from quantipy.state import TradeState


class MockInterface:

    def __init__(self) -> None:
        self.account = {}
        self.cash = 1000
        self.price = 10

    def market_order(self, symbol, side, size) -> dict:
        self.cash -= self.price * size
        order = MarketOrder(
            None,
            {
                "id": str(uuid4()),
                "price": self.price * size,
                "size": size,
                "symbol": symbol,
                "side": side,
                "type": "market",
                "time_in_force": "GTC",
                "created_at": int(time.time()),
                "status": "done",
            },
            MockState(),
        )
        order.get_status = lambda: "done"
        return order


class MockState:
    def __init__(self) -> None:
        self.interface = MockInterface()
        self.base_asset = "FOO"

    def get_exchange_type(self) -> str:
        return "mock"


def test_trade_manager_order_long():
    state = MockState()
    manager = TradeManager()
    position = manager.order(state.interface.price, "FOO", state)
    assert position.open
    assert position.symbol == "FOO"
    assert position.state == TradeState.LONGING
    # We mock the price to a fixed $ amount, need to ensure the
    # entry matches
    assert position.entry == state.interface.price

    stop_loss = manager.default_stop_loss_pct
    risk_ratio = manager.default_risk_ratio
    assert position.stop_loss == (position.entry * (1 - stop_loss))
    assert position.take_profit == (
        position.entry * (1 + stop_loss * risk_ratio)
    )

    assert manager.state.get(state.base_asset) is position

def test_trade_manager_order_short():
    state = MockState()
    manager = TradeManager()
    position = manager.order(state.interface.price, "FOO", state, side="sell")

    assert position.open
    assert position.symbol == "FOO"
    assert position.state == TradeState.SHORTING
    # We mock the price to a fixed $ amount, need to ensure the
    # entry matches
    assert position.entry == state.interface.price

    stop_loss = manager.default_stop_loss_pct
    risk_ratio = manager.default_risk_ratio
    assert position.stop_loss == (position.entry * (1 + stop_loss))
    assert position.take_profit == (
        position.entry * (1 - stop_loss * risk_ratio)
    )

    assert manager.state.get(state.base_asset) is position
