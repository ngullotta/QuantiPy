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

        overall_wins, total = 0, 0
        for symbol, orders in orders_list.items():
            wins = 0
            for buy, sell in zip(orders[::2], orders[1::2]):
                if buy["price"] < sell["price"]:
                    wins += 1
            overall_wins += wins
            total += len(orders)
            print(
                "Win Percentage [%s] (%.2f) => %d wins / %d total orders"
                % (symbol, wins / len(orders), wins, len(orders))
            )
        print(
            "Win Percentage [Overall] (%.2f) => %d wins / %d total orders"
            % (wins / total, overall_wins, total)
        )


if __name__ == "__main__":
    main()
