from typing import Union

from blankly import StrategyState

from quantipy.position import Position
from quantipy.state import TradeState
from quantipy.strategies.simple import SimpleStrategy, event
from quantipy.trade import TradeManager


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
        self.manager = TradeManager(
            default_stop_loss_pct=self.STOP_LOSS_PCT,
            default_risk_ratio=self.RISK_RATIO,
        )

    @event("tick")
    def take_profit(
        self, price: float, symbol: str, state: StrategyState
    ) -> None:
        position: Union[Position, None] = self.manager.state.get(symbol)
        if position is None or not position.open:
            return

        if (
            position.state == TradeState.LONGING
            and price >= position.take_profit
        ) or (
            position.state == TradeState.SHORTING
            and price <= position.take_profit
        ):
            self.manager.close(position, state)

    @event("tick")
    def stop_loss(
        self, price: float, symbol: str, state: StrategyState
    ) -> None:
        position: Union[Position, None] = self.manager.state.get(symbol)
        if position is None or not position.open:
            return

        if (
            position.state == TradeState.LONGING
            and price <= position.stop_loss
        ) or (
            position.state == TradeState.SHORTING
            and price >= position.stop_loss
        ):
            self.manager.close(position, state)

        # Move stop loss if price moves in our favor (Trailing Stop)
        if position.state == TradeState.LONGING:
            if price > position.stop_loss:
                self.manager.state.set(
                    state.base_asset,
                    stop_loss=price * (1 - self.STOP_LOSS_PCT),
                )
        elif position.state == TradeState.SHORTING:
            if price < position.stop_loss:
                self.manager.state.set(
                    state.base_asset,
                    stop_loss=price * (1 + self.STOP_LOSS_PCT),
                )

    def tick(  # noqa: C901
        self, price: float, symbol: str, state: StrategyState
    ) -> None:
        args: tuple = (price, symbol, state)

        self.run_callbacks("tick", *args)

        position: Union[Position, None] = self.manager.state.get(
            state.base_asset
        )

        if not self.safe(symbol):
            if position is not None and position.open:
                self.manager.close(position, state)
            return

        # No position found, or it's closed
        if position is None or not position.open:
            if self.buy(symbol):
                self.run_callbacks("buy", *args)
            elif self.sell(symbol):
                self.run_callbacks("sell", *args)
        # Maybe close our long position
        elif position.open and position.state == TradeState.LONGING:
            if self.sell(symbol):
                self.manager.close(position, state)
        # Maybe close our short
        elif position.open and position.state == TradeState.SHORTING:
            if self.buy(symbol):
                self.manager.close(position, state)
