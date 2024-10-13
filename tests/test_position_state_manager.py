from quantipy.position import Position
from quantipy.trade import PositionStateManager


def test_manager_new():
    state = PositionStateManager()
    symbol = "FOO-USD"
    base, quote = symbol.split("-")

    # This will be mostly default values
    position = state.new(base)
    assert position is state.get(base)
    assert position == Position()._replace(symbol=base)


def test_manager_delete():
    state = PositionStateManager()
    symbol = "FOO-USD"
    base, quote = symbol.split("-")

    # Make new position
    position = state.new(base)
    assert state.get(base) is position

    # Delete it
    state.delete(base)
    assert state.get(base) is None


def test_manager_set():
    state = PositionStateManager()
    symbol = "FOO-USD"
    base, quote = symbol.split("-")

    # Make new position
    original = state.new(base)
    assert state.get(base) is original

    # Update position entry price
    price = 42
    position = state.set(base, entry=price)
    assert position == original._replace(entry=price)
    assert position is not original
