import json
from pathlib import Path
from typing import Union


class SplitProtector:
    def __init__(self, path: Union[Path, str]) -> None:
        self.path = Path(path)
        self.data = {}

        with open(self.path) as fp:
            self.data = json.load(fp)

    def safe(self, symbol: str, timestamp: int) -> bool:
        if symbol not in self.data:
            return True

        for split in self.data[symbol]:
            if split["start"] < timestamp < split["end"]:
                return False
        return True
