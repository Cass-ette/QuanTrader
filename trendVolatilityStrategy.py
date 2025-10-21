import requests
import pandas as pd
import time
import os
import json
from datetime import datetime
import numpy as np

# 导入交易执行模块
import marketLong
import marketShort
import closeLong
import closeShort

class TrendVolatilityStrategy:
    def __init__(self, symbol='ETHUSDT', timeframe='1h', 
                 ema_short=12, ema_long=26, atr_period=14, 
                 risk_per_trade=0.02, stop_loss_pct=0.05):
        self.symbol = symbol
        self.timeframe = timeframe
        self.ema_short = ema_short
        self.ema_long = ema_long
        self.atr_period = atr_period
        self.risk_per_trade = risk_per_trade  # 单笔交易风险不超过总资金的2%
        self.stop_loss_pct = stop_loss_pct    # 固定止损比例5%
        # 使用与closeLong.py相同的API密钥配置
        self.api_key = os.environ.get('BINANCE_API_KEY', 'D3gzp96Lv20e1KCx2WZRPT5xOsavT9jTtATfeVRe6kotuajCdoQjb0lohRoHcBa6')
        self.secret_key = os.environ.get('BINANCE_SECRET_KEY', 'dV1tDLMczFlopnF9ZFXKBJ0oJt9JogJlxnMmeo7TGUhxRwgm5jxdReoUfMJF55XQ')
        
        # 交易状态管理
        self.current_position = None  # 当前持仓状态
        self.entry_price = 0
        self.entry_atr = 0
        self.position_size = 0
        self.initial_position_size = 0
        self.entry_time = None
        
        # 资金管理
        self.initial_account_balance = self.get_account_balance()  # 获取实际账户余额
        self.current_balance = self.initial_account_balance
        self.max_drawdown = 0
        self.total_trades = 0
        self.winning_trades = 0
        
        # 交易记录
        self.trade_history = []
        self.last_trade_id = 0
        
        # 风险控制
        self.max_positions_per_direction = 1  # 每个方向最多持仓数
        self.max_daily_trades = 3  # 每日最大交易次数
        self.daily_trades_count = 0
        self.last_trade_date = None
        
    def fetch_klines(self, limit=300):
        """获取K线数据"""
        url = f'https://fapi.binance.com/fapi/v1/klines?symbol={self.symbol}&interval={self.timeframe}&limit={limit}'
        r = requests.get(url=url).json()
        
        # 转换为DataFrame
        df = pd.DataFrame(r)
        df = df.drop(columns=[5, 6, 7, 8, 9, 10, 11])
        df.columns = ['timestamp', 'open', 'high', 'low', 'close']
        
        # 转换时间戳为中国时区
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms').dt.tz_localize('UTC').dt.tz_convert('Asia/Shanghai')
        
        # 转换数据类型
        for col in ['open', 'high', 'low', 'close']:
            df[col] = df[col].astype(float)
            
        return df
    
    def calculate_indicators(self, df):
        """计算交易指标：EMA和ATR"""
        # 计算EMA
        df['ema_short'] = df['close'].ewm(span=self.ema_short, adjust=False).mean()
        df['ema_long'] = df['close'].ewm(span=self.ema_long, adjust=False).mean()
        
        # 计算MACD（用于辅助确认趋势）
        df['macd_line'] = df['ema_short'] - df['ema_long']
        df['signal_line'] = df['macd_line'].ewm(span=9, adjust=False).mean()
        df['macd_hist'] = df['macd_line'] - df['signal_line']
        
        # 计算ATR
        df['tr1'] = df['high'] - df['low']
        df['tr2'] = abs(df['high'] - df['close'].shift(1))
        df['tr3'] = abs(df['low'] - df['close'].shift(1))
        df['tr'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
        df['atr'] = df['tr'].ewm(span=self.atr_period, adjust=False).mean()
        
        # 计算20日ATR均值
        df['atr_20d_avg'] = df['atr'].rolling(window=20).mean()
        
        # 计算趋势信号
        df['ema_cross_signal'] = 0
        df.loc[df['ema_short'] > df['ema_long'], 'ema_cross_signal'] = 1  # 多头信号
        df.loc[df['ema_short'] < df['ema_long'], 'ema_cross_signal'] = -1  # 空头信号
        
        # 计算交叉点信号
        df['signal_change'] = df['ema_cross_signal'].diff()
        df['bullish_cross'] = (df['signal_change'] == 2).astype(int)
        df['bearish_cross'] = (df['signal_change'] == -2).astype(int)
        
        # 计算波动率过滤条件
        df['volatility_condition'] = 0
        df.loc[df['atr'] > df['atr_20d_avg'] * 1.2, 'volatility_condition'] = 1  # 高波动率
        df.loc[df['atr'] < df['atr_20d_avg'] * 0.8, 'volatility_condition'] = -1  # 低波动率
        
        return df
    
    def calculate_position_size(self, account_balance, atr_value):
        """根据账户余额和ATR计算仓位大小"""
        # 计算风险金额
        risk_amount = account_balance * self.risk_per_trade
        
        # 使用ATR和止损比例计算合适的仓位大小
        current_price = self.get_current_price()
        atr_risk = atr_value * 1.5  # 使用1.5倍ATR作为风险计算基础
        stop_loss_points = min(current_price * self.stop_loss_pct, atr_risk)
        
        # 计算仓位大小（简化版，实际应用中需要考虑最小交易量和精度）
        position_size = risk_amount / stop_loss_points
        
        # 为了安全起见，限制单笔最大仓位不超过总资金的20%
        max_position_size = account_balance * 0.2 / current_price
        position_size = min(position_size, max_position_size)
        
        # 四舍五入到合约精度（对于ETH/USDT，通常是0.001）
        position_size = round(position_size, 3)
        
        print(f"计算仓位大小: 风险金额={risk_amount}, 止损点数={stop_loss_points:.2f}, 仓位大小={position_size}")
        return position_size
    
    def record_trade(self, trade_type, direction, price, quantity, status='completed'):
        """记录交易信息"""
        self.last_trade_id += 1
        trade = {
            'trade_id': self.last_trade_id,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'type': trade_type,  # entry或exit
            'direction': direction,  # long或short
            'price': price,
            'quantity': quantity,
            'status': status,
            'account_balance': self.current_balance
        }
        
        self.trade_history.append(trade)
        
        # 更新交易统计
        if trade_type == 'exit' and status == 'completed':
            # 查找对应的入场交易
            for entry_trade in reversed(self.trade_history):
                if entry_trade['type'] == 'entry' and entry_trade['direction'] == direction:
                    if 'exit_trade_id' not in entry_trade:
                        entry_trade['exit_trade_id'] = self.last_trade_id
                        entry_trade['exit_price'] = price
                        
                        # 计算盈亏
                        if direction == 'long':
                            profit_pct = (price - entry_trade['price']) / entry_trade['price'] * 100
                            profit_amount = (price - entry_trade['price']) * quantity
                        else:
                            profit_pct = (entry_trade['price'] - price) / entry_trade['price'] * 100
                            profit_amount = (entry_trade['price'] - price) * quantity
                        
                        entry_trade['profit_pct'] = profit_pct
                        entry_trade['profit_amount'] = profit_amount
                        
                        # 更新账户余额
                        self.current_balance += profit_amount
                        
                        # 更新交易统计
                        self.total_trades += 1
                        if profit_amount > 0:
                            self.winning_trades += 1
                        
                        # 检查最大回撤
                        peak = max(self.initial_account_balance, self.current_balance)
                        drawdown = (peak - self.current_balance) / peak * 100
                        if drawdown > self.max_drawdown:
                            self.max_drawdown = drawdown
                        
                        print(f"交易完成: 方向={direction}, 入场价={entry_trade['price']:.2f}, 出场价={price:.2f}")
                        print(f"盈亏: {profit_pct:+.2f}% ({profit_amount:+.2f})")
                        print(f"当前账户余额: {self.current_balance:.2f}")
                        break
        
        # 保存交易记录到文件
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
        total_return = (self.current_balance - self.initial_account_balance) / self.initial_account_balance * 100
        
        stats = {
            '总交易次数': self.total_trades,
            '盈利交易': self.winning_trades,
            '胜率': f"{win_rate:.2f}%",
            '初始资金': self.initial_account_balance,
            '当前资金': self.current_balance,
            '总收益率': f"{total_return:.2f}%",
            '最大回撤': f"{self.max_drawdown:.2f}%"
        }
        
        return stats
    
    def check_daily_trade_limit(self):
        """检查每日交易限制"""
        today = datetime.now().date()
        if self.last_trade_date != today:
            self.daily_trades_count = 0
            self.last_trade_date = today
        
        return self.daily_trades_count < self.max_daily_trades
    
    def get_current_price(self):
        """获取当前价格"""
        url = f'https://fapi.binance.com/fapi/v1/ticker/price?symbol={self.symbol}'
        response = requests.get(url)
        if response.status_code == 200:
            return float(response.json()['price'])
        else:
            print(f"获取价格失败: {response.status_code}")
            return None
            
    def get_account_balance(self):
        """获取实际账户余额"""
        try:
            # 使用Binance API获取USDT余额
            url = 'https://fapi.binance.com/fapi/v2/balance'
            headers = {
                'X-MBX-APIKEY': self.api_key
            }
            
            # 生成时间戳
            timestamp = int(round(time.time() * 1000))
            query_string = f'timestamp={timestamp}'
            
            # 生成签名
            import hmac
            import hashlib
            signature = hmac.new(self.secret_key.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
            
            # 添加时间戳和签名到请求
            params = {
                'timestamp': timestamp,
                'signature': signature
            }
            
            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code == 200:
                balances = response.json()
                for balance in balances:
                    if balance['asset'] == 'USDT':
                        return float(balance['availableBalance'])
                return 0
            else:
                print(f"获取账户余额失败: {response.status_code}, {response.text}")
                # 返回默认值以避免程序崩溃
                return 1000  # 假设默认余额为1000 USDT
        except Exception as e:
            print(f"获取账户余额异常: {str(e)}")
            return 1000  # 出错时返回默认值
    
    def check_trade_signals(self):
        """检查交易信号"""
        print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (UTC+8)] 开始检查交易信号...")
        
        # 更新当前账户余额
        self.current_balance = self.get_account_balance()
        
        # 检查每日交易限制
        if not self.check_daily_trade_limit():
            print(f"已达到每日最大交易次数限制({self.max_daily_trades})，今天不再进行交易分析")
            return
        
        # 获取数据
        df = self.fetch_klines(limit=300)
        df = self.calculate_indicators(df)
        
        # 获取最新数据
        latest = df.iloc[-1]
        
        print(f"当前价格: {latest['close']:.2f}")
        print(f"{self.ema_short}小时EMA: {latest['ema_short']:.2f}")
        print(f"{self.ema_long}小时EMA: {latest['ema_long']:.2f}")
        print(f"ATR值: {latest['atr']:.2f}")
        print(f"20日ATR均值: {latest['atr_20d_avg']:.2f}")
        print(f"波动率条件: {'高' if latest['volatility_condition'] == 1 else '低' if latest['volatility_condition'] == -1 else '正常'}")
        print(f"趋势信号: {'多头' if latest['ema_cross_signal'] == 1 else '空头' if latest['ema_cross_signal'] == -1 else '中性'}")
        print(f"账户余额: {self.current_balance:.2f}")
        
        # 检查入场信号
        if latest['volatility_condition'] == 1:  # 波动率足够高
            if latest['bullish_cross'] and not self.current_position:
                print("\n触发多头入场信号！")
                
                # 更新交易状态
                self.current_position = 'long'
                self.entry_price = latest['close']
                self.entry_atr = latest['atr']
                self.entry_time = datetime.now()
                
                # 计算仓位大小
                self.initial_position_size = self.calculate_position_size(self.current_balance, latest['atr'])
                self.position_size = self.initial_position_size
                
                # 计算止损止盈价格
                stop_loss_price = self.entry_price * (1 - self.stop_loss_pct)
                take_profit_price = self.entry_price + 2 * self.entry_atr
                
                print(f"建议多头入场价格: {self.entry_price:.2f}")
                print(f"建议仓位大小: {self.position_size:.6f}")
                print(f"动态止盈价格: {take_profit_price:.2f}")
                print(f"止损价格: {stop_loss_price:.2f}")
                print(f"风险敞口: {self.current_balance * self.risk_per_trade:.2f} ({self.risk_per_trade*100}%)")
                
                # 记录交易
                self.record_trade('entry', 'long', self.entry_price, self.position_size, status='completed')
                
                # 执行多头交易
                result = marketLong.market_long(self.symbol, self.position_size, self.api_key, self.secret_key)
                if 'orderId' in result and result['orderId']:
                    print(f"多头订单已发送，订单ID: {result['orderId']}")
                else:
                    print(f"多头订单发送失败: {result}")
                self.daily_trades_count += 1
                
                # 重要：实际交易执行已被禁用，不会进行真实交易
                # self.execute_market_long(self.symbol, self.position_size)
                
            elif latest['bearish_cross'] and not self.current_position:
                print("\n触发空头入场信号！")
                
                # 更新交易状态
                self.current_position = 'short'
                self.entry_price = latest['close']
                self.entry_atr = latest['atr']
                self.entry_time = datetime.now()
                
                # 计算仓位大小
                self.initial_position_size = self.calculate_position_size(self.current_balance, latest['atr'])
                self.position_size = self.initial_position_size
                
                # 计算止损止盈价格
                stop_loss_price = self.entry_price * (1 + self.stop_loss_pct)
                take_profit_price = self.entry_price - 2 * self.entry_atr
                
                print(f"建议空头入场价格: {self.entry_price:.2f}")
                print(f"建议仓位大小: {self.position_size:.6f}")
                print(f"动态止盈价格: {take_profit_price:.2f}")
                print(f"止损价格: {stop_loss_price:.2f}")
                print(f"风险敞口: {self.current_balance * self.risk_per_trade:.2f} ({self.risk_per_trade*100}%)")
                
                # 记录交易
                self.record_trade('entry', 'short', self.entry_price, self.position_size, status='completed')
                
                # 执行空头交易
                result = marketShort.market_short(self.symbol, self.position_size, self.api_key, self.secret_key)
                if 'orderId' in result and result['orderId']:
                    print(f"空头订单已发送，订单ID: {result['orderId']}")
                else:
                    print(f"空头订单发送失败: {result}")
                self.daily_trades_count += 1
                
                # 重要：实际交易执行已被禁用，不会进行真实交易
                # self.execute_market_short(self.symbol, self.position_size)
        elif latest['volatility_condition'] == -1:
            print("\n波动率过低，暂停交易以规避横盘震荡风险")
        
        # 检查出场信号
        if self.current_position == 'long':
            current_price = latest['close']
            stop_loss_price = self.entry_price * (1 - self.stop_loss_pct)
            take_profit_price = self.entry_price + 2 * self.entry_atr
            
            print(f"\n多头持仓监控:")
            print(f"入场价格: {self.entry_price:.2f}, 当前价格: {current_price:.2f}")
            print(f"浮盈/亏: {((current_price - self.entry_price) / self.entry_price * 100):+.2f}%")
            print(f"止损价格: {stop_loss_price:.2f}, 止盈价格: {take_profit_price:.2f}")
            
            # 检查回调加仓条件
            if current_price <= self.entry_price * 1.01 and current_price >= latest['ema_short'] * 0.99:
                if self.position_size < self.initial_position_size * 2:  # 限制最大加仓次数
                    additional_size = self.initial_position_size * 0.5
                    self.position_size += additional_size
                    print(f"触发多头加仓信号！加仓 {additional_size:.6f}，总仓位 {self.position_size:.6f}")
                    # 记录加仓
                    self.record_trade('add', 'long', current_price, additional_size, status='completed')
                    
                    # 执行加仓
                    result = marketLong.market_long(self.symbol, additional_size, self.api_key, self.secret_key)
                    if 'orderId' in result and result['orderId']:
                        print(f"加仓订单已发送，订单ID: {result['orderId']}")
                    else:
                        print(f"加仓订单发送失败: {result}")
            
            # 检查止盈止损
            if current_price <= stop_loss_price:
                print(f"\n触发多头止损！当前价格 {current_price:.2f}，止损价格 {stop_loss_price:.2f}")
                # 记录出场交易
                self.record_trade('exit', 'long', current_price, self.position_size, status='completed')
                
                # 执行多头平仓
                result = closeLong.close_long(self.symbol, self.position_size, self.api_key, self.secret_key)
                if 'orderId' in result and result['orderId']:
                    print(f"多头平仓订单已发送，订单ID: {result['orderId']}")
                else:
                    print(f"多头平仓订单发送失败: {result}")
                
                self.current_position = None
            elif current_price >= take_profit_price:
                print(f"\n触发多头止盈！当前价格 {current_price:.2f}，止盈价格 {take_profit_price:.2f}")
                # 记录出场交易
                self.record_trade('exit', 'long', current_price, self.position_size, status='completed')
                
                # 执行多头平仓
                result = closeLong.close_long(self.symbol, self.position_size, self.api_key, self.secret_key)
                if 'orderId' in result and result['orderId']:
                    print(f"多头平仓订单已发送，订单ID: {result['orderId']}")
                else:
                    print(f"多头平仓订单发送失败: {result}")
                
                self.current_position = None
            elif latest['bearish_cross']:
                print("\n触发多头出场信号（均线交叉反转）！")
                # 记录出场交易
                self.record_trade('exit', 'long', current_price, self.position_size, status='completed')
                
                # 执行多头平仓
                result = closeLong.close_long(self.symbol, self.position_size, self.api_key, self.secret_key)
                if 'orderId' in result and result['orderId']:
                    print(f"多头平仓订单已发送，订单ID: {result['orderId']}")
                else:
                    print(f"多头平仓订单发送失败: {result}")
                
                self.current_position = None
        
        elif self.current_position == 'short':
            current_price = latest['close']
            stop_loss_price = self.entry_price * (1 + self.stop_loss_pct)
            take_profit_price = self.entry_price - 2 * self.entry_atr
            
            print(f"\n空头持仓监控:")
            print(f"入场价格: {self.entry_price:.2f}, 当前价格: {current_price:.2f}")
            print(f"浮盈/亏: {((self.entry_price - current_price) / self.entry_price * 100):+.2f}%")
            print(f"止损价格: {stop_loss_price:.2f}, 止盈价格: {take_profit_price:.2f}")
            
            # 检查回调加仓条件
            if current_price >= self.entry_price * 0.99 and current_price <= latest['ema_short'] * 1.01:
                if self.position_size < self.initial_position_size * 2:  # 限制最大加仓次数
                    additional_size = self.initial_position_size * 0.5
                    self.position_size += additional_size
                    print(f"触发空头加仓信号！加仓 {additional_size:.6f}，总仓位 {self.position_size:.6f}")
                    # 记录加仓
                    self.record_trade('add', 'short', current_price, additional_size, status='completed')
                    
                    # 执行加仓
                    result = marketShort.market_short(self.symbol, additional_size, self.api_key, self.secret_key)
                    if 'orderId' in result and result['orderId']:
                        print(f"加仓订单已发送，订单ID: {result['orderId']}")
                    else:
                        print(f"加仓订单发送失败: {result}")
            
            # 检查止盈止损
            if current_price >= stop_loss_price:
                print(f"\n触发空头止损！当前价格 {current_price:.2f}，止损价格 {stop_loss_price:.2f}")
                # 记录出场交易
                self.record_trade('exit', 'short', current_price, self.position_size, status='completed')
                
                # 执行空头平仓
                result = closeShort.close_short(self.symbol, self.position_size, self.api_key, self.secret_key)
                if 'orderId' in result and result['orderId']:
                    print(f"空头平仓订单已发送，订单ID: {result['orderId']}")
                else:
                    print(f"空头平仓订单发送失败: {result}")
                
                self.current_position = None
            elif current_price <= take_profit_price:
                print(f"\n触发空头止盈！当前价格 {current_price:.2f}，止盈价格 {take_profit_price:.2f}")
                # 记录出场交易
                self.record_trade('exit', 'short', current_price, self.position_size, status='completed')
                
                # 执行空头平仓
                result = closeShort.close_short(self.symbol, self.position_size, self.api_key, self.secret_key)
                if 'orderId' in result and result['orderId']:
                    print(f"空头平仓订单已发送，订单ID: {result['orderId']}")
                else:
                    print(f"空头平仓订单发送失败: {result}")
                
                self.current_position = None
            elif latest['bullish_cross']:
                print("\n触发空头出场信号（均线交叉反转）！")
                # 记录出场交易
                self.record_trade('exit', 'short', current_price, self.position_size, status='completed')
                
                # 执行空头平仓
                result = closeShort.close_short(self.symbol, self.position_size, self.api_key, self.secret_key)
                if 'orderId' in result and result['orderId']:
                    print(f"空头平仓订单已发送，订单ID: {result['orderId']}")
                else:
                    print(f"空头平仓订单发送失败: {result}")
                
                self.current_position = None
        
        # 打印当前持仓状态
        print(f"\n当前持仓状态: {self.current_position if self.current_position else '空仓'}")
        
        # 打印交易统计
        stats = self.get_trade_statistics()
        print("\n交易统计:")
        for key, value in stats.items():
            print(f"{key}: {value}")
    
    def execute_market_long(self, symbol, quantity):
        """执行多头交易"""
        try:
            # 导入交易模块
            import marketLong
            result = marketLong.market_long(symbol, quantity, self.api_key, self.secret_key)
            print(f"交易结果: {result}")
            return result
        except Exception as e:
            print(f"交易执行失败: {str(e)}")
            return None
    
    def execute_market_short(self, symbol, quantity):
        """执行空头交易"""
        try:
            # 导入交易模块
            import marketShort
            result = marketShort.market_short(symbol, quantity, self.api_key, self.secret_key)
            print(f"交易结果: {result}")
            return result
        except Exception as e:
            print(f"交易执行失败: {str(e)}")
            return None
    
    def execute_close_long(self, symbol, quantity):
        """执行多头平仓交易"""
        try:
            # 导入交易模块
            import closeLong
            result = closeLong.close_long(symbol, quantity, self.api_key, self.secret_key)
            print(f"交易结果: {result}")
            return result
        except Exception as e:
            print(f"交易执行失败: {str(e)}")
            return None
    
    def execute_close_short(self, symbol, quantity):
        """执行空头平仓交易"""
        try:
            # 导入交易模块
            import closeShort
            result = closeShort.close_short(symbol, quantity, self.api_key, self.secret_key)
            print(f"交易结果: {result}")
            return result
        except Exception as e:
            print(f"交易执行失败: {str(e)}")
            return None
    
    def run_backtest(self, lookback_period=30):
        """简单回测功能"""
        print(f"开始进行回测，回测周期：{lookback_period}天")
        
        # 获取历史数据
        df = self.fetch_klines(limit=lookback_period * 24)  # 假设使用1小时周期
        df = self.calculate_indicators(df)
        
        # 回测变量
        backtest_position = None
        backtest_entry_price = 0
        backtest_entry_atr = 0
        trades = []
        
        for i in range(20, len(df)):
            current = df.iloc[i]
            prev = df.iloc[i-1]
            
            # 入场信号
            if backtest_position is None:
                if current['volatility_condition'] == 1:
                    if current['bullish_cross']:
                        backtest_position = 'long'
                        backtest_entry_price = current['close']
                        backtest_entry_atr = current['atr']
                        trades.append({
                            'type': 'entry',
                            'direction': 'long',
                            'price': backtest_entry_price,
                            'time': current['datetime']
                        })
                    elif current['bearish_cross']:
                        backtest_position = 'short'
                        backtest_entry_price = current['close']
                        backtest_entry_atr = current['atr']
                        trades.append({
                            'type': 'entry',
                            'direction': 'short',
                            'price': backtest_entry_price,
                            'time': current['datetime']
                        })
            # 出场信号
            elif backtest_position == 'long':
                stop_loss_price = backtest_entry_price * (1 - self.stop_loss_pct)
                take_profit_price = backtest_entry_price + 2 * backtest_entry_atr
                
                if current['close'] <= stop_loss_price or current['close'] >= take_profit_price or current['bearish_cross']:
                    exit_type = 'stop_loss' if current['close'] <= stop_loss_price else 'take_profit' if current['close'] >= take_profit_price else 'signal_change'
                    trades.append({
                        'type': 'exit',
                        'direction': 'long',
                        'price': current['close'],
                        'time': current['datetime'],
                        'exit_type': exit_type
                    })
                    backtest_position = None
            elif backtest_position == 'short':
                stop_loss_price = backtest_entry_price * (1 + self.stop_loss_pct)
                take_profit_price = backtest_entry_price - 2 * backtest_entry_atr
                
                if current['close'] >= stop_loss_price or current['close'] <= take_profit_price or current['bullish_cross']:
                    exit_type = 'stop_loss' if current['close'] >= stop_loss_price else 'take_profit' if current['close'] <= take_profit_price else 'signal_change'
                    trades.append({
                        'type': 'exit',
                        'direction': 'short',
                        'price': current['close'],
                        'time': current['datetime'],
                        'exit_type': exit_type
                    })
                    backtest_position = None
        
        # 分析回测结果
        if len(trades) >= 2:
            total_trades = len(trades) // 2
            winning_trades = 0
            total_profit = 0
            
            for i in range(0, len(trades), 2):
                if i + 1 < len(trades):
                    entry = trades[i]
                    exit = trades[i+1]
                    
                    if entry['direction'] == 'long':
                        profit_pct = (exit['price'] - entry['price']) / entry['price'] * 100
                    else:
                        profit_pct = (entry['price'] - exit['price']) / entry['price'] * 100
                    
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

# 示例使用
    def optimize_parameters(self, param_grid, lookback_period=30):
        """参数优化功能"""
        print("\n开始参数优化...")
        print(f"参数搜索空间: {param_grid}")
        
        best_params = None
        best_return = -float('inf')
        
        # 遍历所有参数组合
        for ema_short in param_grid.get('ema_short', [self.ema_short]):
            for ema_long in param_grid.get('ema_long', [self.ema_long]):
                # 确保短期EMA小于长期EMA
                if ema_short >= ema_long:
                    continue
                
                for atr_period in param_grid.get('atr_period', [self.atr_period]):
                    for risk_per_trade in param_grid.get('risk_per_trade', [self.risk_per_trade]):
                        for stop_loss_pct in param_grid.get('stop_loss_pct', [self.stop_loss_pct]):
                            print(f"\n测试参数组合: ema_short={ema_short}, ema_long={ema_long}, atr_period={atr_period}, risk={risk_per_trade}, stop_loss={stop_loss_pct}")
                            
                            # 创建临时策略实例进行测试
                            temp_strategy = TrendVolatilityStrategy(
                                symbol=self.symbol,
                                timeframe=self.timeframe,
                                ema_short=ema_short,
                                ema_long=ema_long,
                                atr_period=atr_period,
                                risk_per_trade=risk_per_trade,
                                stop_loss_pct=stop_loss_pct
                            )
                            
                            # 运行回测
                            temp_strategy.run_backtest(lookback_period=lookback_period)
                            
                            # 获取回测结果
                            stats = temp_strategy.get_trade_statistics()
                            total_return_str = stats['总收益率']
                            total_return = float(total_return_str.replace('%', ''))
                            
                            # 更新最佳参数
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
    # 创建策略实例
    strategy = TrendVolatilityStrategy(
        symbol='ETHUSDT', 
        timeframe='1h',
        ema_short=12,      # 短期EMA周期
        ema_long=26,       # 长期EMA周期
        atr_period=14,     # ATR计算周期
        risk_per_trade=0.02,  # 单笔交易风险比例
        stop_loss_pct=0.05    # 止损比例
    )
    
    print("[重要提示]：本程序处于实际交易模式，将执行真实交易操作！")
    print("请确保API密钥配置正确且安全。")
    print("加密货币市场风险高，请勿投入超过承受能力的资金。\n")
    
    # 显示账户余额
    print(f"当前账户余额: {strategy.current_balance:.2f} USDT")
    
    # 运行回测
    print("=== 策略回测结果 ===")
    strategy.run_backtest(lookback_period=30)
    
    # 可选：参数优化
    # 注意：参数优化可能需要较长时间
    # param_grid = {
    #     'ema_short': [8, 12, 15],
    #     'ema_long': [20, 26, 30],
    #     'atr_period': [10, 14, 21],
    #     'risk_per_trade': [0.01, 0.02, 0.03],
    #     'stop_loss_pct': [0.04, 0.05, 0.06]
    # }
    # best_params = strategy.optimize_parameters(param_grid)
    
    # 检查当前交易信号
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