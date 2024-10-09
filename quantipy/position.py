import math
from collections import namedtuple

from quantipy.state import TradeState

Position = namedtuple(
    "Position",
    field_names=[
        "symbol",
        "size",
        "state",
        "open",
        "entry",
        "stop_loss",
        "take_profit",
        "full_symbol",
    ],
    defaults=[
        "N/A",
        0,
        TradeState.INITIALIZED,
        False,
        0,
        -math.inf,
        math.inf,
        "N/A-USD",
    ],
)
