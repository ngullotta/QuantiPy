import time
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from blankly.exchanges.orders.market_order import MarketOrder
from blankly.exchanges.orders.order import Order
from blankly.utils.exceptions import InvalidOrder

from quantipy.position import Position
from quantipy.state import TradeState
from quantipy.trade import TradeManager


class AttrDict(dict):
    def __init__(self, *args, **kwargs):
        super(AttrDict, self).__init__(*args, **kwargs)
        self.__dict__ = self


class MockInterface:

    def __init__(self) -> None:
        self.account = {}
        self.cash = 1000
        self.price = 10

    def market_order(self, symbol, side, size) -> dict:
        if side == "sell":
            self.cash += self.price * size
        else:
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
        self.account[symbol] = AttrDict(available=size)
        order.get_status = lambda: {"status": "done", "symbol": symbol}
        return order


class MockState:
    def __init__(self) -> None:
        self.interface = MockInterface()
        self.base_asset = "FOO"
        self.strategy = MagicMock()

    def get_exchange_type(self) -> str:
        return "mock"


def test_trade_manager_order_long():
    state = MockState()
    cash = state.interface.cash
    manager = TradeManager()

    def dummyaudit(*args, **kwargs):
        pass

    state.strategy.audit = dummyaudit
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

    assert cash > state.interface.cash
    assert state.interface.cash == cash - (position.entry * position.size)

    cash = state.interface.cash

    old_pos = position
    position = manager.order(state.interface.price, "FOO", state)

    assert not position.open
    assert position.symbol
    assert position.state == TradeState.CLOSED

    # We gain money from a regular sale
    assert cash < state.interface.cash
    assert state.interface.cash == cash + (old_pos.entry * old_pos.size)


def test_trade_manager_order_short():
    state = MockState()
    cash = state.interface.cash
    manager = TradeManager()

    def dummyaudit(*args, **kwargs):
        pass

    state.strategy.audit = dummyaudit
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

    # Because this is a short we actually gain money
    assert cash < state.interface.cash
    assert state.interface.cash == cash + (position.entry * position.size)


def test_trade_manager_order_close():
    state = MockState()
    cash = state.interface.cash
    manager = TradeManager()
    pos1 = manager.state.new(
        "FOO", entry=10, size=1, state=TradeState.LONGING, open=True
    )
    position = manager.close(pos1, state)

    assert not position.open
    assert position.symbol
    assert position.state == TradeState.CLOSED

    # We gain money from a regular sale
    assert cash < state.interface.cash
    assert state.interface.cash == cash + (pos1.entry * pos1.size)

    pos2 = manager.state.new(
        "FOO", entry=10, size=1, state=TradeState.SHORTING, open=True
    )
    position = manager.close(pos2, state)

    # note no check for cash here because our mock doesn't understand
    # shorts
    assert not position.open
    assert position.symbol
    assert position.state == TradeState.CLOSED

    pos2 = manager.state.new(
        "FOO", entry=10, size=1, state=TradeState.SHORTING, open=False
    )
    position = manager.close(pos2, state)
    assert position == Position()


def test_order_zero_size(caplog) -> None:
    state = MockState()
    cash = state.interface.cash
    manager = TradeManager()
    order = manager._order("FOO", "buy", 0, state)
    assert order is None

    for record in caplog.records:
        assert record.levelname == "ERROR"
        assert record.msg != ""


def test_order_invalid(caplog) -> None:
    state = MockState()
    cash = state.interface.cash
    manager = TradeManager()

    msg = "Invalid"

    def error(*args, **kwargs):
        nonlocal msg
        raise InvalidOrder(msg)

    state.interface.market_order = error
    order = manager._order("FOO", "buy", 1, state)
    for record in caplog.records:
        assert record.levelname == "ERROR"
        assert record.msg.args[0] == msg


def test_trade_manager_state_set():
    manager = TradeManager()
    symbol = "FOO"
    pos1 = manager.state.set(symbol, entry=42)
    assert pos1 == Position(symbol, entry=42)
    pos2 = manager.state.set(symbol, entry=100)
    assert pos2.entry == 100
    assert pos1 is not pos2
