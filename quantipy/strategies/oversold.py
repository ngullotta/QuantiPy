from blankly import ScreenerState, StrategyState
from blankly.indicators import rsi
from blankly.utils import trunc

from quantipy.strategies.base import StrategyBase


class RSIOversold(StrategyBase):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.register_on_buy_callback(self.on_buy)
        self.register_on_sell_callback(self.on_sell)

    def on_buy(self, price: float, symbol: str, state: StrategyState) -> None:
        qty = trunc(state.interface.cash / price, 3)
        state.interface.market_order(symbol, side="buy", size=qty)
        self.position_open = True

    def on_sell(self, price: float, symbol: str, state: StrategyState) -> None:
        qty = trunc(state.interface.account[state.base_asset].available, 3)
        state.interface.market_order(symbol, side="sell", size=qty)
        self.position_open = False

    def buy(self, symbol: str) -> bool:
        _rsi = rsi(self.data[symbol]["close"])
        return _rsi[-1] < 30

    def sell(self, symbol: str) -> bool:
        _rsi = rsi(self.data[symbol]["close"])
        return _rsi[-1] > 70
