from blankly import StrategyState
from blankly.indicators import macd, stochastic_rsi
from blankly.utils import trunc

from quantipy.strategies.base import StrategyBase


class StochasticRSIWithRSIAndMACD(StrategyBase):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.register_on_tick_callback(self.update_indicators)
        self.register_on_buy_callback(self._buy)
        self.register_on_sell_callback(self._sell)

    def _buy(self, price: float, symbol: str, state: StrategyState) -> None:
        qty = trunc(state.interface.cash / price, 3)
        state.interface.market_order(symbol, side="buy", size=qty)
        self.position_open = True

    def _sell(self, price: float, symbol: str, state: StrategyState) -> None:
        qty = trunc(state.interface.account[state.base_asset].available, 3)
        state.interface.market_order(symbol, side="sell", size=qty)
        self.position_open = False

    def update_indicators(self, *args, **kwargs) -> None:
        self.rsi, self.stoch_rsi_K, self.stoch_rsi_D = stochastic_rsi(
            self.data["close"]
        )
        self.macd_res, self.macd_sig, self.macd_hist = macd(self.data["close"])

    def buy(self) -> bool:
        # Both the %K and %D lines must have been below 20 recently
        stride = 10
        below_20_K = self.stoch_rsi_K < 20
        below_20_D = self.stoch_rsi_D < 20
        both_below_20 = below_20_K & below_20_D
        lookback = both_below_20[-stride:]
        both_below_20_occurred = lookback.any()
        if not both_below_20_occurred:
            return False

        # Ensure RSI > 50
        if float(self.rsi.iloc[-1]) < 50:
            return False

        # Check for MACD cross to confirm uptrend
        slope = (self.macd_res[-1] - self.macd_res[-5]) / 5
        prev_macd = self.macd_res[-2]
        curr_macd = self.macd_res[-1]
        curr_macd_s = self.macd_sig[-1]
        cross = (slope > 0) and (curr_macd >= curr_macd_s > prev_macd)
        if not cross:
            return False

        # Finally ensure that both stochastic lines are not overbought
        if not (self.stoch_rsi_K.iloc[-1] < 80 and self.stoch_rsi_D.iloc[-1] < 80):
            return False
        return True

    def sell(self) -> bool:
        # Both the %K and %D lines must have been above 80 recently
        stride = 10
        above_80_K = self.stoch_rsi_K > 80
        above_80_D = self.stoch_rsi_D > 80
        both_above_20 = above_80_K & above_80_D
        lookback = both_above_20[-stride:]
        both_above_80_occurred = lookback.any()
        if not both_above_80_occurred:
            return False

        # Ensure RSI < 50
        if float(self.rsi.iloc[-1]) > 50:
            return False

        # Check for MACD cross to confirm downtrend
        slope = (self.macd_res[-1] - self.macd_res[-5]) / 5
        prev_macd = self.macd_res[-2]
        curr_macd = self.macd_res[-1]
        curr_macd_s = self.macd_sig[-1]
        cross = (slope < 0) and (curr_macd <= curr_macd_s < prev_macd)
        if not cross:
            return False

        # Finally ensure that both stochastic lines are not oversold
        if not (self.stoch_rsi_K.iloc[-1] > 20 and self.stoch_rsi_D.iloc[-1] > 20):
            return False
        return True
