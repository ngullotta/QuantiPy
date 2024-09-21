import json
import logging
import warnings
from argparse import ArgumentParser

from blankly import Binance, PaperTrade

from quantipy.logger import QuantiPyLogger
from quantipy.strategies import StochasticRSIWithRSIAndMACD

STRATEGIES = {"StochasticRSIWithRSIAndMACD": StochasticRSIWithRSIAndMACD}
EXCHANGES = {"Binance": Binance, "PaperTrade": PaperTrade}


def setupLogger():
    logger = logging.getLogger()
    console = logging.StreamHandler()
    formatter = QuantiPyLogger()
    console.setFormatter(formatter)
    console.setLevel(logging.DEBUG)
    logger.addHandler(console)
    logger.setLevel(logging.DEBUG)


def main():
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
        nargs="+",
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

    args = parser.parse_args()

    exchange = args.exchange(portfolio_name=args.portfolio)

    initial = {}
    if args.exchange == Binance:
        initial["USDT"] = 1000
    else:
        initial["USD"] = 1000

    if not args.live:
        exchange = PaperTrade(exchange, initial_account_values=initial)

    strategy = args.strategy(exchange)

    for symbol in args.symbols:
        strategy.add_price_event(
            strategy.on_event,
            symbol=symbol,
            resolution=args.resolution,
            init=strategy.init,
        )

    if args.backtest:
        with warnings.catch_warnings():
            logger = logging.getLogger()
            warnings.simplefilter("ignore")
            res = strategy.backtest(to=args.to, initial_values=initial)
            with open(f"{args.strategy.__name__}_results.json", "w") as fp:
                json.dump(res.to_dict(), fp, indent=4)
                logger.info("Wrote backtest results to `%s`", fp.name)
        exit()

    strategy.start()


if __name__ == "__main__":
    main()
