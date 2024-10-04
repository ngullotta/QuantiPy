import logging
from collections import defaultdict
from typing import Union

from blankly import StrategyState, trunc
from blankly.exchanges.orders.market_order import MarketOrder

from quantipy.state import TradeState
from quantipy.types import Position, Positions


class TradeManager:
    """
    This class is responsible for managing trades as well as doing
    quantity calculations and updating position state
    """

    logger = logging.getLogger("TradeManager")

    def __init__(self) -> None:
        self.positions: Positions = defaultdict(dict)

    def get_position(self, symbol: str) -> Union[Position, None]:
        return self.positions.get(symbol)

    def new_position(self, symbol: str, **kwargs) -> Position:
        self.positions.pop(symbol, None)
        self.positions[symbol] = Position(**kwargs)
        return self.positions[symbol]

    def update_position(self, symbol: str, **kwargs) -> Position:
        if pos := self.positions.get(symbol):
            self.positions[symbol] = pos._replace(**kwargs)
            return self.positions[symbol]
        return self.new_position(symbol, **kwargs)

    @staticmethod
    def clamp(value: float, _max: float, _min: float) -> float:
        return max(min(value, _max), _min)

    @staticmethod
    def _order_to_str(order: MarketOrder) -> str:
        data: dict = order.get_response()
        return "(%s) [%s] %.8f of -> %s" % (
            int(data["created_at"]),
            data["side"],
            data["size"],
            data["symbol"],
        )

    def log_order(self, order: MarketOrder) -> None:
        self.logger.info(self._order_to_str(order))

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
    ) -> dict:
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
                    stop_loss=0,
                    take_profit=0xFFFFFFFF,
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
                    stop_loss=0,
                    take_profit=0xFFFFFFFF,
                )
                self.logger.info("%s", pos)
                return res["size"]
        return 0.0
