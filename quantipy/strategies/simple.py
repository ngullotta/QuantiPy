from blankly import ScreenerState, StrategyState
from blankly.exchanges.orders.market_order import MarketOrder
from blankly.utils import trunc

from quantipy.strategies.base import StrategyBase, event


class SimpleStrategy(StrategyBase):
    def init(self, symbol: str, state: StrategyState) -> None:
        self.data[symbol] = state.interface.history(
            symbol, to=800, resolution=state.resolution, return_as="deque"
        )

    @event("tick")
    def append_close(
        self, price: float, symbol: str, state: StrategyState
    ) -> None:
        if not price:
            return
        self.data[symbol]["close"].append(price)

    def tick(self, price: float, symbol: str, state: StrategyState) -> None:
        args: tuple = (price, symbol, state)

        self.run_callbacks("tick", *args)

        if symbol in self.blacklist:
            return

        if self.positions[symbol] and self.sell(symbol):
            self.run_callbacks("sell", *args)
        elif not self.positions[symbol] and self.buy(symbol):
            self.run_callbacks("buy", *args)

    @property
    def cash(self) -> float:
        return self.interface.cash

    @property
    def account(self) -> dict:
        return self.interface.account

    @staticmethod
    def order_to_str(order: MarketOrder) -> str:
        data: dict = order.get_response()
        return "(%s) [%s] %.2f of -> %s" % (
            int(data["created_at"]),
            data["side"],
            data["size"],
            data["symbol"],
        )

    def order(
        self,
        price: float,
        symbol: str,
        state: StrategyState,
        side: str = "buy",
        pct: float = 1.0,
    ) -> float:
        # If we're buying divide our cash (or percentage of cash) by
        # unit price. Otherwise sell the whole smash
        quantity: float = 0.0
        if side == "buy":
            quantity = (self.cash * pct) / price
        else:
            quantity = self.account[state.base_asset].available

        # Rounding to 4 decimals should be enough for both regular
        # stocks (with fractional shares) and crypto exchanges
        quantity: float = trunc(quantity, 4)

        if not quantity:
            return 0.0

        # Do the actual order now
        order: MarketOrder = state.interface.market_order(
            symbol, side=side, size=quantity
        )

        data: dict = order.get_response()
        self.logger.info(self.order_to_str(order))

        # Record our new position
        self.positions[symbol]: bool = (
            side == "buy" and data["status"] == "done"
        )

        return quantity

    def screener(self, symbol: str, state: ScreenerState) -> dict:
        self.data[symbol] = state.interface.history(
            symbol, 800, resolution=state.resolution, return_as="deque"
        )
        return {"buy": self.buy(symbol)}
