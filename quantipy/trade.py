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
    """Handles state management for trade positions"""

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

    def set(self, symbol: str, **kwargs) -> Position:
        if position := self.get(symbol):
            self.positions[symbol] = position._replace(**kwargs)
            return self.positions[symbol]
        return self.new(symbol, **kwargs)


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
    ) -> Union[MarketOrder, None]:
        rv = None
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
        if order := self._order(symbol, "buy", quantity, state):
            newpos = self.state.new(
                state.base_asset,
                size=state.interface.account[state.base_asset].available,
                state=TradeState.LONGING,
                open=(
                    order.get_side() == "buy"
                    and order.get_status()["status"] == "done"
                ),
                entry=price,
                stop_loss=price * (1 - self.default_stop_loss_pct),
                take_profit=price
                * (1 + (self.default_stop_loss_pct * self.default_risk_ratio)),
                full_symbol=order.get_status()["symbol"],
            )
            state.strategy.audit(
                event="trade",
                message="Opened long",
                symbol=newpos.full_symbol,
                cash=state.interface.cash,
                size=newpos.size,
                entry=newpos.entry,
                stop_loss=newpos.stop_loss,
                take_profit=newpos.take_profit,
            )
            self.logger.info(newpos)
            return newpos
        return Position()

    def short(
        self,
        price: float,
        symbol: str,
        state: StrategyState,
        percent: float = 0.03,
    ) -> Position:
        quantity: float = self.quantity(price, state, percent)
        if order := self._order(symbol, "sell", quantity, state):
            newpos = self.state.new(
                state.base_asset,
                size=abs(state.interface.account[state.base_asset].available),
                state=TradeState.SHORTING,
                open=(
                    order.get_side() == "sell"
                    and order.get_status()["status"] == "done"
                ),
                entry=price,
                stop_loss=price * (1 + self.default_stop_loss_pct),
                take_profit=price
                * (1 - (self.default_stop_loss_pct * self.default_risk_ratio)),
                full_symbol=order.get_status()["symbol"],
            )
            state.strategy.audit(
                event="trade",
                message="Opened short",
                symbol=newpos.full_symbol,
                cash=state.interface.cash,
                size=newpos.size,
                entry=newpos.entry,
                stop_loss=newpos.stop_loss,
                take_profit=newpos.take_profit,
            )
            self.logger.info(newpos)
            return newpos
        return Position()

    def close(self, position: Position, state: StrategyState) -> Position:
        if not position.open:
            return Position()
        quantity: float = position.size
        if position.state == TradeState.LONGING:
            self._order(position.full_symbol, "sell", quantity, state)
        elif position.state == TradeState.SHORTING:
            self._order(position.full_symbol, "buy", quantity, state)
        newpos = self.state.new(
            state.base_asset,
            state=TradeState.CLOSED,
            full_symbol=position.full_symbol,
        )
        state.strategy.audit(
            event="trade",
            message="Closed position",
            symbol=newpos.full_symbol,
            cash=state.interface.cash,
            size=newpos.size,
            entry=newpos.entry,
        )
        self.logger.info(newpos)
        return newpos

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
