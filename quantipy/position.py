import math
from collections import namedtuple

from quantipy.state import TradeState

Position = namedtuple(
    "Position",
    field_names=["state", "open", "entry", "stop_loss", "take_profit"],
    defaults=[TradeState.INITIALIZED, False, 0, -math.inf, math.inf],
)
