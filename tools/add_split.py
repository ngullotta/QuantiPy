import collections
import json
from argparse import ArgumentParser
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


def main() -> None:
    parser = ArgumentParser(
        description="""
        CLI tool to add split timestamps to the slipts file.

        Timestamps are calculated in US/Eastern offsets unless otherwise
        specified.
        """
    )

    parser.add_argument(
        "symbol", type=str, help="Path of the backtest results"
    )

    parser.add_argument("date", type=str, help="The date in YYYY-mm-dd format")

    parser.add_argument(
        "--tz", type=ZoneInfo, default="US/Eastern", help="The timezone offset"
    )

    parser.add_argument(
        "--pad", type=int, default=1, help="Pad X days out from start"
    )

    args = parser.parse_args()

    splits_path = Path("./splits.json")
    if not splits_path.exists():
        print("Could not find splits.json along %s" % splits_path)
        exit(1)

    with open(splits_path) as fp:
        data = json.load(fp)

    date = datetime.strptime(args.date, "%Y-%m-%d").astimezone(args.tz)

    if args.symbol not in data:
        data[args.symbol] = []

    for obj in data[args.symbol]:
        if obj["start"] == date.timestamp():
            print(
                "%s -> %d already configured" % (args.date, date.timestamp())
            )
            exit()

    data[args.symbol].append(
        {
            "start": int(date.timestamp() - (86400 * args.pad)),
            "end": int(date.timestamp() + (86400 * args.pad)),
        }
    )

    with open(splits_path, "w") as fp:
        ordered = collections.OrderedDict(data.items())
        json.dump(ordered, fp, indent=4)


if __name__ == "__main__":
    main()
