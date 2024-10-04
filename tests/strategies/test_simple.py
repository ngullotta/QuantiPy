from pathlib import Path

import pytest
from blankly import KeylessExchange
from blankly.data.data_reader import PriceReader
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
