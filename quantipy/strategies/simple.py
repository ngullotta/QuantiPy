from blankly import StrategyState
from blankly.exchanges.orders.market_order import MarketOrder
from blankly.utils import trunc

from quantipy.strategies.base import StrategyBase, event


class SimpleStrategy(StrategyBase):
    def init(self, symbol: str, state: StrategyState):
        self.data[symbol] = state.interface.history(
            symbol, to=800, resolution=state.resolution, return_as="deque"
        )

    @event("tick")
    def append_close(self, price: float, symbol: str, state: StrategyState) -> None:
        if not price:
            return
        self.data[symbol]["close"].append(price)

    def tick(self, price: float, symbol: str, state: StrategyState) -> None:
        args = [price, symbol, state]

        self.run_callbacks("tick", *args)

        if self.positions[symbol] and self.sell(symbol):
            self.run_callbacks("sell", *args)
        elif not self.positions[symbol] and self.buy(symbol):
            self.run_callbacks("buy", *args)

    @property
    def cash(self) -> float:
        return self.interface.cash

    @staticmethod
    def order_to_str(order: MarketOrder) -> str:
        data = order.get_response()
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
        side="buy",
        pct: float = 1,
    ) -> float:
        quantity = trunc(
            (
                ((self.cash * pct) / price)
                if side == "buy"
                else state.interface.account[state.base_asset].available
            ),
            4,
        )
        if not quantity:
            return
        order = state.interface.market_order(symbol, side=side, size=quantity)
        data = order.get_response()
        self.logger.info(self.order_to_str(order))
        self.positions[symbol] = (side == "buy") and (data["status"] == "done")
        return quantity
