import json
from pathlib import Path

import pytest
from blankly import StrategyState
from blankly.data.data_reader import PriceReader

from quantipy.strategies.simple import SimpleStrategy
from tests.utils.mock.exchange import Mock


@pytest.fixture
def exchange(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"settings": {"mock": {"cash": "USD"}}}))
    readers = [
        PriceReader(str(path.resolve()), f"{path.stem.upper()}-USD")
        for path in (Path(__file__).parent / "data").glob("*.csv")
    ]
    account = {"USD": {"available": 1000, "hold": 0}}
    yield Mock(
        readers=readers, resolution=1800, account=account, settings=path
    )


@pytest.fixture
def strategy(exchange) -> SimpleStrategy:
    yield SimpleStrategy(exchange)


@pytest.fixture
def state(strategy) -> StrategyState:
    yield StrategyState(
        strategy, {}, "FOO", strategy.interface.interface.resolution
    )
