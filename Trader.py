import DataCollector
import logging
import numpy
import time

class Trader():
    def __init__(self, datacollector):
        logger =  logging.getLogger('datacollector')
        # logger.setLevel(logging.INFO)
        logger.setLevel(logging.ERROR)
        ch = logging.StreamHandler()
        fh = logging.FileHandler("Trading_bot.log", mode="w", encoding=None) #, errors = None)
        # formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        formatter = logging.Formatter('%(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        fh.setFormatter(formatter)
        logger.addHandler(ch)
        logger.addHandler(fh)
        self.logger = logger
        self.datacollector = datacollector
        self.fee_percent = 0

    def trailing_buy(self, symbol, cur_price, down_percent, investment):
        self.logger.info("{} : Starting to trail_down with {}% to invest {}".format(symbol, down_percent, investment))

        trail_gap = cur_price * down_percent / 100
        trail_val = cur_price + trail_gap
        portfolio_value = investment
        prices = []

        while cur_price is not None:
            prices.append(cur_price)
            self.datacollector.store_plot_values(symbol, cur_price = cur_price,
                                portfolio = portfolio_value,
                                realized = investment,
                                trail_down = trail_val)
            # as long as trail_val value is greater than current value, the stock is sinking
            # once the cur_price raises to trail_val, buy
            if trail_val - cur_price > trail_gap:
                trail_val = cur_price + trail_gap

                # trail_downs_list.append(trail_val)
                # trail_ups_list.append(cur_price)
            if cur_price >= trail_val:
                # Upward movement is started. Buy
                qty = investment / cur_price
                fee = qty * self.fee_percent / 100
                qty -= fee
                fee_currency = symbol
                portfolio_value = cur_price * qty
                self.logger.info("{} : Bought {} at price {} after trailing with {}% for {}".format(symbol, qty, cur_price, down_percent, portfolio_value))
                self.logger.warning("BUY  : trail: {}, price: {}, qty: {}, total value: {}".format(trail_val, cur_price, qty, portfolio_value))
                return prices, qty, portfolio_value

            cur_price = self.datacollector.get_next_value(symbol)

        return [0],0,0

    def trailing_sell(self, symbol, cur_price, up_percent, qty):
        self.logger.info("{} : Starting to trail_up with {}% to sell {} qty".format(symbol, up_percent, qty))

        trail_gap = cur_price * up_percent / 100
        trail_val = cur_price - trail_gap
        prices = []
        realized = 0
        if len (self.datacollector.symbol_vals[symbol].plot_arrays["realized"]) > 1:
            realized = self.datacollector.symbol_vals[symbol].plot_arrays["realized"][-1]

        while cur_price is not None:
            prices.append(cur_price)
            portfolio_value = cur_price * qty
            self.datacollector.store_plot_values(symbol, cur_price = cur_price,
                                portfolio = portfolio_value,
                                realized = realized,
                                trail_up = trail_val)

            # as long as trail_val value is less than current value, the stock is raising.
            # once the cur_price falls to trail_val, Sell
            if cur_price - trail_val > trail_gap:
                trail_val = cur_price - trail_gap

            if cur_price <= trail_val:
                # Down ward movement started. Sell.
                portfolio_value = (qty * cur_price)
                fee = portfolio_value * self.fee_percent / 100
                portfolio_value -= fee
                self.logger.info("{} : Sold {} at price {} after trailing with {}% for {}".format(symbol, qty, cur_price, up_percent, portfolio_value))
                self.logger.warning("SELL : trail: {}, price: {}, qty: {}, total value: {}".format(
                    trail_val, cur_price, qty, portfolio_value))
                return prices, 0, portfolio_value

            cur_price = self.datacollector.get_next_value(symbol)

        return [0], 0, 0

    def trailing_strategy(self, symbol, investment, up_percent = 5, down_percent = 5):
        Strategy_name = "Trailing"
        self.logger.info("{} : Following trailing_strategy with investment {}, {}% up trail and {}% down trail".format(
                                                symbol,      investment, up_percent, down_percent))
        holding_qty = 0
        cur_price = self.datacollector.get_next_value(symbol)
        while investment > 0 and cur_price is not None:
            prices, holding_qty, traded_value = self.trailing_buy(symbol, cur_price, down_percent, investment)
            cur_price = prices[-1]
            if cur_price == 0 or cur_price is None:
                break
            investment = traded_value
            cur_price = self.datacollector.get_next_value(symbol)

            if cur_price == 0 or cur_price is None:
                break
            prices, holding_qty, traded_value = self.trailing_sell(symbol, cur_price, up_percent, holding_qty)
            cur_price = prices[-1]
            if cur_price == 0 or cur_price is None:
                break
            investment = traded_value
            cur_price = self.datacollector.get_next_value(symbol)

        plot_arrays = self.datacollector.symbol_vals[symbol].plot_arrays
        base = plot_arrays["base"][-1] if len (plot_arrays["base"]) > 0 else 0
        self.logger.critical("{:<20} : {:<12} strategy: Up% = {}, Down% = {}. Retained {:6.2f} (base {:6.2f}) ".format(
                    Strategy_name, symbol, up_percent, down_percent, investment, base))
        return investment, base

    def trailing_with_RSI(self, symbol, investment, up_percent = 5, down_percent = 5):
        Strategy_name = "Trailing_RSI"
        self.logger.info("{} : Following {} with investment {}, {}% up trail and {}% down trail".format(
                                                symbol, __name__,     investment, up_percent, down_percent))
        holding_qty = 0
        candle = self.datacollector.get_next_candle(symbol)

        RSI_OVERBOUGHT = 70
        RSI_OVERSOLD = 30
        max_portfolio_value = 0
        cash = portfolio = realized = investment
        while portfolio > 0 and candle is not None:
            cur_price = candle["Close"]
            cur_rsi   = candle["RSI"]

            if cur_rsi!= numpy.nan:
                if (cur_rsi < RSI_OVERSOLD) and (cash > 0):
                    self.logger.info("{} : price = {}, rsi = {}. start trailing down with {}% to buy".format(symbol, cur_price, cur_rsi, down_percent))
                    prices, holding_qty, traded_value = self.trailing_buy(symbol, cur_price, down_percent, cash)
                    cur_price = prices[-1]
                    if cur_price == 0:
                        break
                    cash = 0

                if (cur_rsi > RSI_OVERBOUGHT) and (holding_qty > 0):
                    self.logger.info("{} : price = {}, rsi = {}. start trailing up with {}% to sell".format(symbol, cur_price, cur_rsi, up_percent))
                    prices, holding_qty, realized = self.trailing_sell(symbol, cur_price, up_percent, holding_qty)
                    cash = realized
                    if cash > max_portfolio_value:
                        max_portfolio_value = cash
                    cur_price = prices[-1]
                    if cur_price == 0:
                        break

            if cur_price is None:
                break
            portfolio = (holding_qty * cur_price) + cash
            if portfolio > max_portfolio_value:
                max_portfolio_value = portfolio
            self.datacollector.store_plot_values(symbol, cur_price = cur_price,
                                portfolio = portfolio,
                                realized = realized, TA = cur_rsi)

            candle = self.datacollector.get_next_candle(symbol)

        plot_arrays = self.datacollector.symbol_vals[symbol].plot_arrays
        base = plot_arrays["base"][-1] if len (plot_arrays["base"]) > 0 else 0
        self.logger.critical("{:<20} : {:<12} strategy: Up% = {}, Down% = {}. Retained {:6.2f} (base {:6.2f}) max = {}".format(
                    Strategy_name, symbol, up_percent, down_percent, portfolio, base, max_portfolio_value))
        return portfolio, base

    def trailing_with_MFI(self, symbol, investment, up_percent = 5, down_percent = 5):
        Strategy_name = "trailing_with_MFI"
        self.logger.info("{} : Following {} with investment {}, {}% up trail and {}% down trail".format(
                                                symbol, __name__,     investment, up_percent, down_percent))
        holding_qty = 0
        candle = self.datacollector.get_next_candle(symbol)

        MFI_PERIOD = 14
        MFI_OVERBOUGHT = 70
        MFI_OVERSOLD = 25
        max_portfolio_value = 0
        cash = portfolio = realized = investment

        while portfolio > 0 and candle is not None:
            cur_price = candle["Close"]
            cur_mfi = candle["MFI"]

            if cur_mfi != numpy.nan:
                if (cur_mfi < MFI_OVERSOLD) and (cash > 0):
                    self.logger.info("{} : price = {}, mfi = {}. start trailing down with {}% to buy".format(symbol, cur_price, cur_mfi, down_percent))
                    prices, holding_qty, traded_value = self.trailing_buy(symbol, cur_price, down_percent, cash)
                    cur_price = prices[-1]
                    if cur_price == 0:
                        break
                    cash = 0

                if (cur_mfi > MFI_OVERBOUGHT) and (holding_qty > 0):
                    self.logger.info("{} : price = {}, mfi = {}. start trailing up with {}% to sell".format(symbol, cur_price, cur_mfi, up_percent))
                    prices, holding_qty, realized = self.trailing_sell(symbol, cur_price, up_percent, holding_qty)
                    cash = realized
                    if cash > max_portfolio_value:
                        max_portfolio_value = cash
                    cur_price = prices[-1]
                    if cur_price == 0:
                        break

            portfolio = (holding_qty * cur_price) + cash
            if portfolio > max_portfolio_value:
                max_portfolio_value = portfolio
            self.datacollector.store_plot_values(symbol, cur_price = cur_price,
                                portfolio = portfolio,
                                realized = realized,
                                TA = cur_mfi)

            candle = self.datacollector.get_next_candle(symbol)

        plot_arrays = self.datacollector.symbol_vals[symbol].plot_arrays
        base = plot_arrays["base"][-1] if len (plot_arrays["base"]) > 0 else 0
        self.logger.critical("{:<20} : {:<12} strategy: Up% = {}, Down% = {}. Retained {:6.2f} (base {:6.2f}) max = {}".format(
                    Strategy_name, symbol, up_percent, down_percent, portfolio, base, max_portfolio_value))
        return portfolio, base

    def test(self, symbol):
        # self.datacollector.read_symbol_data(symbol)
        # cur_price = self.datacollector.get_next_value(symbol)
        # start = time.time()
        # num_entries = 0
        # while cur_price is not None:
        #     num_entries += 1
        #     cur_price = self.datacollector.get_next_value(symbol)
        # print("iterated through {} entries in {} seconds".format(num_entries, time.time() - start))
        self.datacollector.read_symbol_data(symbol)
        cur_price = self.datacollector.get_next_value_V2(symbol)
        start = time.time()
        num_entries = 0
        while cur_price is not None:
            num_entries += 1
            cur_price = self.datacollector.get_next_value_V2(symbol)
        print("iterated through {} entries in {} seconds".format(num_entries, time.time() - start))

if __name__=='__main__':
    plot_charts = True
    test_trailing_with_MFI = test_trailing_with_RSI = test_trailing_strategy = False
    test_trailing_with_MFI = True
    test_trailing_with_RSI = True
    # test_trailing_strategy = True

    dc = DataCollector.DataCollector(local = False)
    supported_symbols = dc.get_supported_symbols(fallback_to_local = True)
    interested_cryptos = ["USDT"] # for all USDT pairs
    interested_cryptos = ["BTCUSDT", "ETHUSDT"] # for individual pairs
    interested_cryptos = ["WINUSDT", "XRPUSDT", "DOGEUSDT", "HOTUSDT"]
    interested_cryptos = ["WINUSDT"]

    tickers = []
    if len(supported_symbols) > 0:
        if len(interested_cryptos) == 0:
            tickers = supported_symbols
        else:
            for ticker in supported_symbols:
                for crypto in interested_cryptos:
                    if crypto in ticker:
                        tickers.append(ticker)
                        continue

    dc.intialize_db(tickers)

    updown_vals = []
    # updown_vals.append((1, 1))
    # updown_vals.appned((2, 2))
    # updown_vals.append((5, 5))
    # updown_vals.append((10,4))
    # updown_vals.append((0, 0))
    updown_vals.append((2, 5))
    trader = Trader(dc)
    # trader.test(tickers[0])

    if test_trailing_with_MFI:
        for symbol in tickers:
            for up_percent, down_percent in updown_vals:
                # cProfile.run("dc.read_symbol_data(symbol)")
                dc.read_symbol_data(symbol)
                trader.trailing_with_MFI(symbol, 100, up_percent=up_percent, down_percent=down_percent)
                if plot_charts:
                    name = "{}_trailing_with_MFI_{}-Up_{}-Down".format(symbol, up_percent, down_percent)
                    print("Plotting chart ", name)
                    dc.plot_chart(name, symbol)

    if test_trailing_with_RSI:
        for symbol in tickers:
            for up_percent, down_percent in updown_vals:
                dc.read_symbol_data(symbol)
                realized = trader.trailing_with_RSI(symbol, 100, up_percent=up_percent, down_percent=down_percent)
                if plot_charts:
                    name = "{}_trailing_with_RSI_{}-Up_{}-Down".format(symbol, up_percent, down_percent)
                    print("Plotting chart ", name)
                    dc.plot_chart(name, symbol)

    if test_trailing_strategy:
        for symbol in tickers:
            for up_percent, down_percent in updown_vals:
                dc.read_symbol_data(symbol)
                realized = trader.trailing_strategy(symbol, 100, up_percent=up_percent, down_percent=down_percent)
                if plot_charts:
                    name = "{}_trailing_strategy_{}-Up_{}-Down".format(symbol, up_percent, down_percent)
                    print("Plotting chart ", name)
                    dc.plot_chart(name, symbol)
            # if realized > max_realized:
            #     max_realized = realized
            #     max_realized_with = (up, down)
