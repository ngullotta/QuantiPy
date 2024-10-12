from pathlib import Path

import pytest
from blankly.data.data_reader import PriceReader

from tests.utils.mock.exchange import Mock


@pytest.fixture(scope="module")
def exchange():
    readers = [
        PriceReader(str(path.resolve()), f"{path.stem.upper()}-USD")
        for path in (Path(__file__).parent / "data").glob("*.csv")
    ]
    account = {
        "USD": {
            "available": 1000
        }
    }
    yield Mock(readers=readers, resolution=1800, account=account)
