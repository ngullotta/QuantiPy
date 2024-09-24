from blankly import StrategyState
from blankly.indicators import rsi
from blankly.utils import trunc

from quantipy.strategies.simple import SimpleStrategy, event


class Oversold(SimpleStrategy):
    """
    A simple strategy to buy and sell when the RSI hits 30 and 70
    (respecitvely)
    """

    @event("buy")
    def b(self, price: float, symbol: str, state: StrategyState) -> None:
        self.order(price, symbol, state)

    @event("sell")
    def s(self, price: float, symbol: str, state: StrategyState) -> None:
        self.order(price, symbol, state, side="sell")

    def buy(self, symbol: str) -> bool:
        _rsi = rsi(self.data[symbol]["close"])
        return _rsi[-1] <= 30

    def sell(self, symbol: str) -> bool:
        _rsi = rsi(self.data[symbol]["close"])
        return _rsi[-1] >= 70
