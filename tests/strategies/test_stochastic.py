import math
from pathlib import Path
from random import uniform
from typing import List
from unittest.mock import MagicMock

import numpy as np
import pytest
from blankly import KeylessExchange, StrategyState
from blankly.data.data_reader import PriceReader
from pandas import Series, read_csv
from ta.momentum import RSIIndicator, StochRSIIndicator
from ta.trend import MACD

from quantipy.position import Position
from quantipy.state import TradeState
from quantipy.strategies.stochastic import AdvancedHarmonicOscillators, event


# fmt: off
BUY_DATA = [148.772012725778,127.75644285338879,71.48580326501973,183.5389649265939,17.75500112198094,142.6318888223258,165.68017372943567,147.0243719096652,197.49130248072117,157.08242253125897,126.69844097064676,47.86275740196344,161.33108977612076,111.30549826938017,183.47406260346128,119.26025642503899,79.03173532330977,81.31982748682083,196.9310488675943,132.26261327963087,71.98023770566414,127.8017734341947,40.59298895205494,88.09025628660324,14.858608521042658,193.83394605842307,116.07246032850098,27.34190513356574,59.71622208768774,43.59477794089548,110.7052002466568,143.06591955410875,166.15735291801616,156.98309085205497,81.90560021889513,177.44474205714744,189.58590069738636,115.59246677835522,54.61260689896678,72.74141447153946,169.5208185145544,195.3058583029298,61.686493208169885,118.35268978381343,199.34913168095986,180.49492191303995,43.40378616814278,63.4190916333923,111.82767200232368,51.41947886024478,32.305517355506126,184.45747119516855,151.63603803901418,73.9010345255736,195.19240386291378]
SELL_DATA = [150.1711598520398,151.39659289584532,153.16953978632327,148.156015888139,149.40900883564242,149.45247154852555,150.6345164564205,148.88669613726574,151.1543397062021,147.43274386765776,149.85095577160163,147.60264615135367,148.2596341450477,147.19445095405428,150.10929255460593,148.81679629540778,149.9709701887269,147.5775505159841,149.13759342958426,150.51598107876785,149.6432108841069,149.3846702317482,150.71261296229517,149.41661566524243,148.8667492815256,147.10389444633398,149.35440576412378,150.35836432661168,147.81942083854105,148.7733518285701,150.16817704222342,148.58382025127833,147.4499648025456,148.60675156576357,149.99297266427763,148.85168734706195,149.86031819209393,147.50646865275615,148.7699804073646,150.18657161165743,149.9255801822988,147.76370899610532,150.0473894849154,148.37063817140802,149.74134113115423,149.8101300529563,148.744598863966,150.6745242767679,147.3792288108792,149.9983724437073,149.30693993751913,148.42735706065037,147.48501918705819,146.8779568630653,146.96222853046558,148.73372605558,148.72049482511608,149.69377521763067,149.71975674728822,148.76476153117144,148.82174485716706,149.55961355725628,149.36088740752695,148.28401112865265,149.8946495839877,149.05047544595277,148.68546635400418,149.32293416453086,147.8161698556732,149.50813433186926,147.672492350447,148.73792673372165,149.40120861445516,150.56601652010477,150.3459765854059,148.63249584799854,148.58458848867065,149.88094004687505,150.66792402000104,150.59690779054827,147.39918028056658,149.60451061079272,149.35188792385387,148.8423201895444,149.2455986408128,148.44819689341628,148.95651594149953,147.0913766634608,150.11231693509964,147.747784966478,149.13552009890418,150.54989472898228,150.3518614360442,150.8481880645744,150.13601826606086,150.27453156312237,150.37476167112874,149.57055835788637,147.47687899248834,148.4167238074049]
# fmt: on


class TestStrategy(AdvancedHarmonicOscillators):
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
            return super().buy(symbol)
        return False

    def sell(self, symbol: str) -> bool:
        if self.selling_enabled:
            return super().sell(symbol)
        return False


def make_state(
    strategy: AdvancedHarmonicOscillators, symbol: str
) -> StrategyState:
    resolution = strategy.interface.interface.resolution
    return StrategyState(strategy, {}, symbol, resolution=resolution)


def test_advanced_harmonic_oscillators_buy_signal(exchange):
    strategy = TestStrategy(exchange)
    strategy.enable_buying()
    symbol = "FOO-USD"
    strategy.data[symbol]["close"] = BUY_DATA
    assert strategy.buy(symbol)


def test_advanced_harmonic_oscillators_sell_signal(exchange):
    strategy = TestStrategy(exchange)
    strategy.enable_selling()
    symbol = "FOO-USD"
    strategy.data[symbol]["close"] = SELL_DATA
    assert strategy.sell(symbol)


def advanced_harmonic_oscillators_inssuficent_data(exchange):
    pass
    # st = AdvancedHarmonicOscillators(exchange)
    # st.callbacks["buy"] = []
    # st.callbacks["sell"] = []
    # symbol = "PWT-USD"
    # st.STRIDE = 0xFFFFFFFFF
    # st.data[symbol]["close"] = list(
    #     np.cumsum(np.random.uniform(-1, -0.5, 100))
    # )
    # assert not st.buy(symbol)
    # assert not st.sell(symbol)
