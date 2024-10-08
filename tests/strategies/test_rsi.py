from pathlib import Path

import numpy as np
import pytest
from blankly import KeylessExchange
from blankly.data.data_reader import PriceReader
from blankly.indicators import rsi

from quantipy.strategies.rsi import Oversold


@pytest.fixture(scope="module", autouse=True)
def data_path() -> Path:
    yield Path(__file__).parent / "data" / "pine_wave_technologies.csv"


@pytest.fixture(scope="module", autouse=True)
def exchange(data_path) -> None:
    yield KeylessExchange(
        price_reader=PriceReader(str(data_path.resolve()), "PWT-USD")
    )


def test_oversold(exchange) -> None:
    st = Oversold(exchange)
    st.callbacks["tick"] = []
    symbol = "PWT-USD"

    data = np.cumsum(np.random.uniform(-1, -0.5, 100))
    _rsi = rsi(data)

    st.data[symbol]["close"] = list(data)
    assert st.buy(symbol)

    data = np.cumsum(np.random.uniform(1, 0.5, 100))
    _rsi = rsi(data)

    st.data[symbol]["close"] = list(data)
    assert st.sell(symbol)
