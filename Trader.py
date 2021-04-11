import DataCollector
import os
import logging
import numpy
import talib

class Trader():
    def __init__(self, datacollector):
        logger =  logging.getLogger('datacollector')
        # logger.setLevel(logging.INFO)
        logger.setLevel(logging.CRITICAL)
        ch = logging.StreamHandler()
        fh = logging.FileHandler("Trading_bot.log", mode="w", encoding=None, errors = None)
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

            self.datacollector.store_plot_values(symbol, cur_price = cur_price, 
                                portfolio = portfolio_value, 
                                realized = investment, 
                                trail_down = trail_val)
            cur_price = self.datacollector.get_next_value(symbol)

        return [0],0,0

    def trailing_sell(self, symbol, cur_price, up_percent, qty):
        self.logger.info("{} : Starting to trail_up with {}% to sell {} qty".format(symbol, up_percent, qty))

        trail_gap = cur_price * up_percent / 100
        trail_val = cur_price - trail_gap
        prices = []
        realized = self.datacollector.symbol_vals[symbol].plot_arrays["realized"][-1]

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
                fee = portfolio_value * self.fee_percent / 100
                portfolio_value -= fee
                self.logger.info("{} : Sold {} at price {} after trailing with {}% for {}".format(symbol, qty, cur_price, up_percent, portfolio_value))
                self.logger.warning("SELL : trail: {}, price: {}, qty: {}, total value: {}".format(
                    trail_val, cur_price, qty, portfolio_value))
                return prices, 0, portfolio_value

            self.datacollector.store_plot_values(symbol, cur_price = cur_price, 
                                portfolio = portfolio_value, 
                                realized = realized, 
                                trail_up = trail_val)

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
            prices, holding_qty, traded_value = self.trailing_sell(symbol, cur_price, up_percent, holding_qty)
            cur_price = prices[-1]
            if cur_price == 0 or cur_price is None:
                break
            investment = traded_value
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
        cur_price = self.datacollector.get_next_value(symbol)

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
                    self.logger.info("{} : price = {}, rsi = {}. start trailing down with {}% to buy".format(symbol, cur_price, cur_rsi, down_percent))
                    prices, holding_qty, traded_value = self.trailing_buy(symbol, cur_price, down_percent, cash)
                    cur_price = prices[-1]
                    if cur_price == 0:
                        break
                    cash = 0
                    prices_list.extend(prices)
                    prices_list = prices_list[:RSI_PERIOD]

                if (cur_rsi > RSI_OVERBOUGHT) and (holding_qty > 0):
                    self.logger.info("{} : price = {}, rsi = {}. start trailing up with {}% to sell".format(symbol, cur_price, cur_rsi, up_percent))
                    prices, holding_qty, realized = self.trailing_sell(symbol, cur_price, up_percent, holding_qty)
                    cash = realized
                    cur_price = prices[-1]
                    if cur_price == 0:
                        break
                    prices_list.extend(prices)
                    prices_list = prices_list[:RSI_PERIOD]

                prices_list.pop(0)
            portfolio = (holding_qty * cur_price) + cash
            self.datacollector.store_plot_values(symbol, cur_price = cur_price, 
                                portfolio = portfolio, 
                                realized = realized)


            cur_price = self.datacollector.get_next_value(symbol)
        plot_arrays = self.datacollector.symbol_vals[symbol].plot_arrays
        base = plot_arrays["base"][-1] if len (plot_arrays["base"]) > 0 else 0
        self.logger.critical("{:<20} : {:<12} strategy: Up% = {}, Down% = {}. Retained {:6.2f} (base {:6.2f}) ".format(
                    Strategy_name, symbol, up_percent, down_percent, portfolio, base))
        return portfolio, base

if __name__=='__main__':
    plot_charts = True
    test_trailing_with_RSI = True
    test_trailing_strategy = True

    interested_cryptos = []
    dc = DataCollector.DataCollector()
    supported_symbols = dc.get_supported_symbols(fallback_to_local = True)
    # interested_cryptos = ["USDT"] # for all USDT pairs
    # interested_cryptos = ["BTCUSDT", "ETHUSDT"] # for individual pairs

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

    updown_vals = [(1,1), (2,2), (5,5), (10,4)]
    updown_vals = [(5,2)]
    trader = Trader(dc)
    if test_trailing_with_RSI:
        for symbol in tickers:
            for up_percent, down_percent in updown_vals:
                dc.read_symbol_data(symbol)
                realized = trader.trailing_with_RSI(symbol, 100, up_percent=up_percent, down_percent=down_percent)
                if plot_charts:
                    dc.plot_chart("{}_trailing_with_RSI_{}-Up_{}-Down".format(symbol, up_percent, down_percent), symbol)

    if test_trailing_strategy:
        for symbol in tickers:
            for up_percent, down_percent in updown_vals:
                dc.read_symbol_data(symbol)
                realized = trader.trailing_strategy(symbol, 100, up_percent=up_percent, down_percent=down_percent)
                if plot_charts:
                    dc.plot_chart("{}_trailing_strategy_{}-Up_{}-Down".format(symbol, up_percent, down_percent), symbol)
            # if realized > max_realized:
            #     max_realized = realized
            #     max_realized_with = (up, down)
