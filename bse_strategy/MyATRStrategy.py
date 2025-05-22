from vnpy_ctastrategy import (
    CtaTemplate,
    StopOrder,
    TickData,
    BarData,
    TradeData,
    OrderData,
    BarGenerator,
    ArrayManager,
)


class MyAtrRsiStrategy(CtaTemplate):
    """"""

    author = "用Python的交易员"

    atr_length = 22
    atr_ma_length = 10
    rsi_length = 5
    rsi_entry = 16
    trailing_percent = 0.8
    fixed_size = 1

    atr_value = 0
    atr_ma = 0
    rsi_value = 0
    rsi_buy = 0
    rsi_sell = 0
    intra_trade_high = 0
    intra_trade_low = 0

    parameters = [
        "atr_length",
        "atr_ma_length",
        "rsi_length",
        "rsi_entry",
        "trailing_percent",
        "fixed_size"
    ]
    variables = [
        "atr_value",
        "atr_ma",
        "rsi_value",
        "rsi_buy",
        "rsi_sell",
        "intra_trade_high",
        "intra_trade_low"
    ]

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        """"""
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        self.bg = BarGenerator(self.on_bar)
        self.am = ArrayManager()

    def on_init(self):
        """
        Callback when strategy is inited.
        """
        self.write_log("策略初始化")

        self.rsi_buy = 50 + self.rsi_entry
        self.rsi_sell = 50 - self.rsi_entry

        self.load_bar(10)

    def on_start(self):
        """
        Callback when strategy is started.
        """
        self.write_log("策略启动")

    def on_stop(self):
        """
        Callback when strategy is stopped.
        """
        self.write_log("策略停止")

    def on_tick(self, tick: TickData):
        """
        Callback of new tick data update.
        """
        self.bg.update_tick(tick)

    def on_bar(self, bar: BarData):
        """
        当新的K线数据更新时的回调函数。
        
        参数:
        bar: BarData类型，表示新的K线数据。
        """
        # 取消所有挂单
        self.cancel_all()

        # 更新行情分析对象中的K线数据
        am = self.am
        am.update_bar(bar)
        # 如果行情分析对象未初始化，则直接返回
        if not am.inited:
            return

        # 计算并获取ATR（平均真实波幅）数组
        atr_array = am.atr(self.atr_length, array=True)
        # 设置当前的ATR值和ATR移动平均值
        self.atr_value = atr_array[-1]
        self.atr_ma = atr_array[-self.atr_ma_length:].mean()
        # 计算并获取RSI（相对强弱指数）值
        self.rsi_value = am.rsi(self.rsi_length)

        # 如果当前持仓为0
        if self.pos == 0:
            # 初始化当前交易日内的最高价和最低价
            self.intra_trade_high = bar.high_price
            self.intra_trade_low = bar.low_price

            # 如果ATR值大于ATR移动平均值，则进行买入判断
            if self.atr_value > self.atr_ma:
                # 如果RSI值大于设定的买入阈值，则执行买入操作
                if self.rsi_value > self.rsi_buy:
                    self.buy(bar.close_price*1.01, self.fixed_size)
                # 如果RSI值小于设定的卖出阈值，则执行卖出操作（注：该部分代码已注释）
                # elif self.rsi_value < self.rsi_sell:
                #     self.short(bar.close_price - 5, self.fixed_size)

        # 如果当前持有买单
        elif self.pos > 0:
            # 更新当前交易日内的最高价和最低价
            self.intra_trade_high = max(self.intra_trade_high, bar.high_price)
            self.intra_trade_low = bar.low_price

            # 计算多单的止盈价，并挂单卖出
            long_stop = self.intra_trade_high * (1 - self.trailing_percent / 100)
            self.sell(long_stop, abs(self.pos), stop=True)

        # 如果当前持有卖单（注：该部分代码已注释）
        # elif self.pos < 0:
        #     # 更新当前交易日内的最低价和最高价
        #     self.intra_trade_low = min(self.intra_trade_low, bar.low_price)
        #     self.intra_trade_high = bar.high_price
        #
        #     # 计算空单的止盈价，并挂单买入平仓
        #     short_stop = self.intra_trade_low * (1 + self.trailing_percent / 100)
        #     self.cover(short_stop, abs(self.pos), stop=True)

        # 触发事件，通知更新UI或其他组件
        self.put_event()


    def on_order(self, order: OrderData):
        """
        Callback of new order data update.
        """
        pass

    def on_trade(self, trade: TradeData):
        """
        Callback of new trade data update.
        """
        self.put_event()

    def on_stop_order(self, stop_order: StopOrder):
        """
        Callback of stop order update.
        """
        pass
