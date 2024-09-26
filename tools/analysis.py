import json
from argparse import ArgumentParser
from collections import defaultdict
from pathlib import Path


def main() -> None:  # noqa: C901
    parser = ArgumentParser(
        description="""
        CLI tool to analyze backtest json files.

        Shows relevant stats like win percentage etc.
        """
    )

    parser.add_argument(
        "path",
        type=Path,
        help="Path of the backtest results",
    )

    args = parser.parse_args()

    if not args.path.exists():
        print('Could not find file along path "%s"' % args.path)
        exit(1)

    with open(args.path) as fp:
        data = json.load(fp)
        orders = data["trades"]["created"]

        orders_list = defaultdict(list)
        for order in orders:
            symbol = order["symbol"]
            orders_list[symbol].append(
                {"side": order["side"], "price": order["price"]}
            )

        for symbol, orders in orders_list.items():
            wins, pairs = 0, 0
            for buy, sell in zip(orders[::2], orders[1::2]):
                pairs += 1
                if buy["price"] < sell["price"]:
                    wins += 1
            print(
                "Win Percentage [%s] ~> (%d%%) => %d wins / %d trades"
                % (symbol, int((wins / pairs) * 100), wins, pairs)
            )


if __name__ == "__main__":
    main()
