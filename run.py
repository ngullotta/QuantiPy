import json
import logging
import warnings
from argparse import ArgumentParser
from datetime import datetime
from sys import argv

from blankly import Alpaca, Binance, PaperTrade, Screener, ScreenerState

from quantipy.logger import QuantiPyLogger
from quantipy.strategies import (
    AdvancedHarmonicOscillators,
    HarmonicOscillators,
    Oversold,
)

STRATEGIES = {
    "AdvancedHarmonicOscillators": AdvancedHarmonicOscillators,
    "HarmonicOscillators": HarmonicOscillators,
    "Oversold": Oversold,
}
EXCHANGES = {"Binance": Binance, "PaperTrade": PaperTrade, "Alpaca": Alpaca}


def setupLogger() -> None:
    logger = logging.getLogger()
    console = logging.StreamHandler()
    formatter = QuantiPyLogger()
    console.setFormatter(formatter)
    console.setLevel(logging.DEBUG)
    logger.addHandler(console)
    logger.setLevel(logging.DEBUG)


def main() -> None:  # noqa: C901
    setupLogger()

    parser = ArgumentParser(
        description="""
        CLI tool to start the trading bot.

        By default all trades are paper unless --live is passed in.

        Specify the strategy and symbols to begin trading.
        """
    )

    parser.add_argument(
        "strategy",
        type=STRATEGIES.get,
        help="The name of the strategy to use",
    )

    parser.add_argument(
        "exchange",
        type=EXCHANGES.get,
        help="The name of the exchange to use",
    )

    parser.add_argument(
        "-ls",
        action="store_true",
        default=False,
        help="Print all available strategies and exchanges, then exit",
    )

    parser.add_argument(
        "--backtest",
        action="store_true",
        default=False,
        help="Backtest the strategy",
    )

    parser.add_argument(
        "-r",
        "--resolution",
        default="30m",
        help="Time domain resolution",
    )

    parser.add_argument(
        "-p",
        "--portfolio",
        type=str,
        help="The name of the portfoloio to use (see keys.json)",
    )

    parser.add_argument(
        "--to", type=str, default="1y", help='Timeframe to backtest: e.g "1y"'
    )

    parser.add_argument(
        "--live",
        action="store_true",
        default=False,
        help="Run the strategy in live mode",
    )

    parser.add_argument(
        "-sym",
        "--symbol",
        action="append",
        dest="symbols",
        required=True,
        help="One or more symbols to process",
    )

    parser.add_argument(
        "--as-screener",
        action="store_true",
        default=False,
        help='Use the strategy in "Screener" mode',
    )

    parser.add_argument(
        "-l", "--log-level", type=logging.getLogger().setLevel, default="INFO"
    )

    parser.add_argument(
        "-as",
        "--all-symbols",
        action="store_true",
        default=False,
        help="Use all symbols traded in a given exchange (Not recommended)",
    )

    parser.add_argument(
        "--top",
        type=int,
        default=10,
        help="When using symbol lists, use top X symbols",
    )

    parser.add_argument(
        "--dump-audit",
        action="store_true",
        default=False,
        help="Dump the strategy audit log for analysis",
    )

    if len(argv) > 1 and argv[1] == "-ls":
        print("Available strategies:")
        for st in sorted(STRATEGIES.keys()):
            print("" * 4, st, end="")
            print("" * 8, STRATEGIES[st].__doc__)
        print("\nAvailable exchanges:")
        for ex in sorted(EXCHANGES.keys()):
            print("" * 4, ex)
        exit()

    args = parser.parse_args()

    logger = logging.getLogger()

    exchange = args.exchange(portfolio_name=args.portfolio)

    initial = {}
    if args.exchange == Binance:
        initial["USDT"] = 1000
    else:
        initial["USD"] = 1000

    if not args.live:
        exchange = PaperTrade(exchange, initial_account_values=initial)

    strategy = args.strategy(exchange)

    if len(args.symbols) == 1 and args.symbols[0] in ["NASDAQ100"]:
        # Select the top 10 of these lists
        _list = args.symbols[0]
        with open("symbols.json") as fp:
            data = json.load(fp)
            if _list in data:
                args.symbols = data[_list][: args.top]

    if args.backtest:
        with open("backtest.json") as fp:
            data = json.load(fp)
            settings = data.get("settings", {})
            benchmark = settings.get("benchmark_symbol")
            if benchmark and benchmark not in args.symbols:
                logging.info(
                    "Benchmark symbol %s not in symbols, adding it now",
                    benchmark,
                )
                args.symbols.append(benchmark)

                # We need this in the backtest data but don't
                # necessarily want to actually *trade* it
                strategy.blacklist.append(benchmark)

    for symbol in args.symbols:
        logger.info("Tracking symbol: %s", symbol)
        strategy.add_price_event(
            strategy.tick,
            symbol=symbol,
            resolution=args.resolution,
            init=strategy.init,
        )

    if args.backtest:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            res = strategy.backtest(to=args.to, initial_values=initial)
            with open(f"{args.strategy.__name__}_results.json", "w") as fp:
                json.dump(res.to_dict(), fp, indent=4)
                logger.info("Wrote backtest results to `%s`", fp.name)
        if args.dump_audit and strategy._audit != {}:
            with open(f"{strategy.__class__.__name__}_audit.json", "w") as fp:
                json.dump(strategy._audit, fp, indent=4)
        exit()

    if args.as_screener:

        def init(state: ScreenerState) -> None:
            state.resolution = args.resolution

        def formatter(results: dict, state: ScreenerState) -> None:
            outupt = datetime.now().strftime("%c") + ":\n"
            for symbol in results:
                if results[symbol]["buy"]:
                    outupt += "[%s] %s\n" % (symbol, results[symbol]["buy"])
            print(outupt)

        Screener(
            exchange,
            strategy.screener,
            symbols=args.symbols,
            init=init,
            formatter=formatter,
        )

    strategy.start()


if __name__ == "__main__":
    main()
