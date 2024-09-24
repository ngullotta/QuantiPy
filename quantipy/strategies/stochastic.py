from blankly import StrategyState
from blankly.indicators import macd, stochastic_rsi

from quantipy.strategies.simple import SimpleStrategy, event


class HarmonicOscillator(SimpleStrategy):
    """
    A complex strategy involving the Stochastic RSI, (Regular) RSI and
    the MACD all working in concert.
    """

    @event("buy")
    def b(self, price: float, symbol: str, state: StrategyState) -> float:
        return self.order(price, symbol, state, pct=0.5)

    @event("sell")
    def s(self, price: float, symbol: str, state: StrategyState) -> float:
        return self.order(price, symbol, state, side="sell")

    def buy(self, symbol: str) -> bool:
        rsi, stoch_rsi_K, stoch_rsi_D = stochastic_rsi(self.data[symbol]["close"])

        # Both the %K and %D lines must have been below 20 recently
        stride = 2
        below_20_K = stoch_rsi_K < 20
        below_20_D = stoch_rsi_D < 20
        both_below_20 = below_20_K & below_20_D
        lookback = both_below_20[-stride:]
        both_below_20_occurred = lookback.any()
        if not both_below_20_occurred:
            return False

        # Ensure RSI > 50
        if rsi.iloc[-1] < 50:
            return False

        macd_res, macd_sig, macd_hist = macd(self.data[symbol]["close"])

        # Check for MACD cross to confirm uptrend
        slope = (macd_res[-1] - macd_res[-5]) / 5
        prev_macd = macd_res[-2]
        curr_macd = macd_res[-1]
        curr_macd_s = macd_sig[-1]
        cross = (slope > 0) and (curr_macd >= curr_macd_s > prev_macd)
        if not cross:
            return False

        # Finally ensure that both stochastic lines are not overbought
        if not (stoch_rsi_K.iloc[-1] < 80 and stoch_rsi_D.iloc[-1] < 80):
            return False
        return True

    def sell(self, symbol: str) -> bool:
        rsi, stoch_rsi_K, stoch_rsi_D = stochastic_rsi(self.data[symbol]["close"])

        # Both the %K and %D lines must have been above 80 recently
        stride = 2
        above_80_K = stoch_rsi_K > 80
        above_80_D = stoch_rsi_D > 80
        both_above_80 = above_80_K & above_80_D
        lookback = both_above_80[-stride:]
        both_above_80_occurred = lookback.any()
        if not both_above_80_occurred:
            return False

        # Ensure RSI < 50
        if rsi.iloc[-1] > 50:
            return False

        macd_res, macd_sig, macd_hist = macd(self.data[symbol]["close"])

        # Check for MACD cross to confirm downtrend
        slope = (macd_res[-1] - macd_res[-5]) / 5
        prev_macd = macd_res[-2]
        curr_macd = macd_res[-1]
        curr_macd_s = macd_sig[-1]
        cross = (slope < 0) and (curr_macd <= curr_macd_s < prev_macd)
        if not cross:
            return False

        # Finally ensure that both stochastic lines are not oversold
        if not (stoch_rsi_K.iloc[-1] > 20 and stoch_rsi_D.iloc[-1] > 20):
            return False
        return True
