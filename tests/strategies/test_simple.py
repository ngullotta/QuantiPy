from pathlib import Path

import pytest

from blankly import KeylessExchange
from blankly.data.data_reader import PriceReader

from quantipy.strategies.simple import SimpleStrategy


@pytest.fixture(scope="module", autouse=True)
def exchange() -> None:
    data = Path(__file__).parent / "data" / "pine_wave_technologies.csv"
    yield KeylessExchange(price_reader=PriceReader(str(data.resolve()), 'PWT-USD'))


def test_simple_strategy_buy(exchange) -> None:
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
    st.backtest(to="1d", initial_values={"USD": 500}, GUI_output=False, settings_path=settings)
    assert signal

def test_simple_strategy_sell(exchange) -> None:
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
    st.backtest(to="1d", initial_values={"PWT": 50, "USD": 0}, GUI_output=False, settings_path=settings)
    assert signal