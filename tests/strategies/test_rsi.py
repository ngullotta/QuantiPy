from pathlib import Path
from unittest.mock import MagicMock

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


def test_buy_and_sell_fns(exchange) -> None:
    st = Oversold(exchange)
    symbol = "PWT-USD"
    st.manager.order = lambda _, __, ___: 42
    state = MagicMock()
    state.base_asset = "PWT"
    assert st.b(1, symbol, None) == 42
    st.manager.order = lambda _, __, ___, side: 42
    assert st.s(1, symbol, None) == 42
