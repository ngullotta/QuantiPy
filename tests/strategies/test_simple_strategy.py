import json
from time import time
from unittest.mock import MagicMock

import pytest
from blankly import StrategyState

from quantipy.position import Position
from quantipy.state import TradeState
from quantipy.strategies.simple import SimpleStrategy, event


class TestStrategy(SimpleStrategy):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._enable_buy = False
        self._enable_sell = False

    def _dummy_init(self, symbol: str) -> None:
        self.data[symbol]["close"] = []

    def enable_buying(self, yn: bool = True) -> None:
        self._enable_buy = yn

    def enable_selling(self, yn: bool = True) -> None:
        self._enable_sell = yn

    @property
    def buying_enabled(self) -> bool:
        return self._enable_buy

    @property
    def selling_enabled(self) -> bool:
        return self._enable_sell

    def reset(self) -> None:
        self._enable_buy = False
        self._enable_sell = False

    @event("buy")
    def b(self, price: float, symbol: str, state: StrategyState) -> Position:
        return self.manager.order(price, symbol, state)

    @event("sell")
    def s(self, price: float, symbol: str, state: StrategyState) -> Position:
        return self.manager.order(price, symbol, state, side="sell")

    def buy(self, symbol: str) -> bool:
        if self.buying_enabled:
            return True

    def sell(self, symbol: str) -> bool:
        if self.selling_enabled:
            return True


def make_state(strategy: SimpleStrategy, symbol: str) -> StrategyState:
    resolution = strategy.interface.interface.resolution
    return StrategyState(strategy, {}, symbol, resolution=resolution)


def test_simple_strategy_buy(exchange):
    strategy = TestStrategy(exchange)
    # This is overwritten somewhere, need to track this down
    # For now just re-register the buy function
    strategy.register_event_callback("buy", TestStrategy.b)
    strategy.register_event_callback("sell", TestStrategy.s)
    strategy.enable_buying()
    resolution = exchange.interface.resolution
    settings = strategy.interface.interface._settings_path
    for symbol in ["FOO-USD"]:
        base, quote = symbol.split("-")
        data = exchange.interface._price_data[symbol][resolution]
        start, end = data["time"].iloc[-3:-1]
        price = strategy.interface.interface.get_price(symbol, time=start)
        strategy.add_price_event(
            strategy.tick,
            symbol=symbol,
            resolution=resolution,
            init=strategy.init,
        )
        strategy.backtest(
            start_date=start,
            end_date=end,
            initial_values={base: 0, quote: 1000},
            GUI_output=False,
            settings_path=settings,
        )
        position = strategy.manager.state.get(base)
        assert position.open
        assert position.full_symbol == symbol
        assert position.symbol == base
        assert position.state == TradeState.LONGING
        assert position.entry == price
        # Should we check for quantity here? Don't feel like importing
        # and creating a StrategyState for this
        # assert position.size == expected
        assert position.stop_loss == price * (
            1 - strategy.manager.default_stop_loss_pct
        )
        assert position.take_profit == price * (
            1
            + (
                strategy.manager.default_stop_loss_pct
                * strategy.manager.default_risk_ratio
            )
        )

        # Now the sell side. We already have a position to work with
        strategy.enable_buying(False)
        strategy.enable_selling()
        strategy.backtest(
            start_date=start,
            end_date=end,
            initial_values={base: 0, quote: 1000},
            GUI_output=False,
            settings_path=settings,
        )
        position = strategy.manager.state.get(base)
        assert not position.open
        assert position.symbol == base
        assert position.state == TradeState.CLOSED
        strategy.reset()


def test_simple_avoids_blacklist(exchange) -> None:
    strategy = TestStrategy(exchange)
    symbol = "FOO-USD"
    strategy.blacklist.append(symbol)
    assert not strategy.safe(symbol)
    strategy.blacklist.pop()
    assert strategy.safe(symbol)


def test_simple_avoids_split_times(exchange) -> None:
    strategy = SimpleStrategy(exchange)
    symbol = "FOO-USD"
    strategy.protector.data[symbol] = [
        {"start": 0, "end": int(time()) + 86400}
    ]
    assert not strategy.safe(symbol)
    strategy.protector.data[symbol][0]["end"] = 1
    assert strategy.safe(symbol)


def test_simple_sells_on_unsafe(exchange) -> None:
    strategy = TestStrategy(exchange)
    symbol = "FOO-USD"
    strategy._dummy_init(symbol)
    state = make_state(strategy, symbol)
    base, _ = symbol.split("-")
    strategy.manager.state.new(
        base,
        open=True,
        size=1,
        entry=42,
        stop_loss=30,
        state=TradeState.LONGING,
        full_symbol=symbol,
    )
    strategy.blacklist.append(symbol)
    strategy.tick(42, symbol, state)
    position = strategy.manager.state.get(base)
    assert not position.open
    assert position.symbol == base
    assert position.state == TradeState.CLOSED


def test_audit_log(exchange) -> None:
    # Stub for now
    strategy = SimpleStrategy(exchange)
    strategy.audit("foo", "bar", "baz qux quux")
    assert len(strategy._audit_log["foo"]) == 1


def test_simple_screener(exchange) -> None:
    strategy = TestStrategy(exchange)
    strategy.enable_buying()
    symbol = "FOO-USD"
    state = make_state(strategy, symbol)
    result = strategy.screener(symbol, state)
    assert result == {"buy": True}
