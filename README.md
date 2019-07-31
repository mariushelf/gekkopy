# GekkoPy

Python library to interact with the Gekko trading bot found at
https://github.com/askmike/gekko.

# Author

Marius Helf

# Installation and Requirements

1. Install Gekko
2. Start Gekko
3. Clone this repository
4. Enjoy Gekko in Python!

# Accessing the Gekko Server from Python

You can access the Gekko server from Python to pull candle data or run backtests.

## Pulling Candle Data

```python
from gekkopy.gekko_client import GekkoClient

gekko = GekkoClient('http://localhost:3000')
data = gekko.pull_candles(
    'binance', 'BTC', 'USDT', 
    candlesize=60,
    date_start='2019-01-01', date_end='2019-06-01')
```

## Backtesting your Strategy

```python
from gekkopy.gekko_client import GekkoClient

gekko = GekkoClient('http://localhost:3000')

macd_cfg = {
    'short': 10,
    'long': 21,
    'signal': 9,
    'thresholds': {
        'down': -0.025,
        'up': 0.025,
        'persistence': 1,
    }
}
bt_config = gekko.build_backtest_config(
    exchange='binance', 
    asset='BTC', 
    currency='USDT', 
    candlesize=360, 
    strategy='MACD',
    strat_config=macd_cfg, 
    date_start='2019-01-01', 
    date_end='2019-06-01'
)

report, jdf, profits = gekko.backtest(bt_config)

print(report)
# {'startTime': '2019-02-19 23:59:00',
#  'endTime': '2019-06-01 00:01:00',
#  'timespan': '3 months',
#  'market': 118.83289531934932,
#  'balance': 5605.98664554,
#  'profit': 1598.1966455399997,
#  'relativeProfit': 39.87725518402908,
#  'yearlyProfit': 5779.418924137776,
#  'relativeYearlyProfit': 144.20463457760448,
#  'startPrice': 3699.94,
#  'endPrice': 8551.53,
#  'trades': 34,
#  'startBalance': 4007.79,
#  'exposure': 0.4925674839454903,
#  'sharpe': 13.77354874158137,
#  'downside': -2.5799428969375042,
#  'alpha': 1479.3637502206504}


# visualize backtest
gekko.plot_stats(jdf, profits, figsize=(10,10));
```

# Running Python Strategies in Gekko

1. implement the [`Strategy`](gekkopy/serving.py) class
2. register your class with the [`StratServer`](gekkopy/serving.py)
3. start the `StartServer`
4. copy the [`RESTAPI.js`](gekko_strategy/RESTAPI.js) strategy into the `strategies` 
   folder of your Gekko installation
5. copy the [`RESTAPI.toml`](gekko_strategy/RESTAPI.toml) configuration into the 
   `config/strageies` folder of your Gekko installation
6. run the strategy from the Gekko UI. Just make sure to adjust the URL to your
   StratServer and make sure that the last part of the `url` config field
   matches the name under which you registered your strategy.
   
## Example
Here's an [example](scripts/examples/run_dummy_strategy_server.py) of a dummy strategy:
```python
from gekkopy.serving import Strategy, StratServer
import numpy as np


class DummyStrategy(Strategy):
    """ Strategy that creates random advice, just to demo how to implement the
    interface. """

    def __init__(self):
        super().__init__()

    def window_size(self):
        return 5

    def advice(self, data):
        cond = np.ceil(np.sum(data)) % 3
        if cond == 1:
            return self.LONG
        elif cond == 2:
            return self.SHORT
        else:
            return self.HOLD


if __name__ == "__main__":
    dummy_strat = DummyStrategy()
    StratServer.register("dummy", dummy_strat)
    StratServer.start('localhost', port=2626, debug=True)
```

Now you're ready to give (random) advice!

After running this script, you can use the RESTAPI strategy in Gekko. Make sure to
change the last part of the url to `dummy`.
```toml
url = "http://localhost:2626/strats/dummy"  # no trailing slash!
```

# Source Code

The original sourcecode can be found at https://github.com/mariushelf/gekkopy.
