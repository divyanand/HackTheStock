from binance.client import Client
import matplotlib.pyplot as plt
import os
import logging
import numpy

CHARTS_LOCATION = "Charts"
KLINES_LOCATION = "Klines"

class DataCollector():
    def __init__(self):
        self.api_key = ''
        self.api_secret = ''
        self.tld = 'com'
        self.logger = logging.getLogger('datacollector')
        self.BClient = None
        self.plot_arrays = None
        self.supported_symbols = []
        self.symbol_vals ={}

        # try:
        #     self.BClient = Client(self.api_key, self.api_secret, tld = self.tld)
        # except Exception as e:
        #     self.logger.error("Unable to create Client.")
        #     self.logger.error(str(e))

    def get_klines (self, symbol):
        if self.BClient is None:
            self.logger.error("Binance Client is not inintialized. Failing to get klines for {}".format(symbol))
            return

        try:
            out  = "{:<13} ".format("Open-time")
            out += "{:>13} ".format("Open")
            out += "{:>13} ".format("High")
            out += "{:>13} ".format("Low")
            out += "{:>13} ".format("Close")
            out += "{:>13} ".format("Volume")
            out += "{:<13} ".format("Close-time")
            out += "{:>13} ".format("QuoteVolume")
            out += "{:>13} ".format("#Trades")
            out += "{:>13} ".format("#BasedVolume")
            out += "{:>13} ".format("#QuotedVolume")

            fname = os.path.join(KLINES_LOCATION, symbol + ".txt")
            fout = None
            start_str = "1 month ago UTC"
            if os.path.isfile(fname):
                fout = open(fname, "r")
                lines = fout.readlines()
                fout.close()

                if len(lines) < 2:
                    fout = open(fname, "w")
                else:
                    last_time = int(lines[-1].split()[0]) + 1
                    fout = open(fname, "a")
                    start_str = last_time
            else:
                fout = open(fname, "w")

            self.logger.info("Getting klines of {:<8} since {}".format(symbol, start_str))
            klines = self.BClient.get_historical_klines(symbol, self.BClient.KLINE_INTERVAL_1MINUTE, start_str = start_str)
            self.logger.info("Storing klines of {:<8} ".format(symbol))
            if fout.mode == "w":
                print(out, file = fout)

            for kline in klines:
                out = ""
                for val in kline:
                    try:
                        val = "{:>13} ".format(val.replace("\'", ""))
                        if "." in val:
                            val = float(val)
                            out += "{:13.06f} ".format(val)
                        else:
                            out += "{:>13} ".format(val)

                    except:
                        out += "{:>13} ".format(val)
                print(out, file=fout)
            fout.close()
            self.logger.info("Completed storing klines of {:<8} ".format(symbol))
        except Exception as e:
            self.logger.error("Exception while getting /storing klines of {:<8} ".format(symbol))
            self.logger.error(str(e))
        finally:
            try:
                fout.close()
            except:
                pass

    def get_local_klined_symbols(self):
        available_klines = []
        dirpath, dirnames, filenames = next(os.walk(KLINES_LOCATION))
        for filename in filenames:
            if ".txt" in filename:
                stat = os.stat(os.path.join(dirpath, filename))
                if stat.st_size > 1024:
                    available_klines.append(filename.split(".txt")[0])
        return available_klines

    def get_supported_symbols(self, fallback_to_local = False):
        self.supported_symbols = []
        if self.BClient is not None:
            self.logger.info("Getting supported symbols from Binance Client")
            symbols = self.BClient.get_symbol_ticker()
            for d in symbols:
                sym = d['symbol']
                self.supported_symbols.append(sym)

        if fallback_to_local:
            self.supported_symbols = self.get_local_klined_symbols()

        return self.supported_symbols

    def intialize_db(self, symbols_toInit):
        for ctr, sym in enumerate(symbols_toInit):
            self.logger.info("Reading klines for {} ({}/{})".format(sym, ctr, len(symbols_toInit)))
            self.get_klines(sym)

    def read_symbol_data(self, symbol):
        symbol_obj = Symbol(symbol)
        self.symbol_vals.update({symbol : symbol_obj})

        fin_name = os.path.join(KLINES_LOCATION, symbol + ".txt")
        if not os.path.isfile(fin_name):
            return

        with open(fin_name, "r") as fin:
            for line in fin.readlines():
                if len(line.strip()) == 0 or "Open" in line:
                    continue

                self.symbol_vals[symbol].cur_prices.append(float(line.split()[4]))

    def store_plot_values(self, symbol, 
                                cur_price = numpy.nan, 
                                portfolio = numpy.nan, 
                                realized = numpy.nan, 
                                trail_up = numpy.nan, 
                                trail_down = numpy.nan):
        plot_arrays = self.symbol_vals[symbol].plot_arrays
        plot_arrays["cur_price"].append(cur_price)
        plot_arrays["portfolio"].append(portfolio)
        plot_arrays["realized"].append(realized)
        plot_arrays["trail_up"].append(trail_up)
        plot_arrays["trail_down"].append(trail_down)
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

        max_chart_len = 7 * 24 * 60 #7days
        x_start = len(plot_arrays["trail_up"]) - max_chart_len
        x_end   = len(plot_arrays["trail_up"])
        if len(plot_arrays["trail_up"]) > max_chart_len:
            axs[0].set_xlim(x_start, x_end)

        plot_vals = []
        plot_vals.extend(plot_arrays["cur_price"][x_start:x_end])
        plot_vals.extend(plot_arrays["trail_up"][x_start:x_end])
        plot_vals.extend(plot_arrays["trail_down"][x_start:x_end])
        y_min = numpy.nanmin(plot_vals) * 0.9
        y_max = numpy.nanmax(plot_vals) * 1.1
        axs[0].set_ylim(y_min, y_max)
        axs[0].set_title(plot_title)
        axs[0].grid(True)
        axs[0].legend(["Trail_up", "Trail_down", "Price"], loc="upper left")

        t1 = range(len(plot_arrays["portfolio"]))
        t2 = range(len(plot_arrays["realized"]))
        axs[1].plot(t1, plot_arrays["portfolio"], c='b', label = "Potential", linewidth = 1.0)
        axs[1].plot(t2, plot_arrays["realized"], c='r', label = "Realized PL", linewidth = 1.0)
        axs[1].plot(t2, plot_arrays["base"], c='k', linewidth = 1.0)
        axs[1].legend(["Potential", "Realized", "base"], loc="upper left")
        if len(plot_arrays["trail_up"]) > max_chart_len:
            axs[1].set_xlim(x_start, x_end)
        plot_vals = []
        plot_vals.extend(plot_arrays["portfolio"][x_start:x_end])
        plot_vals.extend(plot_arrays["realized"][x_start:x_end])
        plot_vals.extend(plot_arrays["base"][x_start:x_end])
        y_min = numpy.nanmin(plot_vals) * 0.9
        y_max = numpy.nanmax(plot_vals) * 1.1

        axs[1].set_ylim(y_min, y_max)

        axs[1].grid(True)

        fig.tight_layout()
        fig.set_figwidth(12)
        plt.figure
        plt_fname = os.path.join(CHARTS_LOCATION, "{}.png".format(plot_title))
        plt.savefig(plt_fname, dpi=300)
        plt.close()

    def get_next_value(self, symbol):
        if symbol in self.symbol_vals.keys():
            if len(self.symbol_vals[symbol].cur_prices) > 0:
                val = self.symbol_vals[symbol].cur_prices.pop(0)
                return val
        return None

class Symbol():
    def __init__(self, name):
        self.name = name
        self.cur_prices = []
        self.plot_arrays = {
            "symbol"     : name,
            "init_qty"   : 0,
            "cur_price"  : [],
            "portfolio"  : [],
            "realized"   : [],
            "trail_up"   : [],
            "trail_down" : [],
            "base"       : [],
        }


