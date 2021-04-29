from binance.client import Client
import matplotlib.pyplot as plt
import os
import logging
import numpy as np
import pandas as pd
import time
import datetime
import talib

CHARTS_LOCATION = "Charts"
KLINES_LOCATION = "Klines"

class DataCollector():
    def __init__(self, local = False):
        self.api_key = ''
        self.api_secret = ''
        self.tld = 'com'
        self.logger = logging.getLogger('datacollector')
        self.BClient = None
        self.plot_arrays = None
        self.supported_symbols = []
        self.symbol_vals = {}
        self.symbol_klines = {}
        self.local = local

        if not self.local:
            try:
                self.BClient = Client(self.api_key, self.api_secret, tld = self.tld)
            except Exception as e:
                self.logger.error("Unable to create Client.")
                self.logger.error(str(e))
        else:
            self.logger.warn("Restricting to local klines.")

    def get_klines (self, symbol):
        keys = ["Open-time",
                  "Open",
                  "High",
                  "Low",
                  "Close",
                  "Volume",
                  "Closetime",
                  "QuoteVolume",
                  "Trades",
                  "BasedVolume",
                  "QuotedVolume",
                  "RSI"]

        open_time = 0
        Open      = 1
        High = 2
        Low = 3
        Close = 4
        Volume = 5
        Closetime = 6
        QuoteVolume = 7
        Trades = 8
        BasedVolume = 9
        QuotedVolume = 10
        unused = 11

        start_str = "1 month ago UTC"
        klines_df = None
        if not os.path.exists(KLINES_LOCATION):
            os.mkdir(KLINES_LOCATION)
        filename = os.path.join(KLINES_LOCATION, symbol + ".csv")
        reget_TA = False

        if os.path.isfile(filename):
            klines_df = pd.read_csv(filename, delimiter = ',', index_col=0)
            start_str = klines_df.iloc[-1][keys[open_time]]
            try:
                klines_df[keys[open_time]] = pd.to_datetime(klines_df[keys[open_time]],unit='ms')
                klines_df[keys[Closetime]] = pd.to_datetime(klines_df[keys[Closetime]],unit='ms')
            except ValueError:
                pass

        if not self.local:
            if self.BClient is None:
                self.logger.error("Binance Client is not inintialized. Failing to get klines for {}".format(symbol))
            else:
                klines = []
                try:
                    klines = self.BClient.get_historical_klines(symbol, self.BClient.KLINE_INTERVAL_1MINUTE, start_str = start_str)
                except Exception as e:
                    self.logger.error("Exception while downloading klines of {:<8} ".format(symbol))
                    self.logger.error(str(e))

                if len(klines) > 0:
                    klines_np = np.array(klines)
                    klines_tp = klines_np.transpose()
                    d = {}
                    for iter, row in enumerate(klines_tp):
                        if iter not in [open_time, Closetime, Trades]:
                            d.update({keys[iter] : row.astype(float)})
                        else:
                            d.update({keys[iter] : row})
                    d[keys[open_time]] = pd.to_datetime(d[keys[open_time]],unit='ms')
                    d[keys[Closetime]] = pd.to_datetime(d[keys[Closetime]],unit='ms')
                    klines_df_new = pd.DataFrame(d)
                    reget_TA = True

                    if klines_df is None:
                        klines_df = klines_df_new
                    else:
                        klines_df = klines_df.append(klines_df_new, ignore_index = True)

                if reget_TA:
                    ADX_TIMEPERIOD = RSI_TIMEPERIOD = MFI_TIMEPERIOD = AROON_TIMEPERIOD = 14
                    klines_df["ADX"] = talib.ADX(klines_df[keys[High]], klines_df[keys[Low]], klines_df[keys[Close]], timeperiod = ADX_TIMEPERIOD)
                    klines_df["RSI"] = talib.RSI(klines_df[keys[Close]], RSI_TIMEPERIOD)
                    klines_df["MFI"] = talib.MFI(klines_df[keys[High]], klines_df[keys[Low]], klines_df[keys[Close]], klines_df[keys[Volume]], timeperiod=MFI_TIMEPERIOD)
                    aroon_down, aroon_up = talib.AROON(klines_df[keys[High]], klines_df[keys[Low]], timeperiod=AROON_TIMEPERIOD)
                    klines_df["Aroon_up"]   = aroon_up
                    klines_df["Aroon_down"] = aroon_down
                    klines_df.to_csv(filename)

                self.logger.info("Completed getting klines of {:<8} ".format(symbol))

        self.symbol_klines.update({symbol : klines_df})

    def get_local_klined_symbols(self):
        available_klines = []
        dirpath, dirnames, filenames = next(os.walk(KLINES_LOCATION))
        for filename in filenames:
            if ".csv" in filename:
                stat = os.stat(os.path.join(dirpath, filename))
                if stat.st_size > 1024:
                    available_klines.append(filename.split(".csv")[0])
        return available_klines

    def get_supported_symbols(self, fallback_to_local = False):
        self.supported_symbols = []
        if self.BClient is not None:
            self.logger.info("Getting supported symbols from Binance Client")
            symbols = self.BClient.get_symbol_ticker()
            for d in symbols:
                sym = d['symbol']
                self.supported_symbols.append(sym)

        elif fallback_to_local and os.path.exists(KLINES_LOCATION):
            self.supported_symbols = self.get_local_klined_symbols()

        return self.supported_symbols

    def intialize_db(self, symbols_toInit):
        for ctr, sym in enumerate(symbols_toInit):
            self.logger.info("Reading klines for {} ({}/{})".format(sym, ctr, len(symbols_toInit)))
            self.get_klines(sym)

    def read_symbol_data(self, symbol):
        symbol_obj = Symbol(symbol)
        self.symbol_vals.update({symbol : symbol_obj})

        self.symbol_vals[symbol].future = self.symbol_klines[symbol].copy()
        self.symbol_vals[symbol].iterator = self.candle_iterator(symbol)
        self.symbol_vals[symbol].current = self.symbol_vals[symbol].future.iloc[0]
        # self.symbol_vals[symbol].history = None

    def store_plot_values(self, symbol,
                                cur_price = np.nan,
                                portfolio = np.nan,
                                realized = np.nan,
                                trail_up = np.nan,
                                trail_down = np.nan,
                                TA = np.nan):
        plot_arrays = self.symbol_vals[symbol].plot_arrays
        plot_arrays["cur_price"].append(cur_price)
        plot_arrays["portfolio"].append(portfolio)
        plot_arrays["realized"].append(realized)
        plot_arrays["trail_up"].append(trail_up)
        plot_arrays["trail_down"].append(trail_down)
        plot_arrays["TA"].append(TA)
        if plot_arrays["init_qty"] == 0:
            plot_arrays["init_qty"] = portfolio / cur_price
        plot_arrays["base"].append(plot_arrays["init_qty"] * cur_price)

    def plot_chart(self, plot_title, symbol):
        plot_arrays = self.symbol_vals[symbol].plot_arrays
        self.logger.info("Plotting chart")
        fig, axs = plt.subplots(2, 1)
        axs[0].plot(range(len(plot_arrays["trail_up"])), plot_arrays["trail_up"],
                    range(len(plot_arrays["trail_down"])), plot_arrays["trail_down"],
                    range(len(plot_arrays["cur_price"])), plot_arrays["cur_price"], linewidth = 1.0)

        max_days_to_chart = 30
        max_chart_len = max_days_to_chart * 24 * 60 #7days
        x_start = len(plot_arrays["trail_up"]) - max_chart_len
        x_end   = len(plot_arrays["trail_up"])
        if len(plot_arrays["trail_up"]) > max_chart_len:
            axs[0].set_xlim(x_start, x_end)

        plot_vals = []
        plot_vals.extend(plot_arrays["cur_price"][x_start:x_end])
        plot_vals.extend(plot_arrays["trail_up"][x_start:x_end])
        plot_vals.extend(plot_arrays["trail_down"][x_start:x_end])
        y_min = np.nanmin(plot_vals) * 0.9
        y_max = np.nanmax(plot_vals) * 1.1
        axs[0].set_ylim(y_min, y_max)
        axs[0].set_title(plot_title)
        axs[0].grid(True)
        axs[0].legend(["Trail_up", "Trail_down", "Price"], loc="upper left")

        t1 = range(len(plot_arrays["portfolio"]))
        t2 = range(len(plot_arrays["realized"]))

        second_axs = axs[1].twinx()
        # second_axs.plot(t2, plot_arrays["TA"], c = 'g', linewidth = 5, zorder = 10)
        # axs[1].plot(t1, plot_arrays["portfolio"], c='b', label = "Potential", linewidth = 1.0, zorder = 1)
        # axs[1].plot(t2, plot_arrays["realized"], c='r', label = "Realized PL", linewidth = 1.0, zorder = 9)
        # axs[1].plot(t2, plot_arrays["base"], c='k', linewidth = 1.0)

        axs[1].plot(t2, plot_arrays["TA"], c = 'g', label = "TA", linewidth = 1.0, zorder = 10)
        second_axs.plot(t1, plot_arrays["portfolio"], c='b', label = "Potential", linewidth = 1.0, zorder = 1)
        second_axs.plot(t2, plot_arrays["realized"], c='r', label = "Realized PL", linewidth = 1.0, zorder = 9)
        second_axs.plot(t2, plot_arrays["base"], c='k', linewidth = 1.0)

        second_axs.legend(["Potential", "Realized", "base", "TA"], loc="upper left")
        if len(plot_arrays["trail_up"]) > max_chart_len:
            second_axs.set_xlim(x_start, x_end)
        plot_vals = []
        plot_vals.extend(plot_arrays["portfolio"][x_start:x_end])
        plot_vals.extend(plot_arrays["realized"][x_start:x_end])
        plot_vals.extend(plot_arrays["base"][x_start:x_end])
        y_min = np.nanmin(plot_vals) * 0.9
        y_max = np.nanmax(plot_vals) * 1.1

        second_axs.set_ylim(y_min, y_max)

        second_axs.grid(True)

        fig.tight_layout()
        fig.set_figwidth(12)
        plt.figure
        plt_fname = os.path.join(CHARTS_LOCATION, "{}.png".format(plot_title))
        if not os.path.exists(CHARTS_LOCATION):
            os.mkdir(CHARTS_LOCATION)
        plt.savefig(plt_fname, dpi=300)
        plt.close()

    def candle_iterator(self, symbol):
        for index, row in self.symbol_vals[symbol].future.iterrows():
            self.symbol_vals[symbol].candles_processed = index + 1
            self.symbol_vals[symbol].current = row
            if (self.symbol_vals[symbol].candles_processed % (60*24) == 0):
                print("{} : {} - Processing candle of {} now.".format(datetime.datetime.now(), symbol, self.symbol_vals[symbol].current["Open-time"]))
            yield row

    def get_next_candle(self, symbol):
        candle = None
        if symbol in self.symbol_vals.keys():
            symbol_obj = self.symbol_vals[symbol]
            iterator = symbol_obj.iterator
            try:
                candle = next(iterator)
            except StopIteration:
                print("{} : {} - Processed all candles.".format(datetime.datetime.now(), symbol))
            symbol_obj.current = candle

        return candle

    def get_next_value(self, symbol):
        candle = self.get_next_candle(symbol)
        if candle is not None:
            val = candle["Close"]
            return val
        return None

class Symbol():
    def __init__(self, name):
        self.name = name
        self.future = None
        self.current = None
        self.iterator = None
        self.candles_processed = 0
        self.plot_arrays = {
            "symbol"     : name,
            "init_qty"   : 0,
            "cur_price"  : [],
            "portfolio"  : [],
            "realized"   : [],
            "trail_up"   : [],
            "trail_down" : [],
            "base"       : [],
            "TA"       : [],
        }
