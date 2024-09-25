import json
from argparse import ArgumentParser
from pathlib import Path

from bokeh.layouts import gridplot
from bokeh.models import ColumnDataSource
from bokeh.plotting import figure, show
from pandas import DataFrame, read_csv, to_datetime


def get_price_data(symbol: str, start: int = None) -> DataFrame:
    glob = "*%s,%s*.csv" % (symbol, str(start) if start else "")
    for _file in Path("./price_caches").glob(glob):
        return read_csv(_file)


def main() -> None:  # noqa: C901
    parser = ArgumentParser(
        description="""
        CLI tool to analyze backtest json files.

        Points are plotted on graphs of relevant symbols showing entry
        and exit points.
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
        start = int(data["history"][0]["time"])

    df = DataFrame(orders)
    df["time"] = to_datetime(df["time"], unit="s")

    grouped = df.groupby("symbol")

    plots = []
    for symbol, group in grouped:
        p = figure(
            title=f"{symbol} Market Orders",
            x_axis_type="datetime",
            min_width=800,
            min_height=400,
        )

        # Plot buy orders
        buy_orders = group[group["side"] == "buy"]
        p.scatter(
            marker="circle",
            x="time",
            y="price",
            size=10,
            color="green",
            alpha=0.5,
            legend_label="Buy",
            source=ColumnDataSource(buy_orders),
        )

        # Plot sell orders
        sell_orders = group[group["side"] == "sell"]
        p.scatter(
            marker="triangle",
            x="time",
            y="price",
            size=10,
            color="red",
            alpha=0.5,
            legend_label="Sell",
            source=ColumnDataSource(sell_orders),
        )

        # Plot symbol price as a grey line
        if (data := get_price_data(symbol, start)) is not None:
            data["price"] = data["close"]
            data["time"] = to_datetime(data["time"], unit="s")
            p.line(
                x="time",
                y="price",
                line_width=2,
                color="grey",
                alpha=0.7,
                legend_label="Price",
                source=data,
            )

        p.legend.location = "top_left"
        p.xaxis.axis_label = "Time"
        p.yaxis.axis_label = "Price"

        plots.append(p)

    # Arrange plots in a grid
    grid = gridplot(plots, ncols=2)
    show(grid)


if __name__ == "__main__":
    main()
