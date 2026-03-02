import requests
import pandas as pd
import time
import json
from datetime import datetime
import numpy as np
import sys

import marketLong
import marketShort
import closeLong
import closeShort
from config import BINANCE_FUTURES_BASE_URL, DEFAULT_TIMEOUT, DEFAULT_SYMBOL
from binance_client import signed_request


class TrendVolatilityStrategy:
    def __init__(self, symbol='BTCUSDT', timeframe='1h',
                 ema_short=12, ema_long=26, atr_period=14,
                 risk_per_trade=0.02, stop_loss_pct=0.05):
        self.symbol = symbol
        self.timeframe = timeframe
        self.ema_short = ema_short
        self.ema_long = ema_long
        self.atr_period = atr_period
        self.risk_per_trade = risk_per_trade
        self.stop_loss_pct = stop_loss_pct

        # 交易状态管理
        self.current_position = None
        self.entry_price = 0
        self.entry_atr = 0
        self.position_size = 0
        self.initial_position_size = 0
        self.entry_time = None

        # 资金管理
        self.initial_account_balance = self.get_account_balance()
        self.current_balance = self.initial_account_balance
        self.max_drawdown = 0
        self.total_trades = 0
        self.winning_trades = 0

        # 交易记录
        self.trade_history = []
        self.last_trade_id = 0

        # 风险控制
        self.max_positions_per_direction = 1
        self.max_daily_trades = 3
        self.daily_trades_count = 0
        self.last_trade_date = None

    def fetch_klines(self, limit=300):
        """获取K线数据"""
        url = f'{BINANCE_FUTURES_BASE_URL}/fapi/v1/klines?symbol={self.symbol}&interval={self.timeframe}&limit={limit}'
        r = requests.get(url=url, timeout=DEFAULT_TIMEOUT)
        r.raise_for_status()
        r = r.json()

        df = pd.DataFrame(r)
        df = df.drop(columns=[5, 6, 7, 8, 9, 10, 11])
        df.columns = ['timestamp', 'open', 'high', 'low', 'close']

        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms').dt.tz_localize('UTC').dt.tz_convert('Asia/Shanghai')

        for col in ['open', 'high', 'low', 'close']:
            df[col] = df[col].astype(float)

        return df

    def calculate_indicators(self, df):
        """计算交易指标：EMA和ATR"""
        df['ema_short'] = df['close'].ewm(span=self.ema_short, adjust=False).mean()
        df['ema_long'] = df['close'].ewm(span=self.ema_long, adjust=False).mean()

        df['macd_line'] = df['ema_short'] - df['ema_long']
        df['signal_line'] = df['macd_line'].ewm(span=9, adjust=False).mean()
        df['macd_hist'] = df['macd_line'] - df['signal_line']

        df['tr1'] = df['high'] - df['low']
        df['tr2'] = abs(df['high'] - df['close'].shift(1))
        df['tr3'] = abs(df['low'] - df['close'].shift(1))
        df['tr'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
        df['atr'] = df['tr'].ewm(span=self.atr_period, adjust=False).mean()

        df['atr_20d_avg'] = df['atr'].rolling(window=20).mean()

        df['ema_cross_signal'] = 0
        df.loc[df['ema_short'] > df['ema_long'], 'ema_cross_signal'] = 1
        df.loc[df['ema_short'] < df['ema_long'], 'ema_cross_signal'] = -1

        df['signal_change'] = df['ema_cross_signal'].diff()
        df['bullish_cross'] = (df['signal_change'] == 2).astype(int)
        df['bearish_cross'] = (df['signal_change'] == -2).astype(int)

        df['volatility_condition'] = 0
        df.loc[df['atr'] > df['atr_20d_avg'] * 1.2, 'volatility_condition'] = 1
        df.loc[df['atr'] < df['atr_20d_avg'] * 0.8, 'volatility_condition'] = -1

        return df

    def calculate_position_size(self, account_balance, atr_value):
        """根据账户余额和ATR计算仓位大小"""
        risk_amount = account_balance * self.risk_per_trade
        current_price = self.get_current_price()
        if current_price is None:
            return 0

        atr_risk = atr_value * 1.5
        stop_loss_points = min(current_price * self.stop_loss_pct, atr_risk)

        position_size = risk_amount / stop_loss_points
        max_position_size = account_balance * 0.2 / current_price
        position_size = min(position_size, max_position_size)
        position_size = round(position_size, 3)

        print(f"计算仓位大小: 风险金额={risk_amount}, 止损点数={stop_loss_points:.2f}, 仓位大小={position_size}")
        return position_size

    def record_trade(self, trade_type, direction, price, quantity, status='completed'):
        """记录交易信息"""
        self.last_trade_id += 1
        trade = {
            'trade_id': self.last_trade_id,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'type': trade_type,
            'direction': direction,
            'price': price,
            'quantity': quantity,
            'status': status,
            'account_balance': self.current_balance
        }

        self.trade_history.append(trade)

        if trade_type == 'exit' and status == 'completed':
            for entry_trade in reversed(self.trade_history):
                if entry_trade['type'] == 'entry' and entry_trade['direction'] == direction:
                    if 'exit_trade_id' not in entry_trade:
                        entry_trade['exit_trade_id'] = self.last_trade_id
                        entry_trade['exit_price'] = price

                        if direction == 'long':
                            profit_pct = (price - entry_trade['price']) / entry_trade['price'] * 100
                            profit_amount = (price - entry_trade['price']) * quantity
                        else:
                            profit_pct = (entry_trade['price'] - price) / entry_trade['price'] * 100
                            profit_amount = (entry_trade['price'] - price) * quantity

                        entry_trade['profit_pct'] = profit_pct
                        entry_trade['profit_amount'] = profit_amount

                        self.current_balance += profit_amount

                        self.total_trades += 1
                        if profit_amount > 0:
                            self.winning_trades += 1

                        peak = max(self.initial_account_balance, self.current_balance)
                        drawdown = (peak - self.current_balance) / peak * 100
                        if drawdown > self.max_drawdown:
                            self.max_drawdown = drawdown

                        print(f"交易完成: 方向={direction}, 入场价={entry_trade['price']:.2f}, 出场价={price:.2f}")
                        print(f"盈亏: {profit_pct:+.2f}% ({profit_amount:+.2f})")
                        print(f"当前账户余额: {self.current_balance:.2f}")
                        break

        self.save_trade_history()
        return trade

    def save_trade_history(self):
        """保存交易历史到文件"""
        try:
            filename = f"trade_history_{self.symbol}_{datetime.now().strftime('%Y%m%d')}.json"
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.trade_history, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            print(f"保存交易历史失败: {str(e)}")

    def get_trade_statistics(self):
        """获取交易统计信息"""
        win_rate = self.winning_trades / self.total_trades * 100 if self.total_trades > 0 else 0
        total_return = (self.current_balance - self.initial_account_balance) / self.initial_account_balance * 100 if self.initial_account_balance > 0 else 0

        return {
            '总交易次数': self.total_trades,
            '盈利交易': self.winning_trades,
            '胜率': f"{win_rate:.2f}%",
            '初始资金': self.initial_account_balance,
            '当前资金': self.current_balance,
            '总收益率': f"{total_return:.2f}%",
            '最大回撤': f"{self.max_drawdown:.2f}%"
        }

    def check_daily_trade_limit(self):
        today = datetime.now().date()
        if self.last_trade_date != today:
            self.daily_trades_count = 0
            self.last_trade_date = today
        return self.daily_trades_count < self.max_daily_trades

    def get_current_price(self):
        """获取当前价格"""
        try:
            url = f'{BINANCE_FUTURES_BASE_URL}/fapi/v1/ticker/price?symbol={self.symbol}'
            response = requests.get(url, timeout=DEFAULT_TIMEOUT)
            if response.status_code == 200:
                return float(response.json()['price'])
            else:
                print(f"获取价格失败: {response.status_code}")
                return None
        except Exception as e:
            print(f"获取价格异常: {str(e)}")
            return None

    def get_account_balance(self):
        """获取实际账户余额"""
        try:
            balances = signed_request('GET', '/fapi/v2/balance')
            for balance in balances:
                if balance['asset'] == 'USDT':
                    return float(balance['availableBalance'])
            return 0
        except Exception as e:
            print(f"获取账户余额异常: {str(e)}")
            return 1000

    def _execute_order(self, order_func, symbol, quantity, position_side):
        """执行订单并返回结果"""
        try:
            # BUG FIX: 原代码传了4个参数(symbol, size, api_key, secret_key)给只接受3个参数的函数
            result = order_func(symbol, quantity, position_side=position_side)
            return result
        except Exception as e:
            print(f"交易执行失败: {str(e)}")
            return None

    def check_trade_signals(self):
        """检查交易信号"""
        print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (UTC+8)] 开始检查交易信号...")

        self.current_balance = self.get_account_balance()

        if not self.check_daily_trade_limit():
            print(f"已达到每日最大交易次数限制({self.max_daily_trades})，今天不再进行交易分析")
            return

        df = self.fetch_klines(limit=300)
        df = self.calculate_indicators(df)

        latest = df.iloc[-1]

        print(f"当前价格: {latest['close']:.2f}")
        print(f"{self.ema_short}小时EMA: {latest['ema_short']:.2f}")
        print(f"{self.ema_long}小时EMA: {latest['ema_long']:.2f}")
        print(f"ATR值: {latest['atr']:.2f}")
        print(f"20日ATR均值: {latest['atr_20d_avg']:.2f}")
        print(f"波动率条件: {'高' if latest['volatility_condition'] == 1 else '低' if latest['volatility_condition'] == -1 else '正常'}")
        print(f"趋势信号: {'多头' if latest['ema_cross_signal'] == 1 else '空头' if latest['ema_cross_signal'] == -1 else '中性'}")
        print(f"账户余额: {self.current_balance:.2f}")

        # 入场信号
        if latest['volatility_condition'] == 1:
            if latest['bullish_cross'] and not self.current_position:
                print("\n触发多头入场信号！")
                self.current_position = 'long'
                self.entry_price = latest['close']
                self.entry_atr = latest['atr']
                self.entry_time = datetime.now()

                self.initial_position_size = self.calculate_position_size(self.current_balance, latest['atr'])
                self.position_size = self.initial_position_size

                stop_loss_price = self.entry_price * (1 - self.stop_loss_pct)
                take_profit_price = self.entry_price + 2 * self.entry_atr

                print(f"建议多头入场价格: {self.entry_price:.2f}")
                print(f"建议仓位大小: {self.position_size:.6f}")
                print(f"动态止盈价格: {take_profit_price:.2f}")
                print(f"止损价格: {stop_loss_price:.2f}")

                self.record_trade('entry', 'long', self.entry_price, self.position_size, status='completed')
                result = self._execute_order(marketLong.market_long, self.symbol, self.position_size, 'LONG')
                if result and isinstance(result, dict) and 'orderId' in result:
                    print(f"多头订单已发送，订单ID: {result['orderId']}")
                else:
                    print(f"多头订单发送失败: {result}")
                self.daily_trades_count += 1

            elif latest['bearish_cross'] and not self.current_position:
                print("\n触发空头入场信号！")
                self.current_position = 'short'
                self.entry_price = latest['close']
                self.entry_atr = latest['atr']
                self.entry_time = datetime.now()

                self.initial_position_size = self.calculate_position_size(self.current_balance, latest['atr'])
                self.position_size = self.initial_position_size

                stop_loss_price = self.entry_price * (1 + self.stop_loss_pct)
                take_profit_price = self.entry_price - 2 * self.entry_atr

                print(f"建议空头入场价格: {self.entry_price:.2f}")
                print(f"建议仓位大小: {self.position_size:.6f}")
                print(f"动态止盈价格: {take_profit_price:.2f}")
                print(f"止损价格: {stop_loss_price:.2f}")

                self.record_trade('entry', 'short', self.entry_price, self.position_size, status='completed')
                result = self._execute_order(marketShort.market_short, self.symbol, self.position_size, 'SHORT')
                if result and isinstance(result, dict) and 'orderId' in result:
                    print(f"空头订单已发送，订单ID: {result['orderId']}")
                else:
                    print(f"空头订单发送失败: {result}")
                self.daily_trades_count += 1

        elif latest['volatility_condition'] == -1:
            print("\n波动率过低，暂停交易以规避横盘震荡风险")

        # 出场信号
        if self.current_position == 'long':
            current_price = latest['close']
            stop_loss_price = self.entry_price * (1 - self.stop_loss_pct)
            take_profit_price = self.entry_price + 2 * self.entry_atr

            print(f"\n多头持仓监控:")
            print(f"入场价格: {self.entry_price:.2f}, 当前价格: {current_price:.2f}")
            print(f"浮盈/亏: {((current_price - self.entry_price) / self.entry_price * 100):+.2f}%")
            print(f"止损价格: {stop_loss_price:.2f}, 止盈价格: {take_profit_price:.2f}")

            # 加仓
            if current_price <= self.entry_price * 1.01 and current_price >= latest['ema_short'] * 0.99:
                if self.position_size < self.initial_position_size * 2:
                    additional_size = self.initial_position_size * 0.5
                    self.position_size += additional_size
                    print(f"触发多头加仓信号！加仓 {additional_size:.6f}，总仓位 {self.position_size:.6f}")
                    self.record_trade('add', 'long', current_price, additional_size, status='completed')
                    self._execute_order(marketLong.market_long, self.symbol, additional_size, 'LONG')

            if current_price <= stop_loss_price:
                print(f"\n触发多头止损！当前价格 {current_price:.2f}，止损价格 {stop_loss_price:.2f}")
                self.record_trade('exit', 'long', current_price, self.position_size, status='completed')
                closeLong.close_all_long(self.symbol)
                self.current_position = None
            elif current_price >= take_profit_price:
                print(f"\n触发多头止盈！当前价格 {current_price:.2f}，止盈价格 {take_profit_price:.2f}")
                self.record_trade('exit', 'long', current_price, self.position_size, status='completed')
                closeLong.close_all_long(self.symbol)
                self.current_position = None
            elif latest['bearish_cross']:
                print("\n触发多头出场信号（均线交叉反转）！")
                self.record_trade('exit', 'long', current_price, self.position_size, status='completed')
                closeLong.close_all_long(self.symbol)
                self.current_position = None

        elif self.current_position == 'short':
            current_price = latest['close']
            stop_loss_price = self.entry_price * (1 + self.stop_loss_pct)
            take_profit_price = self.entry_price - 2 * self.entry_atr

            print(f"\n空头持仓监控:")
            print(f"入场价格: {self.entry_price:.2f}, 当前价格: {current_price:.2f}")
            print(f"浮盈/亏: {((self.entry_price - current_price) / self.entry_price * 100):+.2f}%")
            print(f"止损价格: {stop_loss_price:.2f}, 止盈价格: {take_profit_price:.2f}")

            # 加仓
            if current_price >= self.entry_price * 0.99 and current_price <= latest['ema_short'] * 1.01:
                if self.position_size < self.initial_position_size * 2:
                    additional_size = self.initial_position_size * 0.5
                    self.position_size += additional_size
                    print(f"触发空头加仓信号！加仓 {additional_size:.6f}，总仓位 {self.position_size:.6f}")
                    self.record_trade('add', 'short', current_price, additional_size, status='completed')
                    self._execute_order(marketShort.market_short, self.symbol, additional_size, 'SHORT')

            if current_price >= stop_loss_price:
                print(f"\n触发空头止损！当前价格 {current_price:.2f}，止损价格 {stop_loss_price:.2f}")
                self.record_trade('exit', 'short', current_price, self.position_size, status='completed')
                closeShort.close_all_short(self.symbol)
                self.current_position = None
            elif current_price <= take_profit_price:
                print(f"\n触发空头止盈！当前价格 {current_price:.2f}，止盈价格 {take_profit_price:.2f}")
                self.record_trade('exit', 'short', current_price, self.position_size, status='completed')
                closeShort.close_all_short(self.symbol)
                self.current_position = None
            elif latest['bullish_cross']:
                print("\n触发空头出场信号（均线交叉反转）！")
                self.record_trade('exit', 'short', current_price, self.position_size, status='completed')
                closeShort.close_all_short(self.symbol)
                self.current_position = None

        print(f"\n当前持仓状态: {self.current_position if self.current_position else '空仓'}")

        stats = self.get_trade_statistics()
        print("\n交易统计:")
        for key, value in stats.items():
            print(f"{key}: {value}")

    def run_backtest(self, lookback_period=30):
        """简单回测功能"""
        print(f"开始进行回测，回测周期：{lookback_period}天")

        df = self.fetch_klines(limit=lookback_period * 24)
        df = self.calculate_indicators(df)

        backtest_position = None
        backtest_entry_price = 0
        backtest_entry_atr = 0
        trades = []

        for i in range(20, len(df)):
            current = df.iloc[i]

            if backtest_position is None:
                if current['volatility_condition'] == 1:
                    if current['bullish_cross']:
                        backtest_position = 'long'
                        backtest_entry_price = current['close']
                        backtest_entry_atr = current['atr']
                        trades.append({'type': 'entry', 'direction': 'long', 'price': backtest_entry_price, 'time': current['datetime']})
                    elif current['bearish_cross']:
                        backtest_position = 'short'
                        backtest_entry_price = current['close']
                        backtest_entry_atr = current['atr']
                        trades.append({'type': 'entry', 'direction': 'short', 'price': backtest_entry_price, 'time': current['datetime']})
            elif backtest_position == 'long':
                stop_loss_price = backtest_entry_price * (1 - self.stop_loss_pct)
                take_profit_price = backtest_entry_price + 2 * backtest_entry_atr

                if current['close'] <= stop_loss_price or current['close'] >= take_profit_price or current['bearish_cross']:
                    exit_type = 'stop_loss' if current['close'] <= stop_loss_price else 'take_profit' if current['close'] >= take_profit_price else 'signal_change'
                    trades.append({'type': 'exit', 'direction': 'long', 'price': current['close'], 'time': current['datetime'], 'exit_type': exit_type})
                    backtest_position = None
            elif backtest_position == 'short':
                stop_loss_price = backtest_entry_price * (1 + self.stop_loss_pct)
                take_profit_price = backtest_entry_price - 2 * backtest_entry_atr

                if current['close'] >= stop_loss_price or current['close'] <= take_profit_price or current['bullish_cross']:
                    exit_type = 'stop_loss' if current['close'] >= stop_loss_price else 'take_profit' if current['close'] <= take_profit_price else 'signal_change'
                    trades.append({'type': 'exit', 'direction': 'short', 'price': current['close'], 'time': current['datetime'], 'exit_type': exit_type})
                    backtest_position = None

        if len(trades) >= 2:
            total_trades = len(trades) // 2
            winning_trades = 0
            total_profit = 0

            for i in range(0, len(trades), 2):
                if i + 1 < len(trades):
                    entry = trades[i]
                    exit_trade = trades[i + 1]

                    if entry['direction'] == 'long':
                        profit_pct = (exit_trade['price'] - entry['price']) / entry['price'] * 100
                    else:
                        profit_pct = (entry['price'] - exit_trade['price']) / entry['price'] * 100

                    total_profit += profit_pct
                    if profit_pct > 0:
                        winning_trades += 1

            win_rate = winning_trades / total_trades * 100 if total_trades > 0 else 0
            avg_profit = total_profit / total_trades if total_trades > 0 else 0

            print(f"回测完成，总交易次数：{total_trades}")
            print(f"胜率：{win_rate:.2f}%")
            print(f"平均收益率：{avg_profit:.2f}%")
            print(f"总收益率：{total_profit:.2f}%")
        else:
            print("回测期间未发生交易")

    def optimize_parameters(self, param_grid, lookback_period=30):
        """参数优化功能"""
        print("\n开始参数优化...")
        print(f"参数搜索空间: {param_grid}")

        best_params = None
        best_return = -float('inf')

        for ema_short in param_grid.get('ema_short', [self.ema_short]):
            for ema_long in param_grid.get('ema_long', [self.ema_long]):
                if ema_short >= ema_long:
                    continue

                for atr_period in param_grid.get('atr_period', [self.atr_period]):
                    for risk_per_trade in param_grid.get('risk_per_trade', [self.risk_per_trade]):
                        for stop_loss_pct in param_grid.get('stop_loss_pct', [self.stop_loss_pct]):
                            print(f"\n测试参数组合: ema_short={ema_short}, ema_long={ema_long}, atr_period={atr_period}, risk={risk_per_trade}, stop_loss={stop_loss_pct}")

                            temp_strategy = TrendVolatilityStrategy(
                                symbol=self.symbol,
                                timeframe=self.timeframe,
                                ema_short=ema_short,
                                ema_long=ema_long,
                                atr_period=atr_period,
                                risk_per_trade=risk_per_trade,
                                stop_loss_pct=stop_loss_pct
                            )

                            temp_strategy.run_backtest(lookback_period=lookback_period)

                            stats = temp_strategy.get_trade_statistics()
                            total_return_str = stats['总收益率']
                            total_return = float(total_return_str.replace('%', ''))

                            if total_return > best_return:
                                best_return = total_return
                                best_params = {
                                    'ema_short': ema_short,
                                    'ema_long': ema_long,
                                    'atr_period': atr_period,
                                    'risk_per_trade': risk_per_trade,
                                    'stop_loss_pct': stop_loss_pct,
                                    'total_return': total_return_str
                                }
                                print(f"找到更好的参数组合！收益率: {total_return_str}")

        print("\n参数优化完成！")
        print(f"最佳参数组合: {best_params}")
        return best_params


def main():
    symbol = DEFAULT_SYMBOL
    timeframe = '1h'
    risk_per_trade = 0.02

    if len(sys.argv) > 1:
        symbol = sys.argv[1]
    if len(sys.argv) > 2:
        timeframe = sys.argv[2]
    if len(sys.argv) > 3:
        try:
            risk_per_trade = float(sys.argv[3]) / 100
        except ValueError:
            print(f"警告: 风险比例参数无效，使用默认值 {risk_per_trade * 100}%")

    strategy = TrendVolatilityStrategy(
        symbol=symbol,
        timeframe=timeframe,
        ema_short=12,
        ema_long=26,
        atr_period=14,
        risk_per_trade=risk_per_trade,
        stop_loss_pct=0.05
    )

    print("[重要提示]：本程序处于实际交易模式，将执行真实交易操作！")
    print("请确保API密钥配置正确且安全。")
    print("加密货币市场风险高，请勿投入超过承受能力的资金。\n")

    print(f"当前账户余额: {strategy.current_balance:.2f} USDT")

    print("=== 策略回测结果 ===")
    strategy.run_backtest(lookback_period=30)

    print("\n=== 当前交易信号分析 ===")
    strategy.check_trade_signals()

    print("\n=== 策略使用说明 ===")
    print("1. 本策略基于趋势跟踪（双EMA交叉）和波动率过滤（ATR）")
    print("2. 仅在波动率足够高时才执行交易，避免横盘震荡市场")
    print("3. 使用动态止盈（基于ATR）和固定止损控制风险")
    print("4. 支持回调加仓，提高趋势捕捉效率")
    print("5. 所有交易记录会保存在当前目录下的JSON文件中")
    print("\n注意：请在充分了解风险的情况下使用此策略！")


if __name__ == "__main__":
    main()
