import math
from pathlib import Path
from time import time
from unittest.mock import MagicMock

import pytest
from blankly import KeylessExchange, StrategyState
from blankly.data.data_reader import PriceReader
from blankly.exchanges.orders.market_order import MarketOrder
from pandas import read_csv

from quantipy.position import Position
from quantipy.state import TradeState
from quantipy.strategies.advanced import AdvancedStrategy, event


class TestStrategy(AdvancedStrategy):
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


def make_state(strategy: AdvancedStrategy, symbol: str) -> StrategyState:
    resolution = strategy.interface.interface.resolution
    return StrategyState(strategy, {}, symbol, resolution=resolution)


def test_advanced_strategy_buy_sell_signals(exchange):
    strategy = TestStrategy(exchange)
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


def test_advanced_long_take_profit(exchange):
    strategy = AdvancedStrategy(exchange)
    symbol = "FOO-USD"
    state = make_state(strategy, symbol)
    base, _ = symbol.split("-")
    original = strategy.manager.state.new(
        base,
        open=True,
        size=1,
        entry=42,
        take_profit=100,
        state=TradeState.LONGING,
        full_symbol=symbol,
    )
    strategy.take_profit(original.take_profit + 1, base, state)
    position = strategy.manager.state.get(base)
    assert not position.open
    assert position.symbol == base
    assert position.state == TradeState.CLOSED


def test_advanced_long_stop_loss(exchange):
    strategy = AdvancedStrategy(exchange)
    symbol = "FOO-USD"
    state = make_state(strategy, symbol)
    base, _ = symbol.split("-")
    original = strategy.manager.state.new(
        base,
        open=True,
        size=1,
        entry=42,
        stop_loss=30,
        state=TradeState.LONGING,
        full_symbol=symbol,
    )
    strategy.stop_loss(original.stop_loss - 1, base, state)
    position = strategy.manager.state.get(base)
    assert not position.open
    assert position.symbol == base
    assert position.state == TradeState.CLOSED


def test_advanced_trailing_stop_loss_increments(exchange):
    strategy = AdvancedStrategy(exchange)
    symbol = "FOO-USD"
    state = make_state(strategy, symbol)
    base, _ = symbol.split("-")
    original = strategy.manager.state.new(
        base,
        open=True,
        size=1,
        entry=42,
        stop_loss=42 * (1 - strategy.STOP_LOSS_PCT),
        state=TradeState.LONGING,
        full_symbol=symbol,
    )
    # Not enough to trigger a stop loss, but enough to move it up
    price = original.entry + 1
    strategy.stop_loss(price, base, state)
    position = strategy.manager.state.get(base)
    assert position.stop_loss == (price * (1 - strategy.STOP_LOSS_PCT))

    # Same for shorts but in reverse
    original = strategy.manager.state.new(
        base,
        open=True,
        size=1,
        entry=42,
        stop_loss=42 * (1 + strategy.STOP_LOSS_PCT),
        state=TradeState.SHORTING,
        full_symbol=symbol,
    )
    price = original.entry - 1
    strategy.stop_loss(price, base, state)
    position = strategy.manager.state.get(base)
    assert position.stop_loss == (price * (1 + strategy.STOP_LOSS_PCT))


def test_advanced_avoids_blacklist(exchange):
    strategy = AdvancedStrategy(exchange)
    symbol = "FOO-USD"
    strategy.blacklist.append(symbol)
    assert not strategy.safe(symbol)
    strategy.blacklist.pop()
    assert strategy.safe(symbol)


def test_advanced_avoids_split_times(exchange):
    strategy = AdvancedStrategy(exchange)
    symbol = "FOO-USD"
    strategy.protector.data[symbol] = [
        {"start": 0, "end": int(time()) + 86400}
    ]
    assert not strategy.safe(symbol)
    strategy.protector.data[symbol][0]["end"] = 1
    assert strategy.safe(symbol)


def test_advanced_sells_on_unsafe(exchange) -> None:
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


def advanced_tick_buy(exchange):
    pass
    # st = AdvancedStrategy(exchange)
    # symbol = "FOO"
    # st.data[symbol]["close"] = []
    # state = StrategyState(st, {}, symbol)

    # st.buy = lambda symbol: True

    # def go_long(self, price, symbol, state) -> Position:
    #     return self.manager.state.new(
    #         symbol, entry=price, state=TradeState.LONGING, open=True
    #     )

    # st.register_event_callback("buy", go_long)

    # # Regular
    # st.tick(42, symbol, state)
    # position = st.manager.state.get(symbol)
    # assert position.open
    # assert position.entry == 42
    # assert position.state == TradeState.LONGING

    # st.manager.state.positions.pop(symbol)
    # position = st.manager.state.new(
    #     symbol, open=False, state=TradeState.CLOSED
    # )

    # # Position in past, but closed
    # st.tick(42, symbol, state)
    # position = st.manager.state.get(symbol)
    # assert position.open
    # assert position.entry == 42
    # assert position.state == TradeState.LONGING

    # # Short buyback
    # def close_short(self, price, symbol, state) -> Position:
    #     return self.manager.state.new(symbol, state=TradeState.CLOSED)

    # st.callbacks["buy"] = []
    # st.callbacks["tick"] = []
    # st.register_event_callback("buy", close_short)

    # st.manager.state.positions.pop(symbol)
    # position = st.manager.state.new(
    #     symbol, open=True, state=TradeState.SHORTING, entry=42
    # )

    # st.tick(42, symbol, state)
    # position = st.manager.state.get(symbol)
    # assert not position.open
    # assert position.state == TradeState.CLOSED


def advanced_tick_sell(exchange):
    st = AdvancedStrategy(exchange)
    symbol = "FOO"
    st.data[symbol]["close"] = []
    state = StrategyState(st, {}, symbol)

    st.buy = lambda symbol: False
    st.sell = lambda symbol: True

    def go_short(self, price, symbol, state) -> Position:
        return self.manager.state.new(
            symbol, entry=price, state=TradeState.SHORTING, open=True
        )

    st.register_event_callback("sell", go_short)

    # Short selling
    position = st.manager.state.new(
        symbol,
        open=False,
        state=TradeState.CLOSED,
    )
    st.tick(42, symbol, state)
    position = st.manager.state.get(symbol)
    assert position.open
    assert position.entry == 42
    assert position.state == TradeState.SHORTING

    # Closing a long
    def close_long(self, price, symbol, state) -> Position:
        return self.manager.state.new(
            symbol, state=TradeState.CLOSED, open=False
        )

    st.callbacks["sell"] = []
    st.callbacks["tick"] = []
    st.register_event_callback("sell", close_long)
    st.manager.state.positions.pop(symbol)
    position = st.manager.state.new(
        symbol,
        entry=42,
        open=True,
        state=TradeState.LONGING,
    )
    st.tick(42, symbol, state)
    position = st.manager.state.get(symbol)
    assert not position.open
    assert position.state == TradeState.CLOSED
