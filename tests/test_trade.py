from quantipy.state import TradeState
from quantipy.trade import TradeManager
from quantipy.position import Position


def test_trade_manager_long(state):
    manager = TradeManager()
    symbol = "FOO-USD"
    price = state.interface.get_price(symbol)
    # Need to record quantity here because the state will change
    quantity = manager.quantity(price, state)
    position = manager.order(price, symbol, state)
    assert position.open == True
    assert position.full_symbol == symbol
    assert position.symbol == symbol.split("-")[0]
    assert position.state == TradeState.LONGING
    assert position.entry == price
    assert position.size == quantity
    assert position.stop_loss == price * (1 - manager.default_stop_loss_pct)
    assert position.take_profit == price * (
        1 + (manager.default_stop_loss_pct * manager.default_risk_ratio)
    )


def test_trade_manager_short(state):
    manager = TradeManager()
    symbol = "FOO-USD"
    price = state.interface.get_price(symbol)
    # Need to record quantity here because the state will change
    quantity = manager.quantity(price, state)
    position = manager.order(price, symbol, state, side="sell")
    assert position.open
    assert position.full_symbol == symbol
    assert position.symbol == symbol.split("-")[0]
    assert position.state == TradeState.SHORTING
    assert position.entry == price
    assert position.size == quantity
    # Same as the long test just flip the operands
    assert position.stop_loss == price * (1 + manager.default_stop_loss_pct)
    assert position.take_profit == price * (
        1 - (manager.default_stop_loss_pct * manager.default_risk_ratio)
    )


def test_trade_manager_close(state):
    manager = TradeManager()
    symbol = "FOO-USD"
    base = symbol.split("-")[0]
    # Price is memoized in this interface
    price = state.interface.get_price("FOO-USD")
    original = manager.state.new(
        base,
        entry=price * 0.90,
        size=1,
        state=TradeState.LONGING,
        open=True,
        full_symbol=symbol,
    )
    current = state.interface.cash
    position = manager.close(original, state)

    assert not position.open
    assert position.full_symbol == symbol
    assert position.symbol == base
    assert position.state == TradeState.CLOSED
    assert state.interface.cash > current
    assert state.interface.cash == current + (price * original.size)


def test_manager_order_zero_size(state, caplog) -> None:
    manager = TradeManager()
    symbol = "FOO-USD"
    base = symbol.split("-")[0]
    quote = symbol.split("-")[-1]
    state.interface.account[quote]["available"] = 0
    position = manager.order(42, symbol, state)
    assert position == Position()
    for record in caplog.records:
        assert record.levelname == "ERROR"
        assert record.msg != ""