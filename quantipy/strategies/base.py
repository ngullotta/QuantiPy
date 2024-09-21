import logging
from collections import deque
from typing import Callable, Dict, List

from blankly import Strategy, StrategyState
from blankly.exchanges.abc_base_exchange import ABCBaseExchange

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
        self.data = deque()

        self.position_open = False

        self.callbacks: StrategyCallback = {
            "buy": [],
            "sell": [],
            "tick": [],
            "stop_loss": [],
            "take_profit": [],
        }

        self.register_on_tick_callback(lambda p, _, __: self.data["close"].append(p))

        self.logger.info("Using strategy: %s", self.__class__.__name__)

    def init(self, symbol: str, state: StrategyState):
        self.data = state.interface.history(
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

        if self.position_open and self.sell():
            for fn in self.callbacks["sell"]:
                fn(price, symbol, state)
        elif not self.position_open and self.buy():
            for fn in self.callbacks["buy"]:
                fn(price, symbol, state)

    def buy(self) -> bool:
        return False

    def sell(self) -> bool:
        return False
