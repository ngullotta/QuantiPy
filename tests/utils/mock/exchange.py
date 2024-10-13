from collections import defaultdict
from pathlib import Path
from random import choice
from time import time
from typing import Dict, List, Union
from unittest.mock import MagicMock
from uuid import uuid4

import blankly
from blankly.data.data_reader import PriceReader
from blankly.exchanges.exchange import Exchange
from blankly.exchanges.interfaces.exchange_interface import ExchangeInterface
from blankly.exchanges.interfaces.keyless.keyless import KeylessExchange
from blankly.exchanges.interfaces.keyless.keyless_api import KeylessAPI
from blankly.exchanges.interfaces.paper_trade.paper_trade_interface import (
    PaperTradeInterface,
)
from blankly.exchanges.orders.market_order import MarketOrder
from blankly.utils.utils import (
    AttributeDict,
    aggregate_prices_by_resolution,
    extract_price_by_resolution,
    get_base_asset,
    get_quote_asset,
)
from blankly.utils.exceptions import InvalidOrder
from pandas import DataFrame, to_datetime

Account = Dict[str, Dict[str, Dict]]
Time = Union[int, float, None]


def memoize(func):
    cache = {}

    def wrapper(*args):
        if args in cache:
            return cache[args]
        result = func(*args)
        cache[args] = result
        return result

    return wrapper


class API(ExchangeInterface):
    def __init__(
        self, readers: List[PriceReader], resolution: int, account: Account
    ) -> None:
        self._orders = []
        self._account = account
        self._price_data = defaultdict(dict)
        for reader in readers:
            for symbol in reader.data:
                self._maybe_initialize_symbol(symbol, starting_currency=1000)
                data = self._parse_raw_data(reader, resolution, symbol)
                self._price_data[symbol][resolution] = data
        super().__init__(self.get_exchange_type(), self)

    def _maybe_initialize_symbol(
        self, symbol: str, starting_currency: int = 0
    ) -> None:
        base, quote = get_base_asset(symbol), get_quote_asset(symbol)
        if base not in self._account:
            self._account[base] = AttributeDict(available=0, hold=0)

        if quote not in self._account:
            self._account[quote] = AttributeDict(
                available=starting_currency, hold=0
            )

    @staticmethod
    def _parse_raw_data(
        reader: PriceReader, resolution: int, symbol: str
    ) -> DataFrame:
        data = reader.data[symbol]
        data["time"] = to_datetime(data["time"], unit="s")
        data.set_index("time", inplace=True)
        data = data.resample(f"{resolution}s").mean()
        data["time"] = data.index.astype(int) // 10**9
        data.reset_index(drop=True, inplace=True)
        return data.ffill()

    def _can_we_afford_this(
        self, symbol: str, size: float, price: float
    ) -> bool:
        base, quote = get_base_asset(symbol), get_quote_asset(symbol)
        total_cost = size * price
        return self.account[quote]["available"] > total_cost

    @property
    def cash(self) -> float:
        return self.get_account("USD").get("available", 0)

    def init_exchange(self):
        pass

    def get_exchange_type(self):
        return "mock"

    def get_account(self, symbol: str = None) -> Dict:
        account = self._account
        if symbol and symbol in account:
            return account[symbol]
        return account

    def get_product_history(
        self, symbol: str, start: Time, stop: Time, resolution: int
    ):
        return extract_price_by_resolution(
            self._price_data, symbol, start, stop, resolution
        )

    def get_products(self) -> {}:
        products = []
        for symbol in self._price_data:
            products.append({"symbol": symbol})
        return products

    def market_order(self, symbol: str, side: str, size: float):
        price = self.get_price(symbol)
        if not self._can_we_afford_this(symbol, size, price):
            raise InvalidOrder("""
                You can not afford, 'ford
                Ford, my diamond sword, sword
                Even if you could, could
                I have a patent!
            """)
        base, quote = get_base_asset(symbol), get_quote_asset(symbol)
        data = {
            "id": str(uuid4()),
            "price": price * size,
            "size": size,
            "symbol": symbol,
            "side": side,
            "time_in_force": "GTC",
            "type": "Market",
            "created_at": int(time()),
            "status": "done",
        }
        order = MarketOrder(None, data, self)
        order.get_status = lambda: data
        self._orders.append(order)
        total = price * size
        if side == "sell":
            if base != quote:
                self._decrement_account_amount(base, size)
                self._increment_account_amount(quote, total)
        elif side == "buy":
            if base != quote:
                self._increment_account_amount(base, size)
                self._decrement_account_amount(quote, total)
        return order

    def _decrement_account_amount(self, symbol: str, size: float) -> None:
        self._account[symbol]["available"] -= size

    def _increment_account_amount(self, symbol: str, size: float) -> None:
        self._account[symbol]["available"] += size

    def take_profit_order(self, symbol: str, price: float, size: float):
        raise NotImplementedError

    def stop_loss_order(self, symbol: str, price: float, size: float):
        raise NotImplementedError

    def limit_order(self, symbol: str, side: str, price: float, size: float):
        raise NotImplementedError

    def cancel_order(self, symbol: str, order_id: str):
        raise NotImplementedError

    def get_open_orders(self, symbol: str = None) -> List[MarketOrder]:
        if symbol:
            return list(
                filter(lambda order: order["symbol"] == symbol), self._orders
            )
        return self._orders

    def get_order(self, symbol: str, order_id: str):
        raise NotImplementedError

    def get_order_filter(self, symbol: str) -> dict:
        return {
            "symbol": symbol,
            "base_asset": get_base_asset(symbol),
            "quote_asset": get_quote_asset(symbol),
            "max_orders": 1000000000000000,
            "limit_order": {
                # Minimum size to buy
                "base_min_size": 0.000000001,
                # Maximum size to buy
                "base_max_size": 1000000000000000,
                # Specifies the minimum increment for the base_asset
                "base_increment": 0.000000001,
                "price_increment": 0.000000001,
                "min_price": 0.000000001,
                "max_price": 1000000000000000,
            },
            "market_order": {
                "fractionable": True,
                # Minimum size to buy
                "base_min_size": 0.000000001,
                # Maximum size to buy
                "base_max_size": 1000000000000000,
                # Specifies the minimum increment
                "base_increment": 0.000000001,
                # Specifies the min order price as well as the price
                # increment
                "quote_increment": 0.000000001,
                "buy": {
                    "min_funds": 0.000000001,
                    "max_funds": 1000000000000000,
                },
                "sell": {
                    "min_funds": 0.000000001,
                    "max_funds": 1000000000000000,
                },
            },
            "exchange_specific": {},
        }

    def get_fees(self) -> dict:
        return {"maker_fee_rate": 0, "taker_fee_rate": 0}

    @memoize
    def get_price(self, symbol: str, time: Time = None) -> float:
        resolution = list(self._price_data[symbol].keys())[0]
        return choice(self._price_data[symbol][resolution]["close"])


class Mock(Exchange):
    def __init__(
        self,
        readers: List[PriceReader],
        resolution: int,
        account: Account,
        portfolio: str = None,
        settings: Path = None,
    ) -> None:
        calls = API(readers, resolution, account)
        Exchange.__init__(self, calls.get_exchange_type(), portfolio, settings)
        super().construct_interface_and_cache(calls)
        self.interface = calls

    def get_asset_state(self, symbol: str) -> Account:
        symbol = get_base_asset(symbol)
        account = self.interface.get_account(symbol=symbol)
        return account

    def get_exchange_state(self) -> List[Dict]:
        return self.interface.get_products()

    def get_direct_calls(self) -> API:
        return self.calls
