import numpy as np
from blankly import StrategyState
from blankly.indicators import rsi

from quantipy.strategies.simple import SimpleStrategy, event


class Oversold(SimpleStrategy):
    """
    A simple strategy to buy and sell when the RSI hits 30 and 70
    (respecitvely)
    """

    @event("buy")
    def b(self, price: float, symbol: str, state: StrategyState) -> float:
        return self.order(price, symbol, state)

    @event("sell")
    def s(self, price: float, symbol: str, state: StrategyState) -> float:
        return self.order(price, symbol, state, side="sell")

    def buy(self, symbol: str) -> bool:
        _rsi: np.array = rsi(self.data[symbol]["close"])
        return _rsi[-1] <= 30

    def sell(self, symbol: str) -> bool:
        _rsi: np.array = rsi(self.data[symbol]["close"])
        return _rsi[-1] >= 70
