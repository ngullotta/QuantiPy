def test_foo(exchange):
    res = exchange.interface.market_order("FOO-USD", "buy", 1)
    cash = exchange.interface.cash
    price = exchange.interface.get_price("FOO-USD")
    pass
