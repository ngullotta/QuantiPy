import json
import sys
from bokeh.plotting import figure, show
import pandas as pd
from datetime import datetime
from bokeh.plotting import figure, show, output_file
from bokeh.layouts import gridplot
from bokeh.io import output_notebook
from bokeh.models import ColumnDataSource
import yfinance as yf
from pathlib import Path

def get_price_data(symbol):
	for _file in Path("./price_caches").glob(f"*{symbol}*.csv"):
		return pd.read_csv(_file)

for _file in sys.argv[1:]:
	with open(_file) as fp:
		data = json.load(fp)
		orders = data["trades"]["created"]
		start = datetime.fromtimestamp(data["history"][0]["time"]).strftime("%Y-%m-%d")
		end = datetime.fromtimestamp(data["history"][-1]["time"]).strftime("%Y-%m-%d")
		df = pd.DataFrame(orders)
		# Convert time strings to datetime objects
		df['time'] = df['time'].apply(lambda x: int(x))
		df['time'] = pd.to_datetime(df['time'], unit="s")
		# Group data by security
		grouped = df.groupby('symbol')
		print(df)
		#output_notebook()

		plots = []

		for security, group in grouped:
			p = figure(title=f"{security} Market Orders", x_axis_type='datetime', min_width=800, min_height=400)
			
			# Create a ColumnDataSource
			source = ColumnDataSource(group)
			
			# Plot buy orders
			buy_orders = group[group['side'] == 'buy']
			p.circle(x='time', y='price', size=10, color='green', alpha=0.5, legend_label='Buy', source=ColumnDataSource(buy_orders))
			
			# Plot sell orders
			sell_orders = group[group['side'] == 'sell']
			p.triangle(x='time', y='price', size=10, color='red', alpha=0.5, legend_label='Sell', source=ColumnDataSource(sell_orders))
			
			# Plot security price as a grey line
			data = get_price_data(security)
			data['price'] = data['close']
			data['time'] = pd.to_datetime(data['time'], unit="s")
			print(data)
			p.line(x='time', y='price', line_width=2, color='grey', alpha=0.7, legend_label='Price', source=data)
			
			p.legend.location = "top_left"
			p.xaxis.axis_label = 'Time'
			p.yaxis.axis_label = 'Price'
			
			plots.append(p)

		# Arrange plots in a grid
		grid = gridplot(plots, ncols=2)
		show(grid)
