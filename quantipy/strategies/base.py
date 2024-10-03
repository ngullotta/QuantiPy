import logging
from collections import defaultdict
from typing import Callable, Deque, Dict, List, Union

from blankly import Strategy
from blankly.exchanges.exchange import Exchange
from blankly.exchanges.interfaces.exchange_interface import ExchangeInterface

Callback = Callable[..., None]
EventCallbacks = Dict[str, List[Callback]]
HistoricalData = Dict[str, Dict[str, Deque]]
Positions = Dict[str, Dict[str, Union[bool, float]]]


def event(event: str) -> Callable:
    def decorator(callback: Callback) -> Callback:
        StrategyBase.register_event_callback(event, callback)
        return callback

    return decorator


class StrategyBase(Strategy):

    logger: logging.RootLogger = logging.getLogger()
    data: HistoricalData = defaultdict(dict)
    positions: Positions = defaultdict(dict)
    callbacks: EventCallbacks = defaultdict(list)
    blacklist: List[str] = []

    def __init__(self, exchange: Exchange) -> None:
        self.logger.info("Using strategy: %s", self.__class__.__name__)
        super().__init__(exchange)
        self.interface: ExchangeInterface = exchange.interface
        self.preferences = self.interface.user_preferences
        self.settings = self.preferences.get("settings", {})
        self._audit = defaultdict(list)

    @classmethod
    def register_event_callback(cls, event: str, callback: Callback) -> bool:
        if callback not in cls.callbacks[event]:
            cls.callbacks[event].append(callback)
        return callback in cls.callbacks[event]

    def run_callbacks(self, _type: str, *args, **kwargs) -> None:
        # This is the worst thing I've ever written
        # We only want registered callbacks of *this* class and its
        # parent classes as well to be able to be called back.
        # But because I'm a fuckup I made all callbacks register
        # regardless at instantiation time.
        # Why did I use @event decorators with class variables :^)
        # @ToDo -> Fix this nonsense
        for fn in self.callbacks[_type]:
            allowed_classes = [
                base.__name__ for base in self.__class__.__bases__
            ]
            allowed_classes.append(self.__class__.__name__)
            if fn.__qualname__.split(".")[0] in allowed_classes:
                fn(self, *args, **kwargs)

    def buy(self) -> bool:
        return False

    def sell(self) -> bool:
        return False
