from binance.client import Client
import multiprocessing
import matplotlib.pyplot as plt
import numpy as np
import datetime
import sys
import os
import logging
import threading
import signal

api_key = ''
api_secret = ''
# client = None
pool = None
logger = None

symbol_vals = {}

def get_klines (symbol):
    global logger
    # logger =  logging.getLogger('datacollector')
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

        fname = symbol + ".txt"
        fout = None
        start_str = "1 month ago UTC"
        if os.path.isfile(fname):
            fout = open(fname, "r")
            lines = fout.readlines()
            fout.close()

            if len(lines) < 2:
                fout = open(fname, "w")
                print(out, file = fout)
            else:
                last_time = int(lines[-1].split()[0]) + 1
                fout = open(fname, "a")
                start_str = last_time
        else:
            fout = open(fname, "w")
            print(out, file = fout)

        logger.info("Getting klines of {:<8} since {}".format(symbol, start_str))
        try:
            client = Client(api_key, api_secret, tld="com")
        except Exception as e:
            logger.error("Exception while creating client. Exiting due to below exception")
            logger.error(str(e))
            fout.close()
            return

        klines = client.get_historical_klines(symbol, client.KLINE_INTERVAL_1MINUTE, start_str = start_str)
        logger.info("Storing klines of {:<8} ".format(symbol))
        for kline in klines:
            out = ""
            for val in kline:
                try:
                    out += "{:>13} ".format(val.replace("\'", ""))
                except:
                    out += "{:>13} ".format(val)
            # out  = "{:<13} ".format(kline[0])                      # 1614770580000,    Open-time
            # out += "{:>13} ".format(kline[1].replace("\'", ""))    # '0.03107400'      Open
            # out += "{:>13} ".format(kline[2].replace("\'", ""))    # '0.03108100'      High
            # out += "{:>13} ".format(kline[3].replace("\'", ""))    # '0.03106000'      Low
            # out += "{:>13} ".format(kline[4].replace("\'", ""))    # '0.03106100'      Close
            # out += "{:>13} ".format(kline[5].replace("\'", ""))    # '255.18400000'    Volume
            # out += "{:>13} ".format(kline[6])                      # 1614770639999,    Close-time
            # out += "{:>13} ".format(kline[7].replace("\'", ""))    # '7.92979073'      QuoteVolume
            # out += "{:<13} ".format(kline[8])                      # 234,              #Trades
            # out += "{:<13} ".format(kline[9].replace("\'", ""))    # '95.12700000'     #BasedVolume
            # out += "{:<13} ".format(kline[10].replace("\'", ""))   # '2.95616782'      #QuotedVolume
            print(out, file=fout)
        fout.close()
        logger.info("Completed storing klines of {:<8} ".format(symbol))
    except Exception as e:
        logger.error("Exception while getting /storing klines of {:<8} ".format(symbol))
        logger.error(str(e))

def get_supported_symbols():
    supported_symbols = []
    try:
        client = Client(api_key, api_secret, tld="com")
    except Exception as e:
        logger.error("Exception while creating client. Exiting due to below exception")
        logger.error(str(e))
        return supported_symbols

    logger.info("Getting supported symbols from Binance Client")
    symbols = client.get_symbol_ticker()

    for d in symbols:
        sym = d['symbol']
        supported_symbols.append(sym)
    return supported_symbols

def intialize_db(symbols_toInit):
    global pool
    global logger

    logger.info("Starting to get klines for {} symbols".format(len(tickers)))
    for sym in symbols_toInit:
        get_klines(sym)
    # pool = multiprocessing.Pool(processes = 3)
    # pool.map(get_klines, tickers)

def close_pool():
    global pool
    pool.close()
    pool.terminate()
    pool.join()

def term(*args,**kwargs):
    sys.stderr.write('\nStopping...')
    # httpd.shutdown()
    stoppool=threading.Thread(target=close_pool)
    stoppool.daemon=True
    stoppool.start()

def read_symbol_data(symbol):
    global symbol_vals
    if symbol not in symbol_vals.keys():
        symbol_vals.update({symbol : []})

    if not os.path.isfile(symbol + ".txt"):
        return

    with open(symbol + ".txt", "r") as fin:
        for line in fin.readlines():
            if len(line.strip()) == 0 or "Open" in line:
                continue

            symbol_vals[symbol].append(float(line.split()[4]))

def get_next_value(symbol):
    global symbol_vals
    if symbol in symbol_vals.keys():
        if len(symbol_vals[symbol]) > 0:
            val = symbol_vals[symbol].pop(0)
            return val
    return None

def trail(symbol, up_percent = 5, down_percent = 5, create_plot = True):
    global logger
    prev_val = get_next_value(symbol)
    if prev_val is None:
        logger.error("Values not received for {}".format(symbol))
        return

    cur_price = get_next_value(symbol)
    if cur_price is None:
        logger.error("Values completed for {}".format(symbol))
        return

    cur_prices_list = []
    net_vals = []
    potential_values_list = []
    realized_vals_list = []
    trail_ups_list = []
    trail_downs_list = []
    base_vals = [] # trend for 100$ invested at the beginning
    buy_vals_list = []
    sell_vals_list = []

    realized_value = 100
    potential_value = 0

    buy_price = 0
    buy_qty = 0
    sell_price = 0
    sell_qty = 0
    trail_gap = cur_price * down_percent / 100
    trail_val = cur_price + trail_gap

    initial_base_qty = realized_value / cur_price

    trailing_down = True

    while cur_price is not None:
        
        potential_value = buy_qty * cur_price if buy_qty > 0 else realized_value

        # first trail down and buy
        if trailing_down:
            # as long as trail_down value is greater than current value, the stock is sinking
            # once the cur_price reaches (increases) trail_down, start to buy
            if trail_val - cur_price > trail_gap:
                trail_val = cur_price + trail_gap

            trail_downs_list.append(trail_val)
            trail_ups_list.append(cur_price)
            if cur_price >= trail_val:
                # Upward movement is started. Buy
                buy_price = cur_price
                buy_qty = realized_value / buy_price
                logger.info("BUY  : trail: {}, price: {}, qty: {}, total value: {}".format(
                                   trail_val, buy_price, buy_qty, realized_value))
                if create_plot:
                    buy_vals_list.append((len(cur_prices_list), buy_price))
                sell_price = sell_qty = 0
                # trade_buy(symbol, buy_qty, buy_price)
                trail_gap = cur_price * up_percent / 100
                trail_val = cur_price - trail_gap
                trailing_down = False
        else:
            # as long as trail_up value is greater than current value, the stock is sinking
            # once the cur_price reaches (increases) trail_down, start to buy
            if cur_price - trail_val > trail_gap:
                trail_val = cur_price - trail_gap

            trail_downs_list.append(cur_price)
            trail_ups_list.append(trail_val)
            if cur_price <= trail_val:
                # Down ward movement is started. Sell.
                sell_price = cur_price
                sell_qty = buy_qty
                buy_qty = buy_price = 0
                if create_plot:
                    sell_vals_list.append((len(cur_prices_list), sell_price))
                realized_value = sell_qty * sell_price
                potential_value = realized_value
                logger.warning("SELL : trail: {}, price: {}, qty: {}, total value: {}".format(
                    trail_val, sell_price, sell_qty, realized_value))
                # trade_sell(symbol, sell_qty, sell_price)
                trail_gap = cur_price * down_percent / 100
                trail_val = cur_price + trail_gap
                trailing_down = True
                # txn += 1
                # if txn > 10:
                #     break
        prev_val = cur_price
        if create_plot:
            cur_prices_list.append(cur_price)
            net_vals.append(realized_value + potential_value)
            potential_values_list.append(potential_value)
            # trail_vals.append(trail_val)
            realized_vals_list.append(realized_value)
            base_vals.append(cur_price * initial_base_qty)
        # print(cur_price, trail_val, potential_value, realized_value)
        cur_price = get_next_value(symbol)

    logger.error("Up = {}, down = {}, asset value at end = {}, +P/-L = {}".format(up_percent, down_percent, realized_value, realized_value - 100))
    if create_plot:
        logger.info("Creating charts")
        fig, axs = plt.subplots(2, 1)
        axs[0].plot(range(len(trail_ups_list)), trail_ups_list, 
                    range(len(trail_downs_list)), trail_downs_list,
                    range(len(cur_prices_list)), cur_prices_list, linewidth = 1.0)

        # buy_x = []
        # buy_y = []
        # for x, y in buy_vals_list:
        #     buy_x.append(x)
        #     buy_y.append(y)
        # axs[0].scatter(buy_x, buy_y, c='g')

        # for i, y in enumerate(buy_y):
        #     axs[0].annotate(y, (buy_x[i], buy_y[i]), c='g')

        low = min(cur_prices_list)
        high = max(cur_prices_list)
        gap = high - low
        low += gap * 0.1
        high += gap * 0.1

        axs[0].set_title("{} {}% Up and {}% Down".format(symbol, up_percent, down_percent))
        axs[0].grid(True)
        axs[0].legend(["Trail_up", "Trail_down", "Price"], loc="upper left")

        # major_ticks_top=np.linspace(low, high, 10)
        # minor_ticks_top=np.linspace(low, high, 20)
        # major_ticks_bottom=np.linspace(0,15,6)

        # axs[0].set_xticks(major_ticks_top)
        # axs[0].set_yticks(major_ticks_top)
        # axs[0].set_xticks(minor_ticks_top,minor=True)
        # axs[0].set_yticks(minor_ticks_top,minor=True)
        # axs[0].grid(which="major",alpha=0.6)
        # axs[0].grid(which="minor",alpha=0.3)
        t1 = range(len(potential_values_list))
        t2 = range(len(realized_vals_list))
        # potential_values_list = t1
        # realized_vals_list = [4, 5, 6]
        axs[1].plot(t1, potential_values_list, c='b', label = "Potential", linewidth = 1.0)
        axs[1].plot(t2, realized_vals_list, c='r', label = "realized PL", linewidth = 1.0)
        axs[1].plot(t2, base_vals, c='k', linewidth = 1.0)
        # axs[1].set_xlim(0, plotlen)
        axs[1].legend(["Potential", "realized", "base"], loc="upper left")
        axs[1].grid(True)
        fig.tight_layout()
        fig.set_figwidth(12)
        plt.figure
        plt_fname = "{}_{}-up_{}-down.png".format(symbol, up_percent, down_percent)
        plt.savefig(plt_fname, dpi=300)
        plt.close()
 
    return realized_value

signal.signal(signal.SIGTERM, term)
signal.signal(signal.SIGINT,  term)

if __name__=='__main__':
    logger =  logging.getLogger('datacollector')
    logger.setLevel(logging.INFO)
    ch = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    # multiprocessing.set_start_method('spawn')

    supported_symbols = get_supported_symbols()
    # interested_cryptos = ["USDT"] # for all USDT pairs
    interested_cryptos = ["WINUSDT", "UFTETH"] # for individual pairs

    tickers = []
    for ticker in supported_symbols:
        for crypto in interested_cryptos:
            if crypto in ticker:
                tickers.append(ticker)
                continue

    intialize_db(tickers)
    updown_vals = [(1,1), (2,2), (5,5), (10,4)]
    for sym in tickers:
        # max_realized_with=()
        # max_realized = 0
        for up, down in updown_vals:
            read_symbol_data(sym)
            realized = trail(sym, up_percent=up, down_percent=down)
            # if realized > max_realized:
            #     max_realized = realized
            #     max_realized_with = (up, down)
