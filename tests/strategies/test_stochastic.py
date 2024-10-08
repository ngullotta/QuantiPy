from pathlib import Path

import numpy as np
import pytest
from blankly import KeylessExchange
from blankly.data.data_reader import PriceReader
from blankly.indicators import rsi
from pandas import read_csv

from quantipy.strategies.stochastic import AdvancedHarmonicOscillators

from quantipy.state import TradeState


@pytest.fixture(scope="module", autouse=True)
def data_path() -> Path:
    yield Path(__file__).parent / "data" / "pine_wave_technologies.csv"


@pytest.fixture(scope="module", autouse=True)
def exchange(data_path) -> None:
    yield KeylessExchange(
        price_reader=PriceReader(str(data_path.resolve()), "PWT-USD")
    )


def test_advanced_harmonic_oscillators(data_path, exchange) -> None:
    st = AdvancedHarmonicOscillators(exchange)
    st.callbacks["buy"] = []
    st.callbacks["sell"] = []
    symbol = "PWT-USD"
    data = read_csv(data_path)
    start = data["time"].iloc[0]
    end = data["time"].iloc[-1]
    settings = Path(__file__).parent / "settings.json"
    st.add_price_event(
        st.tick,
        symbol="PWT-USD",
        resolution="1m",
        init=st.init,
    )
    st.backtest(
        start_date=int(end) - 86400,
        end_date=int(end) + 86400,
        initial_values={"USD": 500},
        GUI_output=False,
        settings_path=settings,
    )

    st.manager.state.new(
        "PWT",
        entry=400,
        open=True,
        state=TradeState.LONGING
    )

    st.backtest(
        start_date=int(end) - (86400 * 2),
        end_date=int(end) + (86400 * 2),
        initial_values={"USD": 500},
        GUI_output=False,
        settings_path=settings,
    )