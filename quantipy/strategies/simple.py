from datetime import datetime

from blankly import ScreenerState, StrategyState
from blankly.exchanges.orders.market_order import MarketOrder
from blankly.utils import trunc

from quantipy.strategies.base import StrategyBase, event
from quantipy.strategies.split_protector import SplitProtector


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

        # Avoid splits when backtesting
        if not self.safe(symbol):
            # If we have an open position, exit it immediately
            if self.positions[symbol].get("open"):
                self.run_callbacks("sell", *args)
            return

        if self.positions[symbol].get("open") and self.sell(symbol):
            self.run_callbacks("sell", *args)
        elif not self.positions[symbol].get("open") and self.buy(symbol):
            self.run_callbacks("buy", *args)

    @staticmethod
    def order_to_str(order: MarketOrder) -> str:
        data: dict = order.get_response()
        return "(%s) [%s] %.8f of -> %s" % (
            int(data["created_at"]),
            data["side"],
            data["size"],
            data["symbol"],
        )

    def get_quantity(
        self,
        price: float,
        symbol: str,
        state: StrategyState,
        pct: float = 0.01,
        stop_loss: float = 0.05,
        precision: int = 4,
    ) -> float:
        if self.positions[symbol].get("open"):
            return trunc(
                state.interface.account[state.base_asset].available, precision
            )
        # Risk management I guess?
        # Cash = Risk amount / Stop loss percentage
        cash = (state.interface.cash * pct) / stop_loss
        return trunc(cash / price, precision)

    def order(
        self,
        price: float,
        symbol: str,
        state: StrategyState,
        side: str = "buy",
        pct: float = 0.01,
        stop_loss: float = 0.05,
    ) -> float:
        quantity: float = self.get_quantity(
            price, symbol, state, pct=pct, stop_loss=stop_loss
        )

        if not quantity:
            return 0.0

        # Do the actual order now
        order: MarketOrder = state.interface.market_order(
            symbol, side=side, size=quantity
        )

        data: dict = order.get_response()
        self.logger.info(self.order_to_str(order))

        # Record our new position
        self.positions[symbol]["open"]: bool = (
            side == "buy" and data["status"] == "done"
        )

        self.positions[symbol]["entry"] = price

        return quantity

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

        # self._audit[symbol].append(obj)
