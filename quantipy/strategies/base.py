import logging
from collections import defaultdict
from typing import Callable, Dict, List

from blankly import ScreenerState, Strategy, StrategyState
from blankly.exchanges.abc_base_exchange import ABCBaseExchange
from blankly.exchanges.orders.market_order import MarketOrder

Callback = Callable[..., None]
StrategyCallback = Dict[str, List[Callback]]


class StrategyBase(Strategy):

    logger = logging.getLogger()

    def __init__(
        self,
        exchange: ABCBaseExchange,
        to: str = "1y",
    ) -> None:
        super().__init__(exchange)
        self.default_history = to
        self.data = defaultdict(dict)
        self.positions = defaultdict(bool)

        self.callbacks: StrategyCallback = {
            "buy": [],
            "sell": [],
            "tick": [],
            "stop_loss": [],
            "take_profit": [],
        }

        self.register_on_tick_callback(self.append_price)

        self.logger.info("Using strategy: %s", self.__class__.__name__)

    def log_order(self, price: float, order: MarketOrder) -> None:
        status = order.get_status()
        side, symbol, size = status["side"], status["symbol"], status["size"]
        self.logger.info(
            "[%s]: %s @ %.2f (qty=%.2f) (total=%.2f)",
            side,
            symbol,
            price,
            size,
            price * size,
        )

    def screener(self, symbol: str, state: ScreenerState) -> None:
        state.resolution = "1d"
        prices = state.interface.history(
            symbol, 40, resolution=state.resolution, return_as="deque"
        )
        self.data[symbol]["close"] = prices["close"]
        price = state.interface.get_price(symbol)
        return {"symbol": symbol, "buy": self.buy(symbol), "price": price}

    def formatter(self, results: List[dict], state: ScreenerState):
        # results is a dictionary on a per symbol basis
        result_string = "These are all the stocks that are currently oversold: \n"
        for symbol in results:
            if results[symbol]["buy"]:
                result_string += "{} is currently oversold at a price of {}\n\n".format(
                    symbol, results[symbol]["price"]
                )
        return result_string

    def append_price(self, price: float, symbol: str, state: StrategyState) -> None:
        self.data[symbol]["close"].append(price)
        self.logger.debug("Added close price to `%s`'s history: $%.2f", symbol, price)

    def init(self, symbol: str, state: StrategyState):
        self.data[symbol] = state.interface.history(
            symbol, to=800, resolution=state.resolution, return_as="deque"
        )

    def register_callback(self, _type: str, callback: Callback) -> bool:
        if _type not in self.callbacks:
            self.callbacks[_type] = []
        if callback not in self.callbacks[_type]:
            self.callbacks[_type].append(callback)
        return callback in self.callbacks[_type]

    def register_on_buy_callback(self, callback: Callback) -> bool:
        return self.register_callback("buy", callback)

    def register_on_sell_callback(self, callback: Callback) -> bool:
        return self.register_callback("sell", callback)

    def register_on_tick_callback(self, callback: Callback) -> bool:
        return self.register_callback("tick", callback)

    def on_event(self, price: float, symbol: str, state: StrategyState) -> None:
        for fn in self.callbacks["tick"]:
            fn(price, symbol, state)

        if self.positions[symbol] and self.sell(symbol):
            for fn in self.callbacks["sell"]:
                fn(price, symbol, state)
        elif not self.positions[symbol] and self.buy(symbol):
            for fn in self.callbacks["buy"]:
                fn(price, symbol, state)

    def buy(self, symbol: str) -> bool:
        return False

    def sell(self, symbol: str) -> bool:
        return False
