import logging
import math
from datetime import datetime
from collections import namedtuple
from typing import Dict, Union
from enum import IntEnum, auto

from blankly import ScreenerState, StrategyState
from blankly.exchanges.orders.market_order import MarketOrder
from blankly.utils import trunc

from quantipy.strategies.simple import SimpleStrategy, event

from blankly.exchanges.interfaces.exchange_interface import ExchangeInterface


Position = namedtuple(
    "Position",
    ["state", "open", "entry", "stop_loss", "take_profit"],
)


class TradeState(IntEnum):
    READY_NEXT = auto()
    SHORTING = auto()
    LONGING = auto()


class TradeManager:

    logger = logging.getLogger()

    def __init__(
        self,
        interface: ExchangeInterface,
        risk_ratio: int = 2,
    ) -> None:
        self.interface: ExchangeInterface = interface
        self.positions: Dict[str, Position] = {}

    def new_position(self, symbol: str, **kwargs) -> Position:
        self.positions.pop(symbol, None)
        self.positions[symbol] = Position(**kwargs)
        return self.positions[symbol]

    def update_position(self, symbol: str, **kwargs) -> Union[Position, None]:
        if pos := self.positions.get(symbol):
            self.positions[symbol] = pos._replace(**kwargs)
            return self.positions[symbol]
        return None

    @staticmethod
    def clamp(value: float, _max: float, _min: float) -> float:
        return max(min(value, _max), _min)

    def get_position(self, symbol: str) -> Union[Position, None]:
        return self.positions.get(symbol)

    def state(self, symbol: str) -> Union[TradeState, None]:
        if pos := self.get_position(symbol):
            return pos.state

    @staticmethod
    def order_to_str(order: MarketOrder) -> str:
        data: dict = order.get_response()
        return "(%s) [%s] %.8f of -> %s" % (
            int(data["created_at"]),
            data["side"],
            data["size"],
            data["symbol"],
        )

    def log_order(self, order: MarketOrder) -> None:
        self.logger.info(self.order_to_str(order))

    def get_quantity(
        self,
        price: float,
        symbol: str,
        state: StrategyState,
        pct: float = 0.01,
        stop_loss: float = 0.05,
        precision: int = 4,
    ) -> float:
        pos: Position = self.get_position(state.base_asset)
        base: dict = state.interface.account[state.base_asset]

        # This must just be a regular "long" market order. Calculate
        # the quantity using `Cash = Risk amount / Stop loss percentage`
        if pos is None or not pos.open:
            cash: float = self.clamp(
                (state.interface.cash * pct) / stop_loss,
                state.interface.cash,
                0,
            )
            return trunc(cash / price, precision)

        # We want to buy back the same amount we borrowed
        if pos.state == TradeState.SHORTING:
            return abs(base.available)

        # Otherwise this a regular sell order and we should sell it all
        return base.available

    def __order_internal(
        self, symbol: str, side: str, size: float, state: StrategyState
    ) -> Dict:
        order: MarketOrder = state.interface.market_order(
            symbol, side=side, size=size
        )
        self.log_order(order)
        return order.get_response()

    def order(
        self,
        price: float,
        symbol: str,
        state: StrategyState,
        side: str = "buy",
        pct: float = 0.01,
        stop_loss: float = 0.05,
        risk_ratio: int = 2,
    ) -> float:
        pos: Position = self.get_position(state.base_asset)
        quantity: float = self.get_quantity(
            price, symbol, state, pct=pct, stop_loss=stop_loss
        )

        if not quantity:
            self.logger.warning(
                "Attempted to buy invalid quantity %f of %s", quantity, symbol
            )
            return 0.0

        if side == "buy":
            # This is a regular "long" order
            if pos is None or pos.state == TradeState.READY_NEXT:
                res: dict = self.__order_internal(
                    symbol, side, quantity, state
                )
                pos: Position = self.new_position(
                    state.base_asset,
                    state=TradeState.LONGING,
                    open=(side == "buy" and res["status"] == "done"),
                    entry=price,
                    stop_loss=price * (1 - stop_loss),
                    take_profit=price * (1 + (stop_loss * risk_ratio)),
                )
                self.logger.info("%s", pos)
                return res["size"]

            # This is a short position buy back now
            if pos.state == TradeState.SHORTING:
                res: dict = self.__order_internal(
                    symbol, side, quantity, state
                )
                pos: Position = self.update_position(
                    state.base_asset,
                    state=TradeState.READY_NEXT,
                    open=not (side == "buy" and res["status"] == "done"),
                    entry=price,
                    stop_loss=-math.inf,
                    take_profit=math.inf,
                )
                self.logger.info("%s", pos)
                return res["size"]
        elif side == "sell":
            # We're going to short this
            if pos is None or pos.state == TradeState.READY_NEXT:
                res: dict = self.__order_internal(
                    symbol, side, quantity, state
                )
                pos: Position = self.update_position(
                    state.base_asset,
                    state=TradeState.SHORTING,
                    open=(side == "sell" and res["status"] == "done"),
                    entry=price,
                    stop_loss=price * (1 + stop_loss),
                    take_profit=price * (1 - (stop_loss * risk_ratio)),
                )
                self.logger.info("%s", pos)
                return res["size"]

            # This is a long position, sell the whole smash
            if pos.state == TradeState.LONGING:
                res: dict = self.__order_internal(
                    symbol, side, quantity, state
                )
                pos: Position = self.update_position(
                    state.base_asset,
                    state=TradeState.READY_NEXT,
                    open=not (side == "sell" and res["status"] == "done"),
                    entry=price,
                    stop_loss=-math.inf,
                    take_profit=math.inf,
                )
                self.logger.info("%s", pos)
                return res["size"]
        return 0.0


class AdvancedStrategy(SimpleStrategy):
    """
    An advanced strategy runner that can take short positions as well
    as long.

    It also has stop loss and take profit mechanisms in-built by
    default.
    """

    STOP_LOSS_PCT: float = 0.05
    RISK_RATIO: int = 2

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.trade_manager = TradeManager(self.interface)

    @event("tick")
    def take_profit(
        self, price: float, symbol: str, state: StrategyState
    ) -> None:
        pos: Union[Position, None] = self.trade_manager.get_position(symbol)
        if pos is None or not pos.open:
            return

        if pos.state == TradeState.LONGING and price >= pos.take_profit:
            self.trade_manager.order(price, symbol, state, side="sell")
        elif pos.state == TradeState.SHORTING and price <= pos.take_profit:
            self.trade_manager.order(price, symbol, state, side="buy")

    @event("tick")
    def stop_loss(
        self, price: float, symbol: str, state: StrategyState
    ) -> None:
        pos: Union[Position, None] = self.trade_manager.get_position(
            state.base_asset
        )
        if pos is None or not pos.open:
            return

        if pos.state == TradeState.LONGING and price <= pos.stop_loss:
            self.trade_manager.order(price, symbol, state, side="sell")
            return
        elif pos.state == TradeState.SHORTING and price >= pos.stop_loss:
            self.trade_manager.order(price, symbol, state, side="buy")
            return

        # Move stop loss if price moves in our favor (Trailing Stop)
        if pos.state == TradeState.LONGING:
            if price > pos.stop_loss:
                self.trade_manager.update_position(
                    state.base_asset,
                    stop_loss=price * (1 - self.STOP_LOSS_PCT),
                )
        elif pos.state == TradeState.SHORTING:
            if price < pos.stop_loss:
                self.trade_manager.update_position(
                    state.base_asset,
                    stop_loss=price * (1 + self.STOP_LOSS_PCT),
                )

    def tick(self, price: float, symbol: str, state: StrategyState) -> None:
        args: tuple = (price, symbol, state)

        self.run_callbacks("tick", *args)

        if not self.safe(symbol):
            return

        pos: Union[Position, None] = self.trade_manager.get_position(
            state.base_asset
        )

        # Open order for the first time
        if pos is None:
            if self.buy(symbol):
                self.run_callbacks("buy", *args)
        # Last position is closed and we can take a long or short
        elif not pos.open and pos.state == TradeState.READY_NEXT:
            if self.buy(symbol):
                self.run_callbacks("buy", *args)
            elif self.sell(symbol):
                self.run_callbacks("sell", *args)
        # Maybe close our long position
        elif pos.open and pos.state == TradeState.LONGING:
            if self.sell(symbol):
                self.run_callbacks("sell", *args)
        # Maybe close our short
        elif pos.open and pos.state == TradeState.SHORTING:
            if self.buy(symbol):
                self.run_callbacks("buy", *args)
