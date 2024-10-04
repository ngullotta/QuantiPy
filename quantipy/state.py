from enum import IntEnum, auto


class TradeState(IntEnum):
    INITIALIZED = auto()
    READY_NEXT = auto()
    SHORTING = auto()
    LONGING = auto()
    CLOSED = auto()
