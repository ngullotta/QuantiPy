from blankly.data.data_reader import PriceReader

from tests.utils.mock.exchange import Mock


def test_foo():
    ex = Mock(
        readers=[
            PriceReader(
                "/home/muto/src/personal/2024/QuantiPy/tests/strategies/data/pine_wave_technologies.csv",
                "FOO-USD",
            )
        ],
        resolution=1800,
        account={
            "USD": {"available": 1000}
        },
    )
    res = ex.interface.market_order("FOO-USD", "buy", 1)
    cash = ex.interface.cash
    pass
