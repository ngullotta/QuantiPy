import numpy as np
from blankly import StrategyState
from pandas import Series
from ta.momentum import RSIIndicator, StochRSIIndicator
from ta.trend import MACD

from quantipy.strategies.simple import SimpleStrategy, event
from quantipy.strategies.advanced import AdvancedStrategy, Position, TradeState


class AdvancedHarmonicOscillators(AdvancedStrategy):
    """
    A complex strategy involving the Stochastic RSI, (Regular) RSI and
    the MACD all working in concert.
    """

    # Strategy-specific parameters
    STRIDE: int = 5

    # `AdvancedStrategy` parameters
    STOP_LOSS_PCT: float = 0.05
    RISK_RATIO: int = 4

    @event("buy")
    def b(self, price: float, symbol: str, state: StrategyState) -> float:
        return self.trade_manager.order(
            price,
            symbol,
            state,
            side="buy",
            pct=0.03,
            stop_loss=self.STOP_LOSS_PCT,
        )

    @event("sell")
    def s(self, price: float, symbol: str, state: StrategyState) -> float:
        pos: Position = self.trade_manager.get_position(state.base_asset)

        # Close our long if applicable
        if pos is not None and pos.state == TradeState.LONGING:
            self.trade_manager.order(price, symbol, state, side="sell")

        # Open a short
        return self.trade_manager.order(
            price,
            symbol,
            state,
            side="sell",
            pct=0.03,
            stop_loss=self.STOP_LOSS_PCT,
        )

    def buy(self, symbol: str) -> bool:  # noqa: C901
        close = Series(self.data[symbol]["close"])

        stoch = StochRSIIndicator(close)
        stoch_rsi_K: Series = stoch.stochrsi_k() * 100
        stoch_rsi_D: Series = stoch.stochrsi_d() * 100

        rsi: Series = RSIIndicator(close).rsi()

        # Sanity check, must have `stride` number of points to check
        lengths = [len(rsi), len(stoch_rsi_K), len(stoch_rsi_D)]
        if any([length < self.STRIDE for length in lengths]):
            return False

        # Both the %K and %D lines must have been below 20 recently
        below_20_K: Series = stoch_rsi_K < 20
        below_20_D: Series = stoch_rsi_D < 20

        if not below_20_K[-self.STRIDE :].any():
            return False

        if not below_20_D[-self.STRIDE :].any():
            return False

        both_below_20_occured = False
        below_20_D: Series = below_20_D[-self.STRIDE :]

        last_k, last_d = -1, -1
        both_below_20_occured = True
        for k, d in zip(
            stoch_rsi_K[-self.STRIDE :], stoch_rsi_D[-self.STRIDE :]
        ):
            if not (k > last_k and d > last_d):
                both_below_20_occured = False
                break
            last_k = k
            last_d = d

        if not both_below_20_occured:
            return False

        # Ensure RSI > 50
        if rsi.iloc[-1] < 50:
            return False

        macd_line: np.ndarry = None
        macd_signal: np.ndarry = None

        macd = MACD(close)
        macd_line, macd_signal = macd.macd(), macd.macd_signal()

        # Check for MACD cross to confirm uptrend
        if not macd_line.iloc[-1] >= macd_signal.iloc[-1]:
            return False

        # Finally ensure that both stochastic lines are not overbought
        if not (stoch_rsi_K.iloc[-1] < 80 and stoch_rsi_D.iloc[-1] < 80):
            return False

        data = {
            "stoch_K": list(stoch_rsi_K)[-self.STRIDE :],
            "stoch_D": list(stoch_rsi_D)[-self.STRIDE :],
            "rsi": rsi.iloc[-1],
            "curr_macd": macd_line.iloc[-1],
            "curr_macd_signal": macd_signal.iloc[-1],
        }

        self.audit(symbol, "buy", "Signal hit", **data)

        return True

    def sell(self, symbol: str) -> bool:  # noqa: C901
        close = Series(self.data[symbol]["close"])

        stoch = StochRSIIndicator(close)
        stoch_rsi_K: Series = stoch.stochrsi_k() * 100
        stoch_rsi_D: Series = stoch.stochrsi_d() * 100

        rsi: Series = RSIIndicator(close).rsi()

        # Sanity check, must have `stride` number of points to check
        lengths = [len(rsi), len(stoch_rsi_K), len(stoch_rsi_D)]
        if any([length < self.STRIDE for length in lengths]):
            return False

        # Both the %K and %D lines must have been above 80 recently
        above_80_K: Series = stoch_rsi_K > 80
        above_80_D: Series = stoch_rsi_D > 80

        if not above_80_K[-self.STRIDE :].any():
            return False

        if not above_80_D[-self.STRIDE :].any():
            return False

        last_k, last_d = -1, -1
        both_above_80_occurred = True
        for k, d in zip(
            stoch_rsi_K[-self.STRIDE :], stoch_rsi_D[-self.STRIDE :]
        ):
            if not (k > last_k and d > last_d):
                both_above_80_occurred = False
                break
            last_k = k
            last_d = d

        if not both_above_80_occurred:
            return False

        # Ensure RSI < 50
        if rsi.iloc[-1] > 50:
            return False

        macd_line: np.ndarry = None
        macd_signal: np.ndarry = None

        macd = MACD(close)
        macd_line, macd_signal = macd.macd(), macd.macd_signal()

        # Check for MACD cross to confirm downtrend
        if not macd_line.iloc[-1] <= macd_signal.iloc[-1]:
            return False

        # Finally ensure that both stochastic lines are not oversold
        if not (stoch_rsi_K.iloc[-1] > 20 and stoch_rsi_D.iloc[-1] > 20):
            return False

        data = {
            "stoch_K": list(stoch_rsi_K)[-self.STRIDE :],
            "stoch_D": list(stoch_rsi_D)[-self.STRIDE :],
            "rsi": rsi.iloc[-1],
            "curr_macd": macd_line.iloc[-1],
            "curr_macd_signal": macd_signal.iloc[-1],
        }

        self.audit(symbol, "sell", "Signal hit", **data)

        return True


class HarmonicOscillators(SimpleStrategy):
    """
    A complex strategy involving the Stochastic RSI, (Regular) RSI and
    the MACD all working in concert.
    """

    stride: int = 5

    stop_loss_pct: float = 0.05
    risk_ratio: int = 4

    @event("buy")
    def b(self, price: float, symbol: str, state: StrategyState) -> float:
        return self.order(
            price, symbol, state, pct=0.03, stop_loss=self.stop_loss_pct
        )

    @event("sell")
    def s(self, price: float, symbol: str, state: StrategyState) -> float:
        return self.order(price, symbol, state, side="sell")

    def buy(self, symbol: str) -> bool:  # noqa: C901
        close = Series(self.data[symbol]["close"])

        stoch = StochRSIIndicator(close)
        stoch_rsi_K: Series = stoch.stochrsi_k() * 100
        stoch_rsi_D: Series = stoch.stochrsi_d() * 100

        rsi: Series = RSIIndicator(close).rsi()

        # Sanity check, must have `stride` number of points to check
        lengths = [len(rsi), len(stoch_rsi_K), len(stoch_rsi_D)]
        if any([length < self.STRIDE for length in lengths]):
            return False

        # Both the %K and %D lines must have been below 20 recently
        below_20_K: Series = stoch_rsi_K < 20
        below_20_D: Series = stoch_rsi_D < 20

        if not below_20_K[-self.STRIDE :].any():
            return False

        if not below_20_D[-self.STRIDE :].any():
            return False

        both_below_20_occured = False
        below_20_D: Series = below_20_D[-self.STRIDE :]

        last_k, last_d = -1, -1
        both_below_20_occured = True
        for k, d in zip(
            stoch_rsi_K[-self.STRIDE :], stoch_rsi_D[-self.STRIDE :]
        ):
            if not (k > last_k and d > last_d):
                both_below_20_occured = False
                break
            last_k = k
            last_d = d

        if not both_below_20_occured:
            return False

        # Ensure RSI > 50
        if rsi.iloc[-1] < 50:
            return False

        macd_line: np.ndarry = None
        macd_signal: np.ndarry = None

        macd = MACD(close)
        macd_line, macd_signal = macd.macd(), macd.macd_signal()

        # Check for MACD cross to confirm uptrend
        if not macd_line.iloc[-1] >= macd_signal.iloc[-1]:
            return False

        # Finally ensure that both stochastic lines are not overbought
        if not (stoch_rsi_K.iloc[-1] < 80 and stoch_rsi_D.iloc[-1] < 80):
            return False

        data = {
            "stoch_K": list(stoch_rsi_K)[-self.STRIDE :],
            "stoch_D": list(stoch_rsi_D)[-self.STRIDE :],
            "rsi": rsi.iloc[-1],
            "curr_macd": macd_line.iloc[-1],
            "curr_macd_signal": macd_signal.iloc[-1],
        }

        self.audit(symbol, "buy", "Signal hit", **data)

        return True

    def sell(self, symbol: str) -> bool:  # noqa: C901
        close = Series(self.data[symbol]["close"])

        stoch = StochRSIIndicator(close)
        stoch_rsi_K: Series = stoch.stochrsi_k() * 100
        stoch_rsi_D: Series = stoch.stochrsi_d() * 100

        rsi: Series = RSIIndicator(close).rsi()

        # Sanity check, must have `stride` number of points to check
        lengths = [len(rsi), len(stoch_rsi_K), len(stoch_rsi_D)]
        if any([length < self.STRIDE for length in lengths]):
            return False

        # Both the %K and %D lines must have been above 80 recently
        above_80_K: Series = stoch_rsi_K > 80
        above_80_D: Series = stoch_rsi_D > 80

        if not above_80_K[-self.STRIDE :].any():
            return False

        if not above_80_D[-self.STRIDE :].any():
            return False

        last_k, last_d = -1, -1
        both_above_80_occurred = True
        for k, d in zip(
            stoch_rsi_K[-self.STRIDE :], stoch_rsi_D[-self.STRIDE :]
        ):
            if not (k > last_k and d > last_d):
                both_above_80_occurred = False
                break
            last_k = k
            last_d = d

        if not both_above_80_occurred:
            return False

        # Ensure RSI < 50
        if rsi.iloc[-1] > 50:
            return False

        macd_line: np.ndarry = None
        macd_signal: np.ndarry = None

        macd = MACD(close)
        macd_line, macd_signal = macd.macd(), macd.macd_signal()

        # Check for MACD cross to confirm downtrend
        if not macd_line.iloc[-1] <= macd_signal.iloc[-1]:
            return False

        # Finally ensure that both stochastic lines are not oversold
        if not (stoch_rsi_K.iloc[-1] > 20 and stoch_rsi_D.iloc[-1] > 20):
            return False

        data = {
            "stoch_K": list(stoch_rsi_K)[-self.STRIDE :],
            "stoch_D": list(stoch_rsi_D)[-self.STRIDE :],
            "rsi": rsi.iloc[-1],
            "curr_macd": macd_line.iloc[-1],
            "curr_macd_signal": macd_signal.iloc[-1],
        }

        self.audit(symbol, "sell", "Signal hit", **data)

        return True
