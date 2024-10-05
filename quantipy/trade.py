import logging
from collections import defaultdict
from typing import Union

from blankly import StrategyState
from blankly.exchanges.orders.market_order import MarketOrder
from blankly.utils import trunc
from blankly.utils.exceptions import InvalidOrder

from quantipy.state import TradeState
from quantipy.types import Position, Positions


class PositionStateManager:
    def __init__(self) -> None:
        self.positions: Positions = defaultdict(dict)

    def new(self, symbol: str, **kwargs) -> Position:
        self.delete(symbol)
        self.positions[symbol] = Position(symbol=symbol, **kwargs)
        return self.positions[symbol]

    def delete(self, symbol: str) -> None:
        self.positions.pop(symbol, None)

    def get(self, symbol: str) -> Union[Position, None]:
        return self.positions.get(symbol)


class TradeManager:
    """
    This class is responsible for managing trades as well as doing
    quantity calculations and updating position state
    """

    logger = logging.getLogger("TradeManager")

    def __init__(
        self, default_stop_loss_pct: float = 0.05, default_risk_ratio: int = 2
    ) -> None:
        self.default_stop_loss_pct = default_stop_loss_pct
        self.default_risk_ratio = default_risk_ratio
        self.state: PositionStateManager = PositionStateManager()

    @staticmethod
    def clamp(value: float, _max: float, _min: float) -> float:
        return max(min(value, _max), _min)

    def quantity(
        self,
        price: float,
        state: StrategyState,
        percent: float = 0.03,
        precision: int = 4,
    ) -> float:
        """
        This function determines how many units of the symbol we should
        buy/sell using our current available funds from
        `state.interface.cash`. Note that this only works for *new*
        positions. Old positions that are still open should instead use
        `TradeManager.close` to close that position.

        The total quantity is also truncated (rounded) to `precision`
        size.

        This works for longs and shorts as well.

        The units are calculated using risk management calculations
        that take into account your stop loss and the percent of your
        total cash you want to risk.

        e.g:
        Cash balance: $1000
        Percent of cash balance: 3%
        Stop Loss Percent: 5%
        Unit Price: $10

        total cash to spend ~> (1000 * 0.03) / 0.05 = 30 / 0.05 = $600
        quantity ~> $600 / $10 = 60 units of symbol

        Note that any attempt to make the percent of cash greater than
        the stop loss percent will be "clamped" to be no more than the
        full cash balance.
        """
        balance: float = state.interface.cash
        cash: float = (balance * percent) / self.default_stop_loss_pct
        total: float = self.clamp(cash, balance, 1)
        return trunc(total / price, precision)

    def _order(
        self, symbol: str, side: str, size: float, state: StrategyState
    ) -> MarketOrder:
        rv = MarketOrder(None, {}, state)
        if not size:
            self.logger.error(
                "Attempted to %s invalid size of %s -> quantity %f",
                side,
                symbol,
                size,
            )
            return rv

        try:
            rv = state.interface.market_order(symbol, side=side, size=size)
        except InvalidOrder as ex:
            self.logger.error(ex)

        return rv

    def long(
        self,
        price: float,
        symbol: str,
        state: StrategyState,
        percent: float = 0.03,
    ) -> Position:
        quantity: float = self.quantity(price, state, percent)
        order: MarketOrder = self._order(symbol, "buy", quantity, state)
        return self.state.new(
            state.base_asset,
            size=order.get_size(),
            state=TradeState.LONGING,
            open=(order.get_side() == "buy" and order.get_status() == "done"),
            entry=price,
            stop_loss=price * (1 - self.default_stop_loss_pct),
            take_profit=price
            * (1 + (self.default_stop_loss_pct * self.default_risk_ratio)),
        )

    def short(
        self,
        price: float,
        symbol: str,
        state: StrategyState,
        percent: float = 0.03,
    ) -> Position:
        quantity: float = self.quantity(price, state, percent)
        order: MarketOrder = self._order(symbol, "sell", quantity, state)
        return self.state.new(
            state.base_asset,
            size=order.get_size(),
            state=TradeState.SHORTING,
            open=(order.get_side() == "sell" and order.get_status() == "done"),
            entry=price,
            stop_loss=price * (1 + self.default_stop_loss_pct),
            take_profit=price
            * (1 - (self.default_stop_loss_pct * self.default_risk_ratio)),
        )

    def close(self, position: Position, state: StrategyState) -> Position:
        if not position.open:
            return Position()
        quantity: float = position.size
        if position.state == TradeState.LONGING:
            order: MarketOrder = self._order(
                position.symbol, "sell", quantity, state
            )
        elif position.state == TradeState.SHORTING:
            order: MarketOrder = self._order(
                position.symbol, "buy", quantity, state
            )
        return self.state.new(state.base_asset, state=TradeState.CLOSED)

    def order(
        self,
        price: float,
        symbol: str,
        state: StrategyState,
        side: str = "buy",
        percent: float = 0.03,
    ) -> Position:
        position: Position = self.state.get(state.base_asset)
        if position is None or not position.open:
            if side == "buy":
                return self.long(price, symbol, state, percent)
            elif side == "sell":
                return self.short(price, symbol, state, percent)
        elif position.open:
            return self.close(position, state)
