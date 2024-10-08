import math
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from blankly import KeylessExchange, StrategyState
from blankly.data.data_reader import PriceReader
from blankly.exchanges.orders.market_order import MarketOrder
from pandas import read_csv

from quantipy.state import TradeState
from quantipy.position import Position
from quantipy.strategies.advanced import AdvancedStrategy


def get_one_day_start_end(path: Path) -> tuple:
    data = read_csv(path)
    end = int(data["time"].iloc[-1])
    return end - 86400, end


@pytest.fixture(scope="module", autouse=True)
def data_path() -> Path:
    yield Path(__file__).parent / "data" / "pine_wave_technologies.csv"


@pytest.fixture(scope="module", autouse=True)
def exchange(data_path) -> None:
    yield KeylessExchange(
        price_reader=PriceReader(str(data_path.resolve()), "PWT-USD")
    )


def test_simple_strategy_buy_sell_signal(data_path, exchange) -> None:
    signal = False

    def buy(symbol):
        nonlocal signal
        if not signal:
            signal = True
            return signal
        return False

    st = AdvancedStrategy(exchange)
    assert not st.buy()
    st.buy = buy
    st.add_price_event(
        st.tick,
        symbol="PWT-USD",
        resolution="1m",
        init=st.init,
    )
    settings = Path(__file__).parent / "settings.json"
    start, end = get_one_day_start_end(data_path)
    st.backtest(
        start_date=start,
        end_date=end,
        initial_values={"USD": 500},
        GUI_output=False,
        settings_path=settings,
    )
    assert signal

    signal = False

    def sell(symbol):
        nonlocal signal
        if not signal:
            signal = True
            return signal
        return False

    assert not st.sell()

    st.buy = lambda symbol: False
    st.sell = sell

    st.manager.state.new(
        "PWT",
        state=TradeState.CLOSED,
        open=False
    )

    st.backtest(
        start_date=start,
        end_date=end,
        initial_values={"USD": 500},
        GUI_output=False,
        settings_path=settings,
    )

    assert signal


def test_advanced_take_profit(exchange) -> None:
    st = AdvancedStrategy(exchange)
    symbol = "FOO"
    st.manager._order = lambda sym, sid, qty, ste: True
    position = st.manager.state.new(
        symbol,
        open=True,
        size=1,
        entry=42,
        take_profit=100,
        state=TradeState.LONGING,
    )
    state = StrategyState(st, {}, symbol)
    st.take_profit(101, symbol, state)
    assert st.manager.state.get(symbol).state == TradeState.CLOSED

    st.manager.state.positions.pop(symbol)

    position = st.manager.state.new(
        symbol,
        open=True,
        size=1,
        entry=42,
        take_profit=30,
        state=TradeState.SHORTING,
    )

    state = StrategyState(st, {}, symbol)
    st.take_profit(29, symbol, state)
    assert st.manager.state.get(symbol).state == TradeState.CLOSED


def test_advanced_stop_loss(exchange) -> None:
    st = AdvancedStrategy(exchange)
    symbol = "FOO"
    st.manager._order = lambda sym, sid, qty, ste: True
    position = st.manager.state.new(
        symbol,
        open=True,
        size=1,
        entry=42,
        stop_loss=30,
        state=TradeState.LONGING,
    )
    state = StrategyState(st, {}, symbol)
    st.stop_loss(29, symbol, state)
    assert st.manager.state.get(symbol).state == TradeState.CLOSED

    st.manager.state.positions.pop(symbol)

    position = st.manager.state.new(
        symbol,
        open=True,
        size=1,
        entry=42,
        stop_loss=50,
        state=TradeState.SHORTING,
    )

    state = StrategyState(st, {}, symbol)
    st.stop_loss(51, symbol, state)
    assert st.manager.state.get(symbol).state == TradeState.CLOSED


def test_advanced_trailing_stop_loss_increments(exchange):
    st = AdvancedStrategy(exchange)
    symbol = "FOO"
    st.manager._order = lambda sym, sid, qty, ste: True
    position = st.manager.state.new(
        symbol,
        open=True,
        size=1,
        entry=42,
        stop_loss=30,
        state=TradeState.LONGING,
    )
    state = StrategyState(st, {}, symbol)
    new_price = 43
    st.stop_loss(new_price, symbol, state)
    position = st.manager.state.get(symbol)
    assert position.stop_loss == (new_price * (1 - st.STOP_LOSS_PCT))

    st.manager.state.positions.pop(symbol)

    position = st.manager.state.new(
        symbol,
        open=True,
        size=1,
        entry=42,
        stop_loss=50,
        state=TradeState.SHORTING,
    )

    state = StrategyState(st, {}, symbol)
    new_price = 41
    st.stop_loss(new_price, symbol, state)
    position = st.manager.state.get(symbol)
    assert position.stop_loss == (new_price * (1 + st.STOP_LOSS_PCT))


def test_advanced_avoids_blacklist(exchange) -> None:
    st = AdvancedStrategy(exchange)
    symbol = "FOO"
    st.blacklist.append(symbol)
    st.data[symbol]["close"] = []
    assert not st.safe(symbol)
    state = StrategyState(st, {}, symbol)
    st.tick(42, symbol, state)


def test_advanced_tick_buy(exchange):
    st = AdvancedStrategy(exchange)
    symbol = "FOO"
    st.data[symbol]["close"] = []
    state = StrategyState(st, {}, symbol)

    st.buy = lambda symbol: True

    def go_long(self, price, symbol, state) -> Position:
        return self.manager.state.new(
            symbol,
            entry=price,
            state=TradeState.LONGING,
            open=True
        )

    st.register_event_callback("buy", go_long)

    # Regular
    st.tick(42, symbol, state)
    position = st.manager.state.get(symbol)
    assert position.open
    assert position.entry == 42
    assert position.state == TradeState.LONGING

    st.manager.state.positions.pop(symbol)
    position = st.manager.state.new(
        symbol, 
        open=False, 
        state=TradeState.CLOSED
    )

    # Position in past, but closed
    st.tick(42, symbol, state)
    position = st.manager.state.get(symbol)
    assert position.open
    assert position.entry == 42
    assert position.state == TradeState.LONGING


    # Short buyback
    def close_short(self, price, symbol, state) -> Position:
        return self.manager.state.new(
            symbol,
            state=TradeState.CLOSED
        )

    st.callbacks["buy"] = []
    st.callbacks["tick"] = []
    st.register_event_callback("buy", close_short)

    st.manager.state.positions.pop(symbol)
    position = st.manager.state.new(
        symbol, 
        open=True, 
        state=TradeState.SHORTING,
        entry=42
    )

    st.tick(42, symbol, state)
    position = st.manager.state.get(symbol)
    assert not position.open
    assert position.state == TradeState.CLOSED


def test_advanced_tick_sell(exchange):
    st = AdvancedStrategy(exchange)
    symbol = "FOO"
    st.data[symbol]["close"] = []
    state = StrategyState(st, {}, symbol)

    st.buy = lambda symbol: False
    st.sell = lambda symbol: True

    def go_short(self, price, symbol, state) -> Position:
        return self.manager.state.new(
            symbol,
            entry=price,
            state=TradeState.SHORTING,
            open=True
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
            symbol,
            state=TradeState.CLOSED,
            open=False
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