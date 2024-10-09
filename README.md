# QuantiPy

QuantiPy is a Python crypto and securities trading bot with various trading
patterns and strategies using Blankly as the backend.

Strategies are written using the Blankly Model API and then run on the command
line. In using Blankly, the strategies can easily be backtested before use.

These are my personal strategies and are ***categorically and unequivocally
unfit for use in real markets***. 

As the saying goes: "A fool and his money are soon parted"

## Currently supported Strategies

- Stochastic  
  - `HarmonicOscillators`
    - A complex strategy that can detect swings in momentum before the regular 
    indicators. Buy positions are taken up when all of the following criteria are met:
      - The Stochastic RSI %K and %D must have been below 20 in the last 2 periods
        - This volatile RSI indicates the symbol is oversold (even when the regular RSI 
        does not)
      - The RSI must be above 50
        - This indicates that the symbol is still bullish (despite the earlier Stochastic 
        RSI)
      - The MACD must cross the signal line to confirm the uptrend
      - The Stochastic RSI %K and %D must not *currently* be oversold (above 20)
    - With all these criteria being met, a buy position is taken up. The reverse is true 
    for a selling position
      - I.e The Stochastic RSI %K and %D must have been above 80, the RSI below 50, MACD 
      crossing down etc.

- RSI
  - `Oversold`
    - A simple strategy where buy positions are taken up when the RSI is less than 30 
    (indicating the symbol is oversold) and sell positions are taken up when the RSI is 
    above 70 (indicating the symbol is overbought)

## Installation

To get started with QuantiPy, follow these steps

### Prerequisites

- Python `3.9` or higher
- Poetry for dependency management
  - If you don't (or can't) have poetry installed, just use the
  `pyproject.toml` file and install all dependencies from the
  `[tool.poetry.dependencies]` section

### Setup

1. **Clone the repository:**

   ```bash
   git clone ...
   cd QuantiPy
   ```

2. **Install the dependencies:**

    ```bash
    poetry install
    ```

3. **Run a strategy backtest:**

    ```bash
    poetry run python run.py <strategy> <exchange> --symbol BTC-USDT --backtest
    ```

    - By default `--live` is false to prevent accidental losses
    - Default starting cash for the backtest is:
        - ***$1000 USD*** if using regular securities through Alpaca
        - ***$1000 USDT*** if using crypto through Binance

## Usage

  Simple backtest of Bitcoin on Binance using the Stochastic + RSI + MACD strategy
  ```bash
  $ poetry run python run.py HarmonicOscillators Binance --symbol BTC-USDT --backtest
  ```

  Strategies are currently built with a "multi-symbol-multi-position" sub-strategy

### Example strategy backtesting graph

Backtest of `HarmonicOscillators`
![An example backtest output](./Stoch+RSI+MACD-Backtest.png)

## Contributing

Contributions are welcome! Please read the contributing guidelines for more details.

## License

This project is licensed under the GNU General Public License v3.0 - see the
`LICENSE` file for details.

## Acknowledgments

Special thanks to the Blankly project for building the backend that makes these
strategies so simple to implement. It really takes the headache out of it!

## @ToDo:

- ~~Add simple conversion to screener via CLI switch~~
- ~~Tests~~
  - I wrote these pretty quick, will make them much easier to understand later
- Add more strategies
- Much better logging and/or csv output
- ~~Add stop loss and take profit handlers~~
- ~~Improve open position detection~~
