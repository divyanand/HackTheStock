from binance.client import Client
import matplotlib.pyplot as plt
import numpy
import datetime
import sys
import os
import logging
import threading
import talib

api_key = ''
api_secret = ''
# client = None
pool = None
logger = None
fee_percent = 0

symbol_vals = {}

plot_arrays = None

def get_klines (symbol):
    global logger

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
    global logger

    logger.info("Starting to get klines for {} symbols".format(len(tickers)))
    for sym in symbols_toInit:
        get_klines(sym)

def read_symbol_data(symbol):
    global symbol_vals
    global plot_arrays 
    plot_arrays = {
        "symbol"     : symbol,
        "init_qty"   : 0,
        "cur_price"  : [],
        "portfolio"  : [],
        "realized"   : [],
        "trail_up"   : [],
        "trail_down" : [],
        "base"       : [],
    }


    if symbol not in symbol_vals.keys():
        symbol_vals.update({symbol : []})

    if not os.path.isfile(symbol + ".txt"):
        return

    with open(symbol + ".txt", "r") as fin:
        for line in fin.readlines():
            if len(line.strip()) == 0 or "Open" in line:
                continue

            symbol_vals[symbol].append(float(line.split()[4]))

def store_plot_values(cur_price = 0, portfolio = 0, realized = 0, trail_up = 0, trail_down = 0):
    global plot_arrays
    plot_arrays["cur_price"].append(cur_price)
    plot_arrays["portfolio"].append(portfolio)
    plot_arrays["realized"].append(realized)
    plot_arrays["trail_up"].append(cur_price if trail_up == 0 else trail_up)
    plot_arrays["trail_down"].append(cur_price if trail_down == 0 else trail_down)
    if plot_arrays["init_qty"] == 0:
        plot_arrays["init_qty"] = portfolio / cur_price
    plot_arrays["base"].append(plot_arrays["init_qty"] * cur_price)

def plot_chart(plot_title):
    global plot_arrays
    logger.info("Plotting chart")
    fig, axs = plt.subplots(2, 1)
    axs[0].plot(range(len(plot_arrays["trail_up"])), plot_arrays["trail_up"], 
                range(len(plot_arrays["trail_down"])), plot_arrays["trail_down"],
                range(len(plot_arrays["cur_price"])), plot_arrays["cur_price"], linewidth = 1.0)

    # buy_x = []
    # buy_y = []
    # for x, y in buy_vals_list:
    #     buy_x.append(x)
    #     buy_y.append(y)
    # axs[0].scatter(buy_x, buy_y, c='g')

    # for i, y in enumerate(buy_y):
    #     axs[0].annotate(y, (buy_x[i], buy_y[i]), c='g')

    low = min(plot_arrays["cur_price"])
    high = max(plot_arrays["cur_price"])
    gap = high - low
    low += gap * 0.1
    high += gap * 0.1

    axs[0].set_title(plot_title)
    axs[0].grid(True)
    axs[0].legend(["Trail_up", "Trail_down", "Price"], loc="upper left")

    # major_ticks_top=numpy.linspace(low, high, 10)
    # minor_ticks_top=numpy.linspace(low, high, 20)
    # major_ticks_bottom=numpy.linspace(0,15,6)

    # axs[0].set_xticks(major_ticks_top)
    # axs[0].set_yticks(major_ticks_top)
    # axs[0].set_xticks(minor_ticks_top,minor=True)
    # axs[0].set_yticks(minor_ticks_top,minor=True)
    # axs[0].grid(which="major",alpha=0.6)
    # axs[0].grid(which="minor",alpha=0.3)
    t1 = range(len(plot_arrays["portfolio"]))
    t2 = range(len(plot_arrays["realized"]))
    # plot_arrays["portfolio"] = t1
    # plot_arrays["realized"] = [4, 5, 6]
    axs[1].plot(t1, plot_arrays["portfolio"], c='b', label = "Potential", linewidth = 1.0)
    axs[1].plot(t2, plot_arrays["realized"], c='r', label = "Realized PL", linewidth = 1.0)
    axs[1].plot(t2, plot_arrays["base"], c='k', linewidth = 1.0)
    # axs[1].set_xlim(0, plotlen)
    axs[1].legend(["Potential", "Realized", "base"], loc="upper left")
    axs[1].grid(True)
    fig.tight_layout()
    fig.set_figwidth(12)
    plt.figure
    plt_fname = "{}.png".format(plot_title)
    plt.savefig(plt_fname, dpi=300)
    plt.close()

def get_next_value(symbol):
    global symbol_vals
    if symbol in symbol_vals.keys():
        if len(symbol_vals[symbol]) > 0:
            val = symbol_vals[symbol].pop(0)
            return val
    return None

def trailing_buy(symbol, cur_price, down_percent, investment):
    global logger
    logger.info("{} : Starting to trail_down with {}% to invest {}".format(symbol, down_percent, investment))

    trail_gap = cur_price * down_percent / 100
    trail_val = cur_price + trail_gap
    portfolio_value = investment
    prices = []

    while cur_price is not None:
        prices.append(cur_price)
        # as long as trail_val value is greater than current value, the stock is sinking
        # once the cur_price raises to trail_val, buy
        if trail_val - cur_price > trail_gap:
            trail_val = cur_price + trail_gap

            # trail_downs_list.append(trail_val)
            # trail_ups_list.append(cur_price)
        if cur_price >= trail_val:
            # Upward movement is started. Buy
            qty = investment / cur_price
            fee = qty * fee_percent / 100
            qty -= fee
            fee_currency = symbol
            portfolio_value = cur_price * qty
            logger.info("{} : Bought {} at price {} after trailing with {}% for {}".format(symbol, qty, cur_price, down_percent, portfolio_value))
            logger.warning("BUY  : trail: {}, price: {}, qty: {}, total value: {}".format(trail_val, cur_price, qty, portfolio_value))
            return prices, qty, portfolio_value

        store_plot_values(cur_price = cur_price, 
                            portfolio = portfolio_value, 
                            realized = investment, 
                            trail_up = cur_price, 
                            trail_down = trail_val)
        cur_price = get_next_value(symbol)

    return [0],0,0

def trailing_sell(symbol, cur_price, up_percent, qty):
    global logger
    global plot_arrays
    logger.info("{} : Starting to trail_up with {}% to sell {} qty".format(symbol, up_percent, qty))

    trail_gap = cur_price * up_percent / 100
    trail_val = cur_price - trail_gap
    prices = []
    realized = plot_arrays["realized"][-1]

    while cur_price is not None:
        prices.append(cur_price)
        portfolio_value = cur_price * qty
        # as long as trail_val value is less than current value, the stock is raising.
        # once the cur_price falls to trail_val, Sell
        if cur_price - trail_val > trail_gap:
            trail_val = cur_price - trail_gap

        if cur_price <= trail_val:
            # Down ward movement started. Sell.
            portfolio_value = (qty * cur_price) 
            fee = portfolio_value * fee_percent / 100
            portfolio_value -= fee
            logger.info("{} : Sold {} at price {} after trailing with {}% for {}".format(symbol, qty, cur_price, up_percent, portfolio_value))
            logger.warning("SELL : trail: {}, price: {}, qty: {}, total value: {}".format(
                trail_val, cur_price, qty, portfolio_value))
            return prices, 0, portfolio_value

        store_plot_values(cur_price = cur_price, 
                            portfolio = portfolio_value, 
                            realized = realized, 
                            trail_up = trail_val, 
                            trail_down = cur_price)

        cur_price = get_next_value(symbol)
    return [0], 0, 0

def trailing_strategy(symbol, investment, up_percent = 5, down_percent = 5):
    global logger
    logger.info("{} : Following trailing_strategy with investment {}, {}% up trail and {}% down trail".format(
                                               symbol,      investment, up_percent, down_percent))
    holding_qty = 0
    cur_price = get_next_value(symbol)
    while investment > 0:
        prices, holding_qty, traded_value = trailing_buy(symbol, cur_price, down_percent, investment)
        cur_price = prices[-1]
        if cur_price == 0:
            break
        investment = traded_value
        prices, holding_qty, traded_value = trailing_sell(symbol, cur_price, up_percent, holding_qty)
        cur_price = prices[-1]
        if cur_price == 0:
            break
        investment = traded_value
    logger.critical("{} : Retained {} at the end of trailing strategy ".format(symbol, investment))
    return investment

def trailing_with_RSI(symbol, investment, up_percent = 5, down_percent = 5):
    global logger
    logger.info("{} : Following trailing_with_RSI with investment {}, {}% up trail and {}% down trail".format(
                                               symbol,      investment, up_percent, down_percent))
    holding_qty = 0
    cur_price = get_next_value(symbol)

    RSI_PERIOD = 14
    RSI_OVERBOUGHT = 70
    RSI_OVERSOLD = 30
    prices_list = []
    cash = portfolio = realized = investment
    while portfolio > 0 and cur_price is not None:
        prices_list.append(cur_price)

        if len(prices_list) > RSI_PERIOD:
            np_prices = numpy.array(prices_list)
            rsi = talib.RSI(np_prices, RSI_PERIOD)
            cur_rsi = rsi[-1]

            if (cur_rsi < RSI_OVERSOLD) and (cash > 0):
                logger.info("{} : price = {}, rsi = {}. start trailing down with {}% to buy".format(symbol, cur_price, cur_rsi, down_percent))
                prices, holding_qty, traded_value = trailing_buy(symbol, cur_price, down_percent, cash)
                cur_price = prices[-1]
                if cur_price == 0:
                    break
                cash = 0
                prices_list.extend(prices)
                prices_list = prices_list[:RSI_PERIOD]

            if (cur_rsi > RSI_OVERBOUGHT) and (holding_qty > 0):
                logger.info("{} : price = {}, rsi = {}. start trailing up with {}% to sell".format(symbol, cur_price, cur_rsi, up_percent))
                prices, holding_qty, realized = trailing_sell(symbol, cur_price, up_percent, holding_qty)
                cash = realized
                cur_price = prices[-1]
                if cur_price == 0:
                    break
                prices_list.extend(prices)
                prices_list = prices_list[:RSI_PERIOD]

            prices_list.pop(0)
        portfolio = (holding_qty * cur_price) + cash
        store_plot_values(cur_price = cur_price, 
                            portfolio = portfolio, 
                            realized = realized, 
                            trail_up = cur_price, 
                            trail_down = cur_price)


        cur_price = get_next_value(symbol)
    logger.critical("{} : Retained {} at the end of trailing_with_RSI strategy".format(symbol, portfolio))
    return portfolio
   
def trail(symbol, realized_value, up_percent = 5, down_percent = 5, create_plot = True):
    global logger
    prev_val = get_next_value(symbol)
    if prev_val is None:
        logger.error("Values not received for {}".format(symbol))
        return

    cur_price = get_next_value(symbol)
    if cur_price is None:
        logger.error("Values completed for {}".format(symbol))
        return

    potential_value = 0

    buy_price = 0
    buy_qty = 0
    sell_price = 0
    sell_qty = 0
    trail_gap = cur_price * down_percent / 100
    trail_val = cur_price + trail_gap

    trailing_down = True

    while cur_price is not None:
        
        potential_value = buy_qty * cur_price if buy_qty > 0 else realized_value

        # first trail down and buy
        if trailing_down:
            # as long as trail_down value is greater than current value, the stock is sinking
            # once the cur_price reaches (increases) trail_down, start to buy
            if trail_val - cur_price > trail_gap:
                trail_val = cur_price + trail_gap

            store_plot_values(cur_price   = cur_price, 
                                portfolio = potential_value, 
                                realized  = realized_value, 
                                trail_up  = trail_val, 
                                trail_down = cur_price)

            if cur_price >= trail_val:
                # Upward movement is started. Buy
                buy_price = cur_price
                buy_qty = realized_value / buy_price
                logger.warning("BUY  : trail: {}, price: {}, qty: {}, total value: {}".format(
                                   trail_val, buy_price, buy_qty, realized_value))
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

            store_plot_values(cur_price   = cur_price, 
                                portfolio = buy_qty*cur_price if cur_price <= trail_val else potential_value, 
                                realized  = buy_qty*cur_price if cur_price <= trail_val else realized_value, 
                                trail_up  = trail_val, 
                                trail_down = cur_price)

            if cur_price <= trail_val:
                # Down ward movement is started. Sell.
                sell_price = cur_price
                sell_qty = buy_qty
                buy_qty = buy_price = 0
                realized_value = sell_qty * sell_price
                potential_value = realized_value
                logger.warning("SELL : trail: {}, price: {}, qty: {}, total value: {}".format(
                    trail_val, sell_price, sell_qty, realized_value))

                trail_gap = cur_price * down_percent / 100
                trail_val = cur_price + trail_gap
                trailing_down = True

        cur_price = get_next_value(symbol)

    logger.error("Up = {}, down = {}, asset value at end = {}, +P/-L = {}".format(up_percent, down_percent, realized_value, realized_value - 100))
 
    logger.critical("{} : Retained {} at the end of trail-buy and trail-sell strategy".format(symbol, realized_value))
    return realized_value

if __name__=='__main__':
    plot_arrays = None
    logger =  logging.getLogger('datacollector')
    logger.setLevel(logging.INFO)
    ch = logging.StreamHandler()
    fh = logging.FileHandler("Trading_bot.log", mode="w", encoding=None, errors = None)
    # formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    formatter = logging.Formatter('%(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    fh.setFormatter(formatter)
    logger.addHandler(ch)
    logger.addHandler(fh)

    supported_symbols = get_supported_symbols()
    # interested_cryptos = ["USDT"] # for all USDT pairs
    interested_cryptos = ["BTCUSDT", "ETHUSDT"] # for individual pairs

    tickers = []
    for ticker in supported_symbols:
        for crypto in interested_cryptos:
            if crypto in ticker:
                tickers.append(ticker)
                continue

    intialize_db(tickers)
    updown_vals = [(1,1), (2,2), (5,5), (10,4)]
    updown_vals = [(5,5)]
    for symbol in tickers:
        # max_realized_with=()
        # max_realized = 0
        for up_percent, down_percent in updown_vals:
            read_symbol_data(symbol)
            realized = trailing_with_RSI(symbol, 100, up_percent=up_percent, down_percent=down_percent)
            plot_chart("{}_trailing_with_RSI_{}-Up_{}-Down".format(symbol, up_percent, down_percent))

            read_symbol_data(symbol)
            realized = trailing_strategy(symbol, 100, up_percent=up_percent, down_percent=down_percent)
            plot_chart("{}_trailing_strategy_{}-Up_{}-Down".format(symbol, up_percent, down_percent))
            # if realized > max_realized:
            #     max_realized = realized
            #     max_realized_with = (up, down)
