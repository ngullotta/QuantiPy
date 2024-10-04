import inspect
import logging
from collections import defaultdict
from typing import List

from blankly import Strategy
from blankly.exchanges.exchange import Exchange

from quantipy.types import (
    Callable,
    Callback,
    EventCallbacks,
    HistoricalData,
    Positions,
)


def event(event: str) -> Callable:
    def decorator(callback: Callback) -> Callback:
        StrategyBase.register_event_callback(event, callback)
        return callback

    return decorator


class StrategyBase(Strategy):
    """
    The base for all QuantiPy strategies.

    The goal of this base is to provide a callback system and registry
    (using the `event` decorator) to allow for quick subclass building.
    All event callbacks are registered in `callbacks`.

    This class also initializes the base `Strategy` class from blankly,
    the logger, position information, symbol blacklist, and symbol
    data.
    """

    logger: logging.RootLogger = logging.getLogger()
    data: HistoricalData = defaultdict(dict)
    positions: Positions = defaultdict(dict)
    callbacks: EventCallbacks = defaultdict(list)
    blacklist: List[str] = []

    def __init__(self, exchange: Exchange) -> None:
        super().__init__(exchange)
        self._clean_callbacks()

    def _clean_callbacks(self) -> None:
        # This is the worst thing I've ever written
        # We only want registered callbacks of *this* class and its
        # parent classes as well to be able to be called back.
        # But because I'm a fuckup I made all callbacks register
        # regardless at instantiation time.
        # Why did I use @event decorators with class variables :^)
        # @ToDo -> Fix this nonsense
        allowed_classes: List[str] = [
            base.__name__ for base in inspect.getmro(self.__class__)
        ]
        to_delete: dict = defaultdict(list)
        for _type, callbacks in self.callbacks.items():
            for callback in callbacks:
                if callback.__qualname__.split(".")[0] not in allowed_classes:
                    to_delete[_type].append(callback)

        for _type, callbacks in to_delete.items():
            for callback in callbacks:
                self.logger.debug(
                    "Removing function `%s` from callbacks",
                    callback.__qualname__,
                )
                index: int = self.callbacks[_type].index(callback)
                del self.callbacks[_type][index]

    @classmethod
    def register_event_callback(cls, event: str, callback: Callback) -> bool:
        if callback not in cls.callbacks[event]:
            cls.callbacks[event].append(callback)
        return callback in cls.callbacks[event]

    def run_callbacks(self, _type: str, *args, **kwargs) -> None:
        for fn in self.callbacks[_type]:
            fn(self, *args, **kwargs)

    def buy(self) -> bool:
        return False

    def sell(self) -> bool:
        return False
