from blankly.data.data_reader import PriceReader

from tests.utils.mock.exchange import Mock


def test_foo():
    ex = Mock(
        readers=[
            PriceReader(
                "/home/muto/src/personal/2024/QuantiPy/tests/strategies/data/pine_wave_technologies.csv",
                "FOO-USDT",
            )
        ],
        resolution=1800,
        account={
            "FOO": {"available": 0},
            "USDT": {"available": 1000},
            "USDT": {"available": 1000},
        },
    )
    res = ex.interface.market_order("FOO-USDT", "buy", 1)
    pass
