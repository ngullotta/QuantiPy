import numpy as np
from blankly import StrategyState
from blankly.indicators import macd, stochastic_rsi
from pandas import Series

from quantipy.strategies.simple import SimpleStrategy, event


class HarmonicOscillators(SimpleStrategy):
    """
    A complex strategy involving the Stochastic RSI, (Regular) RSI and
    the MACD all working in concert.
    """

    # Lookback period for the %K and %D checks
    stride: int = 5

    @event("buy")
    def b(self, price: float, symbol: str, state: StrategyState) -> float:
        return self.order(price, symbol, state, pct=0.5)

    @event("sell")
    def s(self, price: float, symbol: str, state: StrategyState) -> float:
        return self.order(price, symbol, state, side="sell")

    def buy(self, symbol: str) -> bool:
        rsi: Series = None
        stoch_rsi_K: Series = None
        stoch_rsi_D: Series = None

        rsi, stoch_rsi_K, stoch_rsi_D = stochastic_rsi(
            self.data[symbol]["close"]
        )

        # Sanity check, must have `stride` number of points to check
        lengths = [len(rsi), len(stoch_rsi_K), len(stoch_rsi_D)]
        if any([length < self.stride for length in lengths]):
            return False

        # Both the %K and %D lines must have been below 20 recently
        below_20_K: Series = stoch_rsi_K < 20
        below_20_D: Series = stoch_rsi_D < 20
        both_below_20: Series = below_20_K & below_20_D
        lookback: Series = both_below_20[-self.stride :]
        both_below_20_occurred: bool = lookback.any()
        if not both_below_20_occurred:
            return False

        # Ensure RSI > 50
        if rsi.iloc[-1] < 50:
            return False

        macd_line: np.ndarry = None
        macd_signal: np.ndarry = None

        # MACD Hist is unused
        macd_line, macd_signal, _ = macd(self.data[symbol]["close"])

        # Sanity check, must have `minimum_num_points` or more points
        # to check. This is so we can calculate the slope correctly
        minimum_num_points = 5
        lengths = [len(macd_line), len(macd_signal)]
        if any([length < minimum_num_points for length in lengths]):
            return False

        # Check for MACD cross to confirm uptrend
        slope: float = (macd_line[-1] - macd_line[-5]) / 5
        prev_macd: float = macd_line[-2]
        curr_macd: float = macd_line[-1]
        curr_macd_s: float = macd_signal[-1]
        crossing_up: bool = slope > 0 and curr_macd >= curr_macd_s > prev_macd
        if not crossing_up:
            return False

        # Finally ensure that both stochastic lines are not overbought
        if not (stoch_rsi_K.iloc[-1] < 80 and stoch_rsi_D.iloc[-1] < 80):
            return False
        return True

    def sell(self, symbol: str) -> bool:
        rsi: Series = None
        stoch_rsi_K: Series = None
        stoch_rsi_D: Series = None

        rsi, stoch_rsi_K, stoch_rsi_D = stochastic_rsi(
            self.data[symbol]["close"]
        )

        # Sanity check, must have `stride` number of points to check
        lengths = [len(rsi), len(stoch_rsi_K), len(stoch_rsi_D)]
        if any([length < self.stride for length in lengths]):
            return False

        # Both the %K and %D lines must have been above 80 recently
        above_80_K: Series = stoch_rsi_K > 80
        above_80_D: Series = stoch_rsi_D > 80
        both_above_80: Series = above_80_K & above_80_D
        lookback: Series = both_above_80[-self.stride :]
        both_above_80_occurred: bool = lookback.any()
        if not both_above_80_occurred:
            return False

        # Ensure RSI < 50
        if rsi.iloc[-1] > 50:
            return False

        macd_line: np.ndarry = None
        macd_signal: np.ndarry = None

        # MACD Hist is unused
        macd_line, macd_signal, _ = macd(self.data[symbol]["close"])

        # Sanity check, must have `minimum_num_points` or more points
        # to check. This is so we can calculate the slope correctly
        minimum_num_points = 5
        lengths = [len(macd_line), len(macd_signal)]
        if any([length < minimum_num_points for length in lengths]):
            return False

        # Check for MACD cross to confirm downtrend
        slope: float = (macd_line[-1] - macd_line[-5]) / 5
        prev_macd: float = macd_line[-2]
        curr_macd: float = macd_line[-1]
        curr_macd_s: float = macd_signal[-1]
        crossing_down: bool = (
            slope < 0 and curr_macd <= curr_macd_s < prev_macd
        )
        if not crossing_down:
            return False

        # Finally ensure that both stochastic lines are not oversold
        if not (stoch_rsi_K.iloc[-1] > 20 and stoch_rsi_D.iloc[-1] > 20):
            return False
        return True
