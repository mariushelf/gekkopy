from typing import Dict

import matplotlib.pyplot as plt
import matplotlib
import pandas as pd
import requests


class GekkoClient:
    def __init__(self, url="http://localhost:3000"):
        self.url = url
        self.api = f"{url}/api"

    def get(self, endpoint: str):
        """ Send GET request to Gekko and return parsed JSON.

        Parameters
        ----------
        endpoint
            which endpoint to call, excluding `/api`

        Returns
        -------
        response:
            response as parsed JSON
        """
        res = requests.get(f"{self.api}/{endpoint}")
        res.raise_for_status()
        return res.json()

    def post(self, endpoint, request=None):
        """ Send POST request to Gekko and return parsed JSON.

        Parameters
        ----------
        endpoint
            which endpoint to call, excluding `/api`
        request
            data to add to the POST request as JSON

        Returns
        -------
        response:
            response as parsed JSON

        """
        if request is None:
            request = {}
        res = requests.post(f"{self.api}/{endpoint}", json=request)
        res.raise_for_status()
        return res.json()

    def pull_dataranges(self) -> pd.DataFrame:
        """ Pulls data ranges from Gekko. This is what you see at the top of Gekko's
        `Backtest` page. """
        data = self.post("scansets")
        dataranges = pd.DataFrame(data["datasets"])
        dataranges = (
            dataranges.join(
                dataranges["ranges"]
                .apply(pd.Series)
                .reset_index()
                .melt(id_vars="index")
                .dropna()[["index", "value"]]
                .set_index("index")
            )
            .drop("ranges", axis=1)
            .rename(dict(value="range"), axis=1)
            .dropna(subset=["range"])
        )
        dataranges["from"] = pd.to_datetime(
            dataranges.range.apply(lambda x: x["from"]), unit="s"
        )
        dataranges["to"] = pd.to_datetime(
            dataranges.range.apply(lambda x: x["to"]), unit="s"
        )
        dataranges = dataranges.drop("range", axis=1)

        return dataranges

    def build_backtest_config(
        self,
        exchange,
        asset,
        currency,
        candlesize,
        strategy,
        strat_config,
        date_start=None,
        date_end=None,
    ):
        """ Helper function to create the configuration for a backtest  from a few
        simple input parameters.
        Can be passed to the :meth:`.backtest` function

        Parameters
        ----------
        exchange
            on which exchange to backtest
        asset
            asset
        currency
            currency
        candlesize
            candlesize
        strategy
            name of gekko strategy
        strat_config
            dictionary with strategy config
        date_start
            start date as iso string or python date
        date_end
            start date as iso string or python date

        Returns
        -------
        dict
            configuration dictionary

        """
        cfg_template = {
            "watch": {},
            "paperTrader": {
                "feeMaker": 0.25,
                "feeTaker": 0.25,
                "feeUsing": "maker",
                "slippage": 0.05,
                "simulationBalance": {"asset": 1, "currency": 100},
                "reportRoundtrips": True,
                "enabled": True,
            },
            "tradingAdvisor": {"enabled": True, "historySize": 200},
            "backtest": {"daterange": {}},
            "backtestResultExporter": {
                "enabled": True,
                "writeToDisk": False,
                "data": {
                    "stratUpdates": True,
                    "roundtrips": True,
                    "stratCandles": True,
                    "stratCandleProps": ["open", "high", "low", "close"],
                    "trades": True,
                },
            },
            "performanceAnalyzer": {"riskFreeReturn": 2, "enabled": True},
        }

        # auto-impute date_start/date_end with min/max of first matching range
        if date_start is None or date_end is None:
            dr = self.pull_dataranges()
            dr = dr[
                (dr.exchange == exchange)
                & (dr.asset == asset)
                & (dr.currency == currency)
            ]
            if len(dr) == 0:
                raise ValueError(
                    f"no data ranges match specified exchange/asset/currency "
                    f"combination ({asset}/{currency}@{exchange})"
                )
            if date_start is None:
                date_start = dr.iloc[0, :]["from"]
            if date_end is None:
                date_end = dr.iloc[0, :]["to"]
        if date_start is not None:
            date_start = pd.to_datetime(date_start)
        if date_end is not None:
            date_end = pd.to_datetime(date_end)

        # fill config template
        cfg = cfg_template.copy()
        cfg[strategy] = strat_config
        cfg["tradingAdvisor"]["method"] = strategy
        cfg["tradingAdvisor"]["candleSize"] = candlesize
        cfg["watch"] = dict(exchange=exchange, currency=currency, asset=asset)
        cfg["backtest"]["daterange"]["from"] = date_start.isoformat()
        cfg["backtest"]["daterange"]["to"] = date_end.isoformat()
        return cfg

    def backtest(self, config):
        """ Run a backtest on gekko and calculate statistics.

        Parameters
        ----------
        config
            configuration dictionary as constructec by :meth:`.build_backtest_config`.

        Returns
        -------
        report : Dict
            performance report as returned by Gekko
        jdf : pd.DataFrame
            joint dataframe with all information over time
        profits : pd.DataFrame
            profit per month for market ("HODL") and the strategy under test
            
        See Also
        --------
        * :meth:`._assemble_joint_df`
        * :meth:`.plot_stats`
        * :meth:`.build_backtest_config`
        """
        res = self.post("backtest", config)

        roundtrips = pd.DataFrame(res["roundtrips"])
        roundtrips.entryAt = pd.to_datetime(roundtrips.entryAt, unit="s")
        roundtrips.exitAt = pd.to_datetime(roundtrips.exitAt, unit="s")

        candles = pd.DataFrame(res["stratCandles"]).set_index("start")
        indicators = pd.DataFrame(res["stratUpdates"]).set_index("date")
        trades = pd.DataFrame(res["trades"]).set_index("date")

        candles.index = pd.to_datetime(candles.index, unit="s")
        indicators.index = pd.to_datetime(indicators.index, unit="s")
        trades.index = pd.to_datetime(trades.index, unit="s")

        indicators = pd.concat(
            [indicators, indicators.indicators.apply(pd.Series)], axis=1
        ).drop("indicators", axis=1)
        indicators.columns = [f"ind_{c}" for c in indicators.columns]

        report = res["performanceReport"]
        report["startPrice"] = candles["close"].iloc[0]

        jdf = (
            candles.join(indicators)
            .join(trades)
            .join(roundtrips.set_index("entryAt")[["entryBalance"]])
            .join(roundtrips.set_index("exitAt")[["exitBalance"]])
            .pipe(self._assemble_joint_df, report)
        )
        profits = self._profit_per_month(jdf)

        return report, jdf, profits

    def plot_stats(
        self, jdf, profit_per_month, figsize=(20, 25)
    ) -> matplotlib.figure.Figure:
        """ Create a figure from the output of :meth:`.backtest`.

        Parameters
        ----------
        jdf
            as returned by :meth:`.backtest`
        profit_per_month
            as returned by :meth:`.backtest`
        figsize
            matplotlib figsize for the whole plot

        Returns
        -------
        fig
            a matplotlib figure
        """
        fig, axes = plt.subplots(4, 1, figsize=figsize)
        axidx = 0
        alpha = 0.4

        # Market
        ax = axes[0]
        jdf[["close"]].plot(ax=ax)
        jdf[jdf.action == "buy"].plot(
            x="date",
            y="close",
            ls="",
            marker=matplotlib.markers.CARETUP,
            ax=ax,
            ms=10,
            color="green",
            label="buy",
        )
        jdf[jdf.action == "sell"].plot(
            x="date",
            y="close",
            ls="",
            marker=matplotlib.markers.CARETDOWN,
            ax=ax,
            ms=10,
            color="red",
            label="sell",
        )
        ax.set_yscale("log")
        ax.set_title("market")
        ax.grid()

        # Profits per month
        axidx += 1
        ax = axes[axidx]
        ax.set_title("Profit per month")
        profit_per_month[["marketProfit", "stratProfit"]].plot.bar(ax=ax)
        ax.legend(['market', 'strategy'])
        ax.set_xticklabels(
            ax.get_xticklabels(), rotation=45, horizontalalignment="right"
        )
        vals = ax.get_yticks()
        ax.set_yticklabels(['{:,.0%}'.format(x) for x in vals])
        ax.axhline(0, c="black", lw=1.5)
        ax.grid()

        # Strategy
        axidx += 1
        ax = axes[axidx]
        jdf[["marketP", "stratP"]].plot(ax=ax)
        jdf[jdf.action == "buy"].plot(
            x="date",
            y="stratP",
            ls="",
            marker=matplotlib.markers.CARETUP,
            ax=ax,
            ms=10,
            color="green",
            label="buy",
            alpha=alpha,
        )
        jdf[jdf.action == "sell"].plot(
            x="date",
            y="stratP",
            ls="",
            marker=matplotlib.markers.CARETDOWN,
            ax=ax,
            ms=10,
            color="red",
            label="sell",
            alpha=alpha,
        )
        ax.set_yscale("log")
        ax.set_title("relative profit")
        ax.legend(['market', 'strategy'])
        ax.grid()

        # Drawdown
        axidx += 1
        ax = axes[axidx]
        jdf[["marketDrawdown", "stratDrawdown"]].plot(ax=ax)
        vals = ax.get_yticks()
        ax.set_yticklabels(['{:,.0%}'.format(x) for x in vals])
        ax.set_title("drawdown")
        ax.legend(['market', 'strategy'])
        ax.grid()
        fig.tight_layout()

        return fig

    def pull_candles(
        self,
        exchange: str,
        asset: str,
        currency: str,
        candlesize: int,
        date_start: str = None,
        date_end: str = None,
    ) -> pd.DataFrame:
        """ Pull candles from Gekko for the given exchange, asset, currency and
        date range.

        Parameters
        ----------
        exchange
            name of the exchange as in return of :meth:`.pull_dataranges`
        asset
            name of the asset
        currency
            name of the currency
        candlesize
            candlesize in minutes
        date_start: anything that can be parsed by pd.to_datetime
            first date for which to retrieve data.
            If None, will be imputed via :meth:`.assemble_daterange`

        date_end: anything that can be parsed by pd.to_datetime
            last date for which to retrieve data.
            If None, will be imputed via :meth:`.assemble_daterange`

        Returns
        -------

        """
        req = {
            "watch": {"exchange": exchange, "asset": asset, "currency": currency},
            "daterange": self.assemble_daterange(
                date_start, date_end, exchange=exchange, asset=asset, currency=currency
            ),
            "candleSize": candlesize,
        }
        res = self.post("getCandles", req)
        candles = pd.DataFrame(res)
        return candles

    def assemble_daterange(
        self,
        date_start=None,
        date_end=None,
        exchange=None,
        asset=None,
        currency=None,
        dataranges=None,
    ) -> Dict[str, str]:
        """ Create daterange dictionary. If date_start or date_end is None, auto-impute
        to maximum range of the first entry in `dataranges` that matches `exchange`,
        `asset` and `currency`. If only one of them `date_start`, `date_end` is given,
        it must be in the first matching entry from `dataranges`.

        Parameters
        ----------
        date_start: anything that can be parsed by pd.to_datetime
            first date which is part of
        date_end: anything that can be parsed by pd.to_datetime
        exchange
            used to auto-impute date range
        asset
            used to auto-impute date range
        currency
            used to auto-impute date range
        dataranges
            dataranges as returned by :func:`.pull_dataranges`. If None, this function
            pulls them directly from Gekko

        Returns
        -------
        daterange: Dict[str, str]
            Dictionary with keys `from`, `to` with provided or imputed dates in
            isoformat as values.
        """
        if date_start is None or date_end is None:
            if dataranges is None:
                dataranges = self.pull_dataranges()
            dataranges = dataranges[
                (dataranges.exchange == exchange)
                & (dataranges.asset == asset)
                & (dataranges.currency == currency)
            ]
            if len(dataranges) == 0:
                raise ValueError(
                    f"no data ranges match specified exchange/asset/currency combination "
                    f"({asset}/{currency}@{exchange})"
                )
            if date_start is None:
                date_start = dataranges.iloc[0, :]["from"]
            if date_end is None:
                date_end = dataranges.iloc[0, :]["to"]
        if date_start is not None:
            date_start = pd.to_datetime(date_start)
        if date_end is not None:
            date_end = pd.to_datetime(date_end)

        return {"from": date_start.isoformat(), "to": date_end.isoformat()}

    @staticmethod
    def _profit_per_month(jdf):
        # Profits
        def first(df):
            return df.iloc[0, :]

        def last(df):
            return df.iloc[-1, :]

        groups = jdf[["currentBalance", "close"]].groupby(pd.Grouper(freq="M"))
        firsts = groups.apply(first)
        lasts = groups.apply(last)
        firsts.columns = [f"f{c}" for c in firsts.columns]
        lasts.columns = [f"l{c}" for c in lasts.columns]
        profits = pd.concat([firsts, lasts], axis=1)
        profits.index = [d.date() for d in profits.index]
        profits["marketProfit"] = (profits.lclose - profits.fclose) / profits.fclose
        profits["stratProfit"] = (
            profits.lcurrentBalance - profits.fcurrentBalance
        ) / profits.fcurrentBalance
        return profits

    @staticmethod
    def _assemble_joint_df(jdf, report, short_ratio: float = 0.0) -> pd.DataFrame:
        """ Assemble a pandas DataFrame from the output of :meth:`.backtest` with
        all information and some calculated statistics.

        Parameters
        ----------
        jdf
            jdf as returned by :meth:`.backtest`
        report
            report as returned by :meth:`.backtest`
        short_ratio
            Experimental feature.
            Specifies how much of your budget to keep in a short
            order. E.g., if 0.5, half of the budget is always in a short order,
            effectively opening a net short position when Gekko goes "short", and
            then again yielding only 50% profit when Gekko is "long" (because the
            short order persists).

            This is a way to work around Gekko's inability to create native short
            positions.

        Returns
        -------
        joint:
            DataFrame with a lot of nice info and stats :)

        """
        start_price = report["startPrice"]
        start_balance = report["startBalance"]
        jdf["lastAction"] = jdf.action.ffill()
        jdf["lastAmount"] = jdf.amount.ffill()
        jdf["lastBalance"] = jdf.balance.ffill()

        jdf["profit"] = (jdf.close / start_price).diff()
        jdf["profit"] = jdf.apply(
            lambda row: row.profit * (1 - short_ratio)
            if row.lastAction == "buy"
            else (-row.profit * short_ratio if row.lastAction == "sell" else 0),
            axis=1,
        )
        jdf["currentBalance"] = jdf.apply(
            lambda row: row["lastBalance"]
            if row["lastAction"] == "sell"
            else row["lastAmount"] * row["close"],
            axis=1,
        ).fillna(report["startBalance"])
        jdf["marketP"] = jdf.close / start_price
        jdf["stratP"] = jdf.currentBalance / start_balance
        jdf["marketMax"] = jdf.marketP.cummax()
        jdf["stratMax"] = jdf.stratP.cummax()
        jdf["marketDrawdown"] = -(1 - jdf.marketP / jdf.marketMax)
        jdf["stratDrawdown"] = -(1 - jdf.stratP / jdf.stratMax)
        jdf["date"] = jdf.index
        return jdf
