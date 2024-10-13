from unittest.mock import MagicMock

import pytest

from quantipy.strategies.simple import SimpleStrategy


class TestStrategy(SimpleStrategy):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._buy_signal_hit = False
        self._sell_signal_hit = False

    def reset(self) -> None:
        self._buy_signal_hit = False
        self._sell_signal_hit = False

    def buy(self, symbol: str) -> bool:
        self._buy_signal_hit = True
        return True

    def sell(self, symbol: str) -> bool:
        self._sell_signal_hit = True
        return True


@pytest.fixture
def settings(tmp_path):
    CONTENT = "{}"
    path = tmp_path / "settings.json"
    path.write_text(CONTENT)
    yield path


def test_simple_strategy_buy(exchange, settings):
    strategy = TestStrategy(exchange)
    resolution = exchange.interface.resolution
    for symbol in ["FOO-USD"]:
        base, quote = symbol.split("-")
        strategy.add_price_event(
            strategy.tick,
            symbol=symbol,
            resolution=resolution,
            init=strategy.init,
        )
        data = exchange.interface._price_data[symbol][resolution]
        start, end = data["time"].astype(int).iloc[-2:]
        strategy.backtest(
            start_date=start,
            end_date=end,
            initial_values={base: 0, quote: 1000},
            GUI_output=False,
            settings_path=str(settings.resolve()),
        )
        assert strategy._buy_signal_hit
        strategy.reset()


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
    st.manager.state.new("PWT", open=True, entry=42)
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

    def cb(pos, state):
        nonlocal hit
        hit = True

    st.callbacks["tick"] = []
    st.register_event_callback("sell", cb)

    # This will need to change when I shift to trademanager in simple
    st.manager.state.new(symbol, open=True, entry=42)

    state = MagicMock()
    state.base_asset = symbol
    st.manager.close = cb
    st.tick(10, symbol, state)

    assert hit


def test_audit_log(exchange) -> None:
    # Stub for now
    st = SimpleStrategy(exchange)
    st.audit("FOO", "BAR", "Baz qux quux.")
    assert len(st._audit_log["FOO"]) == 1


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
