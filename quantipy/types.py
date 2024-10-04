from typing import Callable, Deque, Dict, List, Union

from quantipy.position import Position

Callback = Callable[..., None]
EventCallbacks = Dict[str, List[Callback]]
HistoricalData = Dict[str, Dict[str, Union[Deque, List]]]
PositionList = List[Position]
Positions = Dict[str, PositionList]
