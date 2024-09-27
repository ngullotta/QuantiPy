import numpy as np
from blankly import StrategyState
from pandas import Series
from ta.momentum import RSIIndicator, StochRSIIndicator
from ta.trend import MACD

from quantipy.strategies.simple import SimpleStrategy, event


class HarmonicOscillators(SimpleStrategy):
    """
    A complex strategy involving the Stochastic RSI, (Regular) RSI and
    the MACD all working in concert.
    """

    # Lookback period for the %K and %D checks
    stride: int = 5

    stop_loss_pct: float = 0.10
    risk_ratio = 5
    take_profit_pct: float = stop_loss_pct * risk_ratio

    @event("tick")
    def take_profit_or_stop_loss(
        self, price: float, symbol: str, state: StrategyState
    ) -> None:
        if not self.positions[symbol].get("open"):
            return

        entry: float = self.positions[symbol]["entry"]
        take_profit: float = entry * (1 + self.take_profit_pct)
        stop_loss: float = entry * (1 - self.stop_loss_pct)

        if price >= take_profit or price <= stop_loss:
            message = "Take Profit" if price >= take_profit else "Stop Loss"
            data = {
                "price": price,
                "entry": entry,
                "take_profit": take_profit,
                "stop_loss": stop_loss,
            }
            self.audit(symbol, "sell", message, **data)
            self.s(price, symbol, state)

    @event("buy")
    def b(self, price: float, symbol: str, state: StrategyState) -> float:
        return self.order(price, symbol, state, pct=0.75, stop_loss=1)

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
        if any([length < self.stride for length in lengths]):
            return False

        # Both the %K and %D lines must have been below 20 recently
        below_20_K: Series = stoch_rsi_K < 20
        below_20_D: Series = stoch_rsi_D < 20

        if not below_20_K[-self.stride :].any():
            return False

        if not below_20_D[-self.stride :].any():
            return False

        both_below_20_occured = False
        below_20_D: Series = below_20_D[-self.stride :]

        last_k, last_d = -1, -1
        both_below_20_occured = True
        for k, d in zip(
            stoch_rsi_K[-self.stride :], stoch_rsi_D[-self.stride :]
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

        # MACD Hist is unused
        macd = MACD(close)
        macd_line, macd_signal = macd.macd(), macd.macd_signal()

        # Sanity check, must have `minimum_num_points` or more points
        # to check. This is so we can calculate the slope correctly
        minimum_num_points = 5
        lengths = [len(macd_line), len(macd_signal)]
        if any([length < minimum_num_points for length in lengths]):
            return False

        # Check for MACD cross to confirm uptrend
        slope: float = (macd_line.iloc[-1] - macd_line.iloc[-5]) / 5
        prev_macd: float = macd_line.iloc[-2]
        curr_macd: float = macd_line.iloc[-1]
        curr_macd_s: float = macd_signal.iloc[-1]
        crossing_up: bool = slope > 0 and curr_macd >= curr_macd_s > prev_macd
        if not crossing_up:
            return False

        # Finally ensure that both stochastic lines are not overbought
        if not (stoch_rsi_K.iloc[-1] < 80 and stoch_rsi_D.iloc[-1] < 80):
            return False

        data = {
            "stoch_K": list(stoch_rsi_K)[-self.stride :],
            "stoch_D": list(stoch_rsi_D)[-self.stride :],
            "rsi": rsi.iloc[-1],
            "macd_slope": slope,
            "curr_macd": curr_macd,
            "curr_macd_signal": curr_macd_s,
            "prev_macd": prev_macd,
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
        if any([length < self.stride for length in lengths]):
            return False

        # Both the %K and %D lines must have been above 80 recently
        above_80_K: Series = stoch_rsi_K > 80
        above_80_D: Series = stoch_rsi_D > 80

        if not above_80_K[-self.stride :].any():
            return False

        if not above_80_D[-self.stride :].any():
            return False

        last_k, last_d = -1, -1
        both_above_80_occurred = True
        for k, d in zip(
            stoch_rsi_K[-self.stride :], stoch_rsi_D[-self.stride :]
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

        # MACD Hist is unused
        macd = MACD(close)
        macd_line, macd_signal = macd.macd(), macd.macd_signal()

        # Sanity check, must have `minimum_num_points` or more points
        # to check. This is so we can calculate the slope correctly
        minimum_num_points = 5
        lengths = [len(macd_line), len(macd_signal)]
        if any([length < minimum_num_points for length in lengths]):
            return False

        # Check for MACD cross to confirm downtrend
        slope: float = (macd_line.iloc[-1] - macd_line.iloc[-5]) / 5
        prev_macd: float = macd_line.iloc[-2]
        curr_macd: float = macd_line.iloc[-1]
        curr_macd_s: float = macd_signal.iloc[-1]
        crossing_down: bool = curr_macd <= curr_macd_s
        if not crossing_down:
            return False

        # Finally ensure that both stochastic lines are not oversold
        if not (stoch_rsi_K.iloc[-1] > 20 and stoch_rsi_D.iloc[-1] > 20):
            return False

        data = {
            "stoch_K": list(stoch_rsi_K)[-self.stride :],
            "stoch_D": list(stoch_rsi_D)[-self.stride :],
            "rsi": rsi.iloc[-1],
            "macd_slope": slope,
            "curr_macd": curr_macd,
            "curr_macd_signal": curr_macd_s,
            "prev_macd": prev_macd,
        }

        self.audit(symbol, "sell", "Signal hit", **data)

        return True
