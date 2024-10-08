import math
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from blankly import KeylessExchange, StrategyState
from blankly.data.data_reader import PriceReader
from blankly.exchanges.orders.market_order import MarketOrder
from pandas import read_csv

from quantipy.strategies.simple import SimpleStrategy


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


def test_simple_strategy_buy(data_path, exchange) -> None:
    signal = False

    def buy(symbol):
        nonlocal signal
        if not signal:
            signal = True
            return signal
        return False

    st = SimpleStrategy(exchange)
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


def test_simple_strategy_sell(data_path, exchange) -> None:
    signal = False

    def sell(symbol):
        nonlocal signal
        if not signal:
            signal = True
            return signal
        return False

    st = SimpleStrategy(exchange)
    assert not st.sell()
    st.sell = sell
    st.add_price_event(
        st.tick,
        symbol="PWT-USD",
        resolution="1m",
        init=st.init,
    )
    settings = Path(__file__).parent / "settings.json"
    st.positions["PWT-USD"] = {"open": True}
    start, end = get_one_day_start_end(data_path)
    st.backtest(
        start_date=start,
        end_date=end,
        initial_values={"PWT": 50, "USD": 0},
        GUI_output=False,
        settings_path=settings,
    )
    assert signal


def test_simple_avoids_blacklist(exchange) -> None:
    st = SimpleStrategy(exchange)
    symbol = "FOO"
    st.blacklist.append(symbol)
    assert not st.safe(symbol)


def test_simple_avoids_split_times(exchange) -> None:
    st = SimpleStrategy(exchange)
    symbol = "FOO"
    st.protector.data[symbol] = [{"start": -math.inf, "end": math.inf}]
    assert not st.safe(symbol)

    st.protector.data[symbol] = [{"start": 0, "end": 1}]

    assert st.safe(symbol)


def test_simple_avoids_on_tick(exchange) -> None:
    st = SimpleStrategy(exchange)
    symbol = "FOO"
    st.protector.data[symbol] = [{"start": -math.inf, "end": math.inf}]
    hit = False

    def cb(*args, **kwargs):
        nonlocal hit
        hit = True

    st.callbacks["tick"] = []
    st.register_event_callback("sell", cb)

    # This will need to change when I shift to trademanager in simple
    st.positions[symbol] = {"open": True}

    st.tick(10, symbol, None)

    assert hit


def test_order_to_str(exchange):
    st = SimpleStrategy(exchange)
    data = {
        "id": "foo-bar-1234",
        "price": 42,
        "size": 1,
        "symbol": "FOO",
        "side": "buy",
        "type": "market",
        "time_in_force": "GTC",
        "created_at": 42,
        "status": "done",
    }

    class State:
        def get_exchange_type(self):
            return "mock"

    order = MarketOrder(None, data, State())
    string = st.order_to_str(order)

    assert data["symbol"] in string
    ### Fill the rest out later


def test_simple_get_quantity(exchange) -> None:
    st = SimpleStrategy(exchange)
    symbol = "FOO"
    price = 42
    mock = MagicMock()
    mock.interface.cash = 1000

    # (state.interface.cash * pct) / stop_loss
    # default stop_loss = 5%
    # default pct = 1%
    # default precision 4
    qty = st.get_quantity(price, symbol, mock)
    assert qty == round(((mock.interface.cash * 0.01) / 0.05) / price, 4)

    st.positions[symbol] = {"open": True}

    how_many = 100
    mock.interface.account[symbol].available = how_many

    assert st.get_quantity(price, symbol, mock) == how_many


def test_simple_order(exchange) -> None:
    exchange.interface.local_account.override_local_account(
        {"USD": {"available": 1000}}
    )
    st = SimpleStrategy(exchange)
    symbol = "PWT"
    price = 42
    state = StrategyState(st, {}, symbol)
    cash = state.interface.cash

    def market_order(symbol, side, size) -> MarketOrder:
        nonlocal price
        data = {
            "id": "foo-bar-1234",
            "price": price,
            "size": size,
            "symbol": symbol,
            "side": "side",
            "type": "market",
            "time_in_force": "GTC",
            "created_at": 42,
            "status": "done",
        }
        state = MagicMock()
        state.get_exchange_type = lambda: "mock"
        return MarketOrder(None, data, state)

    state.interface.market_order = market_order

    qty = st.order(price, symbol, state)

    assert qty > 0
    assert qty == round(((state.interface.cash * 0.01) / 0.05) / price, 4)


def test_simple_order_zero(exchange) -> None:
    exchange.interface.local_account.override_local_account(
        {"USD": {"available": 0}}
    )
    st = SimpleStrategy(exchange)
    symbol = "PWT"
    price = 42
    state = StrategyState(st, {}, symbol)
    cash = state.interface.cash
    qty = st.order(price, symbol, state)
    assert qty == 0


def test_audit_log(exchange) -> None:
    # Stub for now
    st = SimpleStrategy(exchange)
    st.audit("FOO", "BAR", "Baz qux quux.")


def test_simple_screener(exchange) -> None:
    st = SimpleStrategy(exchange)
    symbol = "PWT-USD"
    state = StrategyState(st, {}, symbol)
    state.resolution = "1m"

    def buy(*args, **kwargs) -> bool:
        return True

    st.buy = buy

    res = st.screener(symbol, state)

    assert res == {"buy": True}


def test_on_tick_append(exchange) -> None:
    st = SimpleStrategy(exchange)
    st.register_event_callback("tick", SimpleStrategy.append_close)
    symbol = "PWT-USD"
    state = StrategyState(st, {}, symbol)
    state.resolution = "1m"
    st.init(symbol, state)
    price = 42
    st.data[symbol]["close"] = [100 for _ in range(100)]
    args = (price, symbol, state)
    st.run_callbacks("tick", *args)
    assert st.data[symbol]["close"][-1] == price