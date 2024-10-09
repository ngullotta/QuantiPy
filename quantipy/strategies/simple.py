from collections import defaultdict
from datetime import datetime
from typing import Union

from blankly import ScreenerState, StrategyState

from quantipy.position import Position
from quantipy.strategies.base import StrategyBase, event
from quantipy.strategies.split_protector import SplitProtector
from quantipy.trade import TradeManager


class SimpleStrategy(StrategyBase):
    """
    A simple strategy base.

    The SimpleStrategy class is a good starting point for basic
    strategy testing.

    It provides (among other things) basic facilities for:
      - Initializing symbol data
      - Appending new price data on each tick
      - Taking basic long positions
      - Position state management
      - Doing risk management calculations for quantities
      - Handling buy and sell signals
      - Simple conversion into "screener"
        - A screener just informs about buy/sell signals on tracked
        symbols instead of actually handling trades
      - An audit log to profile the accuracy of your strategy
      - Protecting against stock splits (when backtesting)
      - Avoiding blacklisted symbols (niche)

    Things it cannot do:
      - Short selling
    """

    protector: SplitProtector = SplitProtector("splits.json")

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.manager = TradeManager()
        self._audit_log = defaultdict(list)

    def init(self, symbol: str, state: StrategyState) -> None:
        self.data[symbol] = state.interface.history(
            symbol, to=800, resolution=state.resolution, return_as="deque"
        )

    @event("tick")
    def append_close(
        self, price: float, symbol: str, state: StrategyState
    ) -> None:
        self.data[symbol]["close"].append(price)

    def safe(self, symbol: str) -> bool:
        if symbol in self.blacklist:
            return False

        # Avoid splits when backtesting
        return self.protector.safe(symbol, self.time())

    def tick(self, price: float, symbol: str, state: StrategyState) -> None:
        args: tuple = (price, symbol, state)

        self.run_callbacks("tick", *args)

        position: Union[Position, None] = self.manager.state.get(
            state.base_asset
        )

        if not self.safe(symbol):
            if position is not None and position.open:
                self.manager.close(position, state)
            return

        if (position is not None and position.open) and self.sell(symbol):
            self.run_callbacks("sell", *args)
        elif (position is None or not position.open) and self.buy(symbol):
            self.run_callbacks("buy", *args)

    def screener(self, symbol: str, state: ScreenerState) -> dict:
        self.data[symbol] = state.interface.history(
            symbol, 800, resolution=state.resolution, return_as="deque"
        )
        return {"buy": self.buy(symbol)}

    def audit(self, symbol: str, event: str, message: str, **kwargs) -> None:
        obj = {
            "time": int(self.time()),
            "date_string": datetime.fromtimestamp(int(self.time())).strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            "event": event,
            "message": message,
        }

        obj.update(**kwargs)

        self._audit_log[symbol].append(obj)
