import ccxt
import pandas as pd
import numpy as np
import time
import datetime
import json
import hmac
import hashlib
import requests
import logging
import sys
from decimal import Decimal, getcontext
import os
from config import BINANCE_API_KEY, BINANCE_SECRET_KEY, DEFAULT_SYMBOL

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("volume_price_strategy.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("volume_price_strategy")

# 配置decimal精度
getcontext().prec = 8

class VolumePriceStrategy:
    def __init__(self, api_key=None, api_secret=None, testnet=False):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.exchange = self._init_exchange()
        self.symbol = DEFAULT_SYMBOL
        self.timeframe = '1h'  # 1小时K线
        
        # 策略参数
        self.ema_fast = 6
        self.ema_mid = 12
        self.ema_slow = 24
        self.volume_ratio_threshold = 1.5
        self.volume_ratio_min = 1.0
        self.stop_profit_points = 65  # 固定点数止盈
        self.stop_loss_points = 30  # 固定点数止损
        self.max_holding_hours = 4  # 最大持仓时间
        self.risk_per_trade = 0.015  # 单笔交易风险（1.5%）
        self.max_daily_trades = 5  # 每日最大交易次数
        self.pause_after_losses = 2  # 连续亏损次数
        self.pause_hours = 1  # 暂停交易小时数
        
        # 交易统计
        self.trade_count_today = 0
        self.consecutive_losses = 0
        self.last_pause_time = 0
        self.trade_history = []
        self.current_position = None
        self.entry_price = None
        self.entry_time = None
        self.position_size = None
        self.trade_direction = None
        
        # 加载历史交易记录
        self._load_trade_history()
        
    def _init_exchange(self):
        """初始化交易所连接"""
        exchange = ccxt.binance({
            'apiKey': self.api_key,
            'secret': self.api_secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future'
            }
        })
        
        if self.testnet:
            exchange.set_sandbox_mode(True)
            logger.info("使用测试网络模式")
        else:
            logger.info("[重要提示]：本程序处于实际交易模式，将执行真实交易操作！")
        
        # 验证连接
        try:
            exchange.load_markets()
            logger.info(f"成功连接到交易所")
        except Exception as e:
            logger.error(f"连接交易所失败: {str(e)}")
            # 即使连接失败也返回exchange对象，后续操作会捕获异常
        
        return exchange
    
    def _load_trade_history(self):
        """加载交易历史记录"""
        try:
            with open('volume_price_trade_history.json', 'r', encoding='utf-8') as f:
                self.trade_history = json.load(f)
            logger.info(f"加载交易历史记录，共{len(self.trade_history)}笔交易")
        except FileNotFoundError:
            logger.info("未找到交易历史记录文件，创建新的交易历史")
            self.trade_history = []
    
    def _save_trade_history(self):
        """保存交易历史记录"""
        try:
            with open('volume_price_trade_history.json', 'w', encoding='utf-8') as f:
                json.dump(self.trade_history, f, indent=2, ensure_ascii=False)
            logger.info(f"保存交易历史记录，共{len(self.trade_history)}笔交易")
        except Exception as e:
            logger.error(f"保存交易历史记录失败: {str(e)}")
    
    def get_account_balance(self):
        """获取账户余额"""
        try:
            timestamp = int(time.time() * 1000)
            params = {'timestamp': timestamp}
            query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
            signature = hmac.new(
                self.api_secret.encode('utf-8'),
                query_string.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            url = 'https://fapi.binance.com/fapi/v2/balance'
            headers = {'X-MBX-APIKEY': self.api_key}
            params['signature'] = signature
            
            response = requests.get(url, headers=headers, params=params)
            data = response.json()
            
            for asset in data:
                if asset['asset'] == 'USDT':
                    return float(asset['availableBalance'])
            
            return 0.0
        except Exception as e:
            logger.error(f"获取账户余额失败: {str(e)}")
            return 1000.0  # 出错时返回默认值
    
    def fetch_klines(self, limit=100):
        """获取K线数据"""
        try:
            klines = self.exchange.fetch_ohlcv(self.symbol, self.timeframe, limit=limit)
            df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df
        except Exception as e:
            logger.error(f"获取K线数据失败: {str(e)}")
            return pd.DataFrame()
    
    def calculate_indicators(self, df):
        """计算技术指标"""
        if df.empty:
            return df
        
        # 计算EMA
        df[f'ema_{self.ema_fast}'] = df['close'].ewm(span=self.ema_fast, adjust=False).mean()
        df[f'ema_{self.ema_mid}'] = df['close'].ewm(span=self.ema_mid, adjust=False).mean()
        df[f'ema_{self.ema_slow}'] = df['close'].ewm(span=self.ema_slow, adjust=False).mean()
        
        # 计算EMA斜率
        df['ema_fast_slope'] = df[f'ema_{self.ema_fast}'].diff()
        df['ema_mid_slope'] = df[f'ema_{self.ema_mid}'].diff()
        df['ema_slow_slope'] = df[f'ema_{self.ema_slow}'].diff()
        
        # 计算成交量指标
        df['volume_5h_avg'] = df['volume'].rolling(window=5).mean()
        df['volume_ratio'] = df['volume'] / df['volume_5h_avg']
        
        # 计算前2根K线的高低点
        df['prev2_high'] = df['high'].shift(2)
        df['prev2_low'] = df['low'].shift(2)
        
        # 计算ATR
        df['tr'] = np.maximum(
            df['high'] - df['low'],
            np.maximum(
                np.abs(df['high'] - df['close'].shift(1)),
                np.abs(df['low'] - df['close'].shift(1))
            )
        )
        df['atr'] = df['tr'].rolling(window=14).mean()
        
        return df
    
    def check_trend_direction(self, df):
        """检查趋势方向"""
        if len(df) < max(self.ema_fast, self.ema_mid, self.ema_slow):
            return None
        
        latest = df.iloc[-1]
        
        # 多头条件：快速EMA > 中期EMA > 慢速EMA，且三线斜率均为正
        bullish = (latest[f'ema_{self.ema_fast}'] > latest[f'ema_{self.ema_mid}'] > latest[f'ema_{self.ema_slow}'] and
                  latest['ema_fast_slope'] > 0 and latest['ema_mid_slope'] > 0 and latest['ema_slow_slope'] > 0)
        
        # 空头条件：快速EMA < 中期EMA < 慢速EMA，且三线斜率均为负
        bearish = (latest[f'ema_{self.ema_fast}'] < latest[f'ema_{self.ema_mid}'] < latest[f'ema_{self.ema_slow}'] and
                  latest['ema_fast_slope'] < 0 and latest['ema_mid_slope'] < 0 and latest['ema_slow_slope'] < 0)
        
        if bullish:
            return 'long'
        elif bearish:
            return 'short'
        else:
            return None
    
    def check_volume_condition(self, df):
        """检查成交量条件"""
        if len(df) < 5:
            return False
        
        latest = df.iloc[-1]
        return latest['volume_ratio'] > self.volume_ratio_threshold
    
    def check_breakout_condition(self, df, trend_direction):
        """检查突破条件"""
        if len(df) < 3 or pd.isna(df.iloc[-1]['prev2_high']) or pd.isna(df.iloc[-1]['prev2_low']):
            return False
        
        latest = df.iloc[-1]
        
        if trend_direction == 'long':
            # 多头突破：收盘价突破前2根K线高点
            return latest['close'] > latest['prev2_high']
        elif trend_direction == 'short':
            # 空头突破：收盘价跌破前2根K线低点
            return latest['close'] < latest['prev2_low']
        else:
            return False
    
    def calculate_position_size(self, balance):
        """计算仓位大小"""
        try:
            ticker = self.exchange.fetch_ticker(self.symbol)
            current_price = ticker['last']
            
            # 计算风险金额
            risk_amount = balance * self.risk_per_trade
            
            # 基于止损点数计算仓位
            position_size = risk_amount / self.stop_loss_points
            
            # 转换为合约数量（假设是线性合约）
            contract_size = Decimal(str(position_size)) / Decimal(str(current_price))
            
            # 确保合约数量不超过交易所限制（这里简化处理）
            contract_size = float(contract_size.quantize(Decimal('0.001')))  # 保留3位小数
            
            return contract_size, current_price
        except Exception as e:
            logger.error(f"计算仓位大小失败: {str(e)}")
            return 0.1, 0  # 默认值
    
    def update_daily_stats(self):
        """更新每日交易统计"""
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        
        # 过滤出今天的交易
        today_trades = [t for t in self.trade_history if t['date'].startswith(today)]
        self.trade_count_today = len(today_trades)
        
        # 计算连续亏损次数
        recent_trades = list(reversed(self.trade_history))[:10]  # 查看最近10笔交易
        self.consecutive_losses = 0
        
        for trade in recent_trades:
            if trade['profit_loss'] < 0:
                self.consecutive_losses += 1
            else:
                break
    
    def check_trade_allowed(self):
        """检查是否允许交易"""
        self.update_daily_stats()
        
        # 检查每日交易次数限制
        if self.trade_count_today >= self.max_daily_trades:
            logger.info(f"已达到每日最大交易次数限制: {self.trade_count_today}/{self.max_daily_trades}")
            return False
        
        # 检查连续亏损暂停
        if self.consecutive_losses >= self.pause_after_losses:
            if time.time() - self.last_pause_time < self.pause_hours * 3600:
                logger.info(f"连续亏损暂停中，剩余时间: {(self.pause_hours * 3600 - (time.time() - self.last_pause_time))/3600:.2f}小时")
                return False
            else:
                logger.info("连续亏损暂停时间已过，恢复交易")
                self.last_pause_time = 0
        
        # 检查是否有未平仓的头寸
        if self.current_position is not None:
            logger.info("有未平仓的头寸，不允许开新仓")
            return False
        
        return True
    
    def place_market_order(self, side, quantity):
        """下单"""
        try:
            order = self.exchange.create_market_order(self.symbol, side, quantity)
            logger.info(f"下单成功: {side} {quantity} {self.symbol}, 订单ID: {order['id']}")
            return order
        except Exception as e:
            logger.error(f"下单失败: {str(e)}")
            return None
    
    def close_position(self):
        """平仓"""
        if self.current_position is None:
            return None
        
        try:
            side = 'sell' if self.trade_direction == 'long' else 'buy'
            order = self.exchange.create_market_order(self.symbol, side, abs(self.position_size))
            
            # 计算盈亏
            ticker = self.exchange.fetch_ticker(self.symbol)
            exit_price = ticker['last']
            profit_loss = 0
            
            if self.trade_direction == 'long':
                profit_loss = (exit_price - self.entry_price) * self.position_size
            else:
                profit_loss = (self.entry_price - exit_price) * self.position_size
            
            # 记录交易
            trade_record = {
                'date': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'symbol': self.symbol,
                'direction': self.trade_direction,
                'entry_price': self.entry_price,
                'exit_price': exit_price,
                'quantity': self.position_size,
                'profit_loss': profit_loss,
                'holding_time': (time.time() - self.entry_time) / 3600  # 小时
            }
            
            self.trade_history.append(trade_record)
            self._save_trade_history()
            
            logger.info(f"平仓成功: {side} {abs(self.position_size)} {self.symbol}, 盈亏: {profit_loss:.2f} USDT")
            
            # 更新连续亏损记录
            if profit_loss < 0:
                self.consecutive_losses += 1
                if self.consecutive_losses >= self.pause_after_losses:
                    self.last_pause_time = time.time()
                    logger.info(f"连续亏损{self.consecutive_losses}次，暂停交易{self.pause_hours}小时")
            else:
                self.consecutive_losses = 0
            
            # 重置当前仓位信息
            self.current_position = None
            self.entry_price = None
            self.entry_time = None
            self.position_size = None
            self.trade_direction = None
            
            return trade_record
        except Exception as e:
            logger.error(f"平仓失败: {str(e)}")
            return None
    
    def check_exit_conditions(self, df):
        """检查出场条件"""
        if self.current_position is None:
            return False
        
        ticker = self.exchange.fetch_ticker(self.symbol)
        current_price = ticker['last']
        holding_time = (time.time() - self.entry_time) / 3600  # 小时
        
        # 止盈条件
        if self.trade_direction == 'long':
            profit_points = current_price - self.entry_price
            if profit_points >= self.stop_profit_points:
                logger.info(f"触发止盈条件: {profit_points:.2f}点 >= {self.stop_profit_points}点")
                return True
        else:
            profit_points = self.entry_price - current_price
            if profit_points >= self.stop_profit_points:
                logger.info(f"触发止盈条件: {profit_points:.2f}点 >= {self.stop_profit_points}点")
                return True
        
        # 止损条件
        if self.trade_direction == 'long':
            loss_points = self.entry_price - current_price
            if loss_points >= self.stop_loss_points:
                logger.info(f"触发止损条件: {loss_points:.2f}点 >= {self.stop_loss_points}点")
                return True
        else:
            loss_points = current_price - self.entry_price
            if loss_points >= self.stop_loss_points:
                logger.info(f"触发止损条件: {loss_points:.2f}点 >= {self.stop_loss_points}点")
                return True
        
        # 时间限制条件
        if holding_time > self.max_holding_hours:
            logger.info(f"触发时间限制条件: {holding_time:.2f}小时 > {self.max_holding_hours}小时")
            return True
        
        # EMA交叉反向条件
        if len(df) > max(self.ema_fast, self.ema_mid):
            latest = df.iloc[-1]
            prev = df.iloc[-2]
            
            # 检查快速EMA和中期EMA是否交叉反向
            if self.trade_direction == 'long':
                # 多头：如果快速EMA从上方穿过中期EMA向下
                if prev[f'ema_{self.ema_fast}'] > prev[f'ema_{self.ema_mid}'] and \
                   latest[f'ema_{self.ema_fast}'] <= latest[f'ema_{self.ema_mid}']:
                    logger.info("触发EMA交叉反向条件（多头）")
                    return True
            else:
                # 空头：如果快速EMA从下方穿过中期EMA向上
                if prev[f'ema_{self.ema_fast}'] < prev[f'ema_{self.ema_mid}'] and \
                   latest[f'ema_{self.ema_fast}'] >= latest[f'ema_{self.ema_mid}']:
                    logger.info("触发EMA交叉反向条件（空头）")
                    return True
        
        return False
    
    def execute_strategy(self):
        """执行策略主逻辑"""
        logger.info("开始执行量价共振+短期突破策略")
        
        while True:
            try:
                # 检查是否应该平仓
                if self.current_position is not None:
                    df = self.fetch_klines(limit=50)
                    if not df.empty:
                        df = self.calculate_indicators(df)
                        if self.check_exit_conditions(df):
                            self.close_position()
                    
                    # 休眠一段时间再检查
                    time.sleep(60)  # 每分钟检查一次出场条件
                    continue
                
                # 检查是否允许开仓
                if not self.check_trade_allowed():
                    logger.info("当前不满足交易条件，等待下一个检查周期")
                    time.sleep(300)  # 5分钟后再检查
                    continue
                
                # 获取数据并计算指标
                df = self.fetch_klines(limit=50)
                if df.empty:
                    logger.warning("未能获取有效的K线数据")
                    time.sleep(300)
                    continue
                
                df = self.calculate_indicators(df)
                
                # 检查趋势方向
                trend_direction = self.check_trend_direction(df)
                if trend_direction is None:
                    logger.info("未检测到明确的趋势方向")
                    time.sleep(300)
                    continue
                
                # 检查成交量条件
                if not self.check_volume_condition(df):
                    logger.info("成交量条件不满足")
                    time.sleep(300)
                    continue
                
                # 检查突破条件
                if not self.check_breakout_condition(df, trend_direction):
                    logger.info("突破条件不满足")
                    time.sleep(300)
                    continue
                
                # 计算仓位并开仓
                balance = self.get_account_balance()
                position_size, entry_price = self.calculate_position_size(balance)
                
                if position_size <= 0:
                    logger.warning("计算的仓位大小无效")
                    time.sleep(300)
                    continue
                
                # 开仓
                side = 'buy' if trend_direction == 'long' else 'sell'
                order = self.place_market_order(side, position_size)
                
                if order:
                    # 更新当前仓位信息
                    self.current_position = order
                    self.entry_price = entry_price
                    self.entry_time = time.time()
                    self.position_size = position_size
                    self.trade_direction = trend_direction
                    
                    logger.info(f"开仓成功: {trend_direction} {position_size} {self.symbol}, 入场价: {entry_price}")
                
                # 开仓后等待一段时间
                time.sleep(60)
                
            except Exception as e:
                logger.error(f"策略执行出错: {str(e)}")
                time.sleep(300)

if __name__ == "__main__":
    # 解析命令行参数（从Web界面传递）
    symbol = DEFAULT_SYMBOL
    testnet = False  # 默认使用实盘
    
    # 从命令行参数获取配置
    if len(sys.argv) > 1:
        symbol = sys.argv[1]
    if len(sys.argv) > 2:
        testnet = sys.argv[2].lower() == 'true' or sys.argv[2].lower() == '1'
    
    API_KEY = BINANCE_API_KEY
    API_SECRET = BINANCE_SECRET_KEY
    
    print(f"启动策略 - 交易对: {symbol}, 测试网络: {'是' if testnet else '否'}")
    
    strategy = VolumePriceStrategy(
        api_key=API_KEY,
        api_secret=API_SECRET,
        testnet=testnet
    )
    
    # 修改策略的交易对
    strategy.symbol = symbol
    
    try:
        strategy.execute_strategy()
    except KeyboardInterrupt:
        logger.info("策略执行被用户中断")
        # 尝试平仓
        if strategy.current_position is not None:
            strategy.close_position()