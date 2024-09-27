import json
from argparse import ArgumentParser
from pathlib import Path

from bokeh.layouts import column, gridplot
from bokeh.models import ColumnDataSource
from bokeh.plotting import figure, show
from pandas import DataFrame, concat, read_csv, to_datetime, to_numeric
from ta.momentum import RSIIndicator, StochRSIIndicator


def get_price_data(symbol: str, start: int, end: int) -> DataFrame:
    data = []
    for _file in Path("./price_caches").glob("*%s*.csv" % symbol):
        data.append(read_csv(_file))
    df = concat(data)
    df["time"] = to_numeric(df["time"], downcast="integer")
    return df.drop_duplicates(subset="time").sort_values(by="time")


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
        start = int(data["start_time"])
        end = int(data["stop_time"])

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
        if (data := get_price_data(symbol, start, end)) is not None:
            data["price"] = data["close"]
            data["time"] = to_datetime(data["time"], unit="s")
            data["rsi"] = RSIIndicator(data["close"]).rsi()
            data["stoch_rsi"] = StochRSIIndicator(data["close"]).stochrsi()
            data["stoch_rsi_k"] = (
                StochRSIIndicator(data["close"]).stochrsi_k() * 100
            )
            data["stoch_rsi_d"] = (
                StochRSIIndicator(data["close"]).stochrsi_d() * 100
            )
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

        volume_plot = figure(
            title="Volume",
            tools="xpan, xwheel_zoom, reset",
            x_axis_type="datetime",
            width=800,
            height=100,
            x_range=p.x_range,
        )

        volume_plot.vbar(
            x="time",
            top="volume",
            width=86400 * 1000,
            color="blue",
            source=ColumnDataSource(data),
        )

        rsi_plot = figure(
            title="RSI",
            tools="xpan, xwheel_zoom, reset",
            x_axis_type="datetime",
            width=800,
            height=200,
            x_range=p.x_range,
        )
        rsi_plot.line(
            x="time",
            y="rsi",
            line_width=2,
            color="orange",
            source=ColumnDataSource(data),
        )

        stoch_rsi_plot = figure(
            title="RSI",
            tools="xpan, xwheel_zoom, reset",
            x_axis_type="datetime",
            width=800,
            height=200,
            x_range=p.x_range,
        )
        stoch_rsi_plot.line(
            x="time",
            y="stoch_rsi_k",
            line_width=2,
            color="blue",
            source=ColumnDataSource(data),
        )
        stoch_rsi_plot.line(
            x="time",
            y="stoch_rsi_d",
            line_width=2,
            color="orange",
            source=ColumnDataSource(data),
        )

        plots.append(column(p, volume_plot, stoch_rsi_plot, rsi_plot))

    # Arrange plots in a grid
    grid = gridplot(plots, ncols=1)
    show(grid)


if __name__ == "__main__":
    main()
