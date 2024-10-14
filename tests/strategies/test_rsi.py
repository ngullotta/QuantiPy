from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest
from blankly import KeylessExchange
from blankly.data.data_reader import PriceReader
from blankly.indicators import rsi

from quantipy.strategies.rsi import Oversold


def test_oversold_signals(exchange) -> None:
    strategy = Oversold(exchange)
    symbol = "FOO-USD"
    strategy.data[symbol]["close"] = list(
        np.cumsum(np.random.uniform(-1, -0.5, 100))
    )
    assert strategy.buy(symbol)
    strategy.data[symbol]["close"] = list(
        np.cumsum(np.random.uniform(1, 0.5, 100))
    )
    assert strategy.sell(symbol)
