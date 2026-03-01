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
from config import DEFAULT_SYMBOL

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("grid_trading_strategy.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("grid_trading_strategy")

# 配置decimal精度
getcontext().prec = 8

class GridTradingStrategy:
    def __init__(self, api_key=None, api_secret=None, testnet=False, grid_levels=10, grid_range_pct=0.08):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.exchange = self._init_exchange()
        self.symbol = DEFAULT_SYMBOL
        self.timeframe = '1h'  # 1小时K线
        
        # 网格策略参数
        self.grid_range_pct = grid_range_pct  # 初始网格区间百分比
        self.grid_levels = grid_levels  # 网格档位数量
        self.total_grid_funds_pct = 0.5  # 网格占用资金比例（50%）
        self.single_grid_funds_pct = 0.01  # 每档资金比例（1%）
        self.breakout_candles = 3  # 突破确认K线数量
        self.stop_loss_multiplier = 1.5  # 止损倍数
        self.stop_strategy_hours = 12  # 策略暂停时间
        
        # 网格状态
        self.grid_upper = None  # 网格上限
        self.grid_lower = None  # 网格下限
        self.grid_spacing = None  # 网格间距
        self.grid_prices = []  # 网格价格列表
        self.active_orders = {}  # 活跃订单
        self.holdings = {}  # 当前持仓
        self.breakout_detected = False  # 突破标志
        self.strategy_paused = False  # 策略暂停标志
        self.pause_start_time = 0  # 暂停开始时间
        
        # 交易统计
        self.trade_history = []
        self.total_profit = 0
        self.total_trades = 0
        
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
            with open('grid_trading_history.json', 'r', encoding='utf-8') as f:
                self.trade_history = json.load(f)
            logger.info(f"加载交易历史记录，共{len(self.trade_history)}笔交易")
        except FileNotFoundError:
            logger.info("未找到交易历史记录文件，创建新的交易历史")
            self.trade_history = []
    
    def _save_trade_history(self):
        """保存交易历史记录"""
        try:
            with open('grid_trading_history.json', 'w', encoding='utf-8') as f:
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
    
    def calculate_atr(self, df, window=14):
        """计算ATR指标"""
        if df.empty or len(df) < window:
            return 0
        
        df['tr'] = np.maximum(
            df['high'] - df['low'],
            np.maximum(
                np.abs(df['high'] - df['close'].shift(1)),
                np.abs(df['low'] - df['close'].shift(1))
            )
        )
        df['atr'] = df['tr'].rolling(window=window).mean()
        
        return df['atr'].iloc[-1]
    
    def initialize_grid(self):
        """初始化网格"""
        try:
            # 获取最新价格
            ticker = self.exchange.fetch_ticker(self.symbol)
            current_price = ticker['last']
            
            # 获取K线数据计算ATR调整网格范围
            df = self.fetch_klines(limit=50)
            atr = self.calculate_atr(df)
            
            # 根据ATR动态调整网格范围
            if atr > 0:
                # 使用ATR*20作为调整后的区间宽度
                atr_range_pct = min((atr * 20) / current_price, 0.12)  # 最大不超过12%
                self.grid_range_pct = max(atr_range_pct, 0.08)  # 最小不低于8%
                logger.info(f"根据ATR动态调整网格范围: {self.grid_range_pct*100:.2f}%")
            
            # 计算网格上下限
            self.grid_lower = current_price * (1 - self.grid_range_pct)
            self.grid_upper = current_price * (1 + self.grid_range_pct)
            
            # 计算网格间距
            self.grid_spacing = (self.grid_upper - self.grid_lower) / (self.grid_levels - 1)
            
            # 生成网格价格列表
            self.grid_prices = [self.grid_lower + i * self.grid_spacing for i in range(self.grid_levels)]
            
            logger.info(f"网格初始化完成 - 上限: {self.grid_upper:.2f}, 下限: {self.grid_lower:.2f}, 间距: {self.grid_spacing:.2f}")
            logger.info(f"网格价格: {[f'{price:.2f}' for price in self.grid_prices]}")
            
            return True
        except Exception as e:
            logger.error(f"初始化网格失败: {str(e)}")
            return False
    
    def place_limit_order(self, side, price, quantity):
        """下限价单"""
        try:
            order = self.exchange.create_limit_order(self.symbol, side, quantity, price)
            logger.info(f"限价单下单成功: {side} {quantity} {self.symbol} @ {price}, 订单ID: {order['id']}")
            return order
        except Exception as e:
            logger.error(f"限价单下单失败: {str(e)}")
            return None
    
    def cancel_order(self, order_id):
        """取消订单"""
        try:
            self.exchange.cancel_order(order_id, self.symbol)
            logger.info(f"取消订单成功: {order_id}")
            return True
        except Exception as e:
            logger.error(f"取消订单失败: {str(e)}")
            return False
    
    def cancel_all_orders(self):
        """取消所有订单"""
        try:
            self.exchange.cancel_all_orders(self.symbol)
            logger.info("取消所有订单成功")
            self.active_orders.clear()
            return True
        except Exception as e:
            logger.error(f"取消所有订单失败: {str(e)}")
            return False
    
    def close_all_positions(self):
        """平掉所有仓位"""
        try:
            # 获取当前持仓
            positions = self.exchange.fetch_positions([self.symbol])
            
            for position in positions:
                if abs(position['contracts']) > 0:
                    side = 'sell' if position['side'] == 'long' else 'buy'
                    quantity = abs(position['contracts'])
                    order = self.exchange.create_market_order(self.symbol, side, quantity)
                    logger.info(f"平仓成功: {side} {quantity} {self.symbol}")
            
            self.holdings.clear()
            return True
        except Exception as e:
            logger.error(f"平掉所有仓位失败: {str(e)}")
            return False
    
    def calculate_position_size(self, balance):
        """计算每个网格的仓位大小"""
        try:
            # 计算总网格资金
            total_grid_funds = balance * self.total_grid_funds_pct
            
            # 计算每档资金
            single_grid_funds = total_grid_funds / self.grid_levels
            
            # 获取当前价格
            ticker = self.exchange.fetch_ticker(self.symbol)
            current_price = ticker['last']
            
            # 转换为合约数量
            contract_size = Decimal(str(single_grid_funds)) / Decimal(str(current_price))
            
            # 确保合约数量不超过交易所限制（这里简化处理）
            contract_size = float(contract_size.quantize(Decimal('0.001')))  # 保留3位小数
            
            return contract_size
        except Exception as e:
            logger.error(f"计算仓位大小失败: {str(e)}")
            return 0.1  # 默认值
    
    def place_grid_orders(self):
        """根据网格价格下单"""
        try:
            # 获取账户余额
            balance = self.get_account_balance()
            
            # 计算每档仓位大小
            grid_size = self.calculate_position_size(balance)
            
            if grid_size <= 0:
                logger.warning("计算的仓位大小无效")
                return False
            
            # 取消所有现有订单
            self.cancel_all_orders()
            
            # 下买单（第1-9档）
            for i in range(self.grid_levels - 1):
                price = self.grid_prices[i]
                order = self.place_limit_order('buy', price, grid_size)
                if order:
                    self.active_orders[order['id']] = {'side': 'buy', 'price': price, 'quantity': grid_size, 'level': i}
            
            # 下卖单（第2-10档）
            for i in range(1, self.grid_levels):
                price = self.grid_prices[i]
                order = self.place_limit_order('sell', price, grid_size)
                if order:
                    self.active_orders[order['id']] = {'side': 'sell', 'price': price, 'quantity': grid_size, 'level': i}
            
            logger.info(f"网格订单放置完成，每档大小: {grid_size}")
            return True
        except Exception as e:
            logger.error(f"放置网格订单失败: {str(e)}")
            return False
    
    def check_breakout(self, df):
        """检查价格是否突破网格区间"""
        if df.empty or len(df) < self.breakout_candles:
            return None
        
        # 获取最近的K线
        recent_candles = df.iloc[-self.breakout_candles:]
        
        # 检查向上突破
        if all(candle['close'] > self.grid_upper for _, candle in recent_candles.iterrows()):
            logger.info(f"检测到向上突破，连续{self.breakout_candles}根K线收盘价在网格上限之上")
            return 'up'
        
        # 检查向下突破
        if all(candle['close'] < self.grid_lower for _, candle in recent_candles.iterrows()):
            logger.info(f"检测到向下突破，连续{self.breakout_candles}根K线收盘价在网格下限之下")
            return 'down'
        
        return None
    
    def adjust_grid(self, breakout_direction):
        """根据突破方向调整网格"""
        try:
            if breakout_direction == 'up':
                # 向上突破，上移网格
                new_lower = self.grid_upper * 0.92
                new_upper = self.grid_upper * 1.08
            else:  # 'down'
                # 向下突破，下移网格
                new_lower = self.grid_lower * 0.92
                new_upper = self.grid_lower * 1.08
            
            logger.info(f"调整网格 - 新上限: {new_upper:.2f}, 新下限: {new_lower:.2f}")
            
            # 更新网格参数
            self.grid_lower = new_lower
            self.grid_upper = new_upper
            self.grid_spacing = (self.grid_upper - self.grid_lower) / (self.grid_levels - 1)
            self.grid_prices = [self.grid_lower + i * self.grid_spacing for i in range(self.grid_levels)]
            
            # 取消所有订单
            self.cancel_all_orders()
            
            # 清理突破标志
            self.breakout_detected = False
            
            # 重新下单
            return self.place_grid_orders()
        except Exception as e:
            logger.error(f"调整网格失败: {str(e)}")
            return False
    
    def check_stop_loss(self, df):
        """检查止损条件"""
        if df.empty or len(df) < 2:
            return False
        
        # 获取最近的价格
        latest_close = df['close'].iloc[-1]
        previous_close = df['close'].iloc[-2]
        
        # 计算价格变化幅度
        price_change = abs(latest_close - previous_close)
        
        # 检查是否超过止损阈值
        stop_loss_threshold = self.grid_spacing * (self.grid_levels - 1) * self.stop_loss_multiplier
        
        if price_change > stop_loss_threshold:
            logger.warning(f"触发止损条件: 价格变化{price_change:.2f}超过阈值{stop_loss_threshold:.2f}")
            return True
        
        return False
    
    def update_order_status(self):
        """更新订单状态"""
        try:
            # 获取当前所有订单
            open_orders = self.exchange.fetch_open_orders(self.symbol)
            open_order_ids = {order['id'] for order in open_orders}
            
            # 获取已成交订单
            closed_orders = [order_id for order_id in self.active_orders if order_id not in open_order_ids]
            
            for order_id in closed_orders:
                order_info = self.active_orders[order_id]
                logger.info(f"订单已成交: {order_info['side']} @ {order_info['price']}, 数量: {order_info['quantity']}")
                
                # 记录交易
                trade_record = {
                    'date': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'symbol': self.symbol,
                    'side': order_info['side'],
                    'price': order_info['price'],
                    'quantity': order_info['quantity'],
                    'level': order_info['level']
                }
                
                # 更新持仓
                if order_info['side'] == 'buy':
                    # 买入成交，记录持仓
                    self.holdings[order_id] = order_info
                    trade_record['profit_loss'] = 0  # 买入时无盈亏
                else:
                    # 卖出成交，计算盈亏
                    # 寻找对应的买入持仓（简化处理，实际应该按先进先出或其他策略）
                    if self.holdings:
                        buy_order_id, buy_info = next(iter(self.holdings.items()))
                        profit = (order_info['price'] - buy_info['price']) * order_info['quantity']
                        trade_record['profit_loss'] = profit
                        self.total_profit += profit
                        
                        # 移除对应的买入持仓
                        del self.holdings[buy_order_id]
                        logger.info(f"完成一轮网格交易，盈利: {profit:.2f} USDT")
                    else:
                        trade_record['profit_loss'] = 0
                
                # 保存交易记录
                self.trade_history.append(trade_record)
                self._save_trade_history()
                self.total_trades += 1
                
                # 从活跃订单中移除
                del self.active_orders[order_id]
            
            # 如果有订单成交，补充新的订单
            if closed_orders:
                self.place_grid_orders()
                
        except Exception as e:
            logger.error(f"更新订单状态失败: {str(e)}")
    
    def execute_strategy(self):
        """执行策略主逻辑"""
        logger.info("开始执行ETH/USDT网格交易策略")
        
        # 初始化网格
        if not self.initialize_grid():
            logger.error("网格初始化失败，无法启动策略")
            return
        
        # 放置初始网格订单
        if not self.place_grid_orders():
            logger.error("放置初始网格订单失败")
            return
        
        while True:
            try:
                # 检查策略是否暂停
                if self.strategy_paused:
                    if time.time() - self.pause_start_time > self.stop_strategy_hours * 3600:
                        logger.info("策略暂停时间已过，恢复交易")
                        self.strategy_paused = False
                        # 重新初始化网格
                        self.initialize_grid()
                        self.place_grid_orders()
                    else:
                        remaining_time = (self.stop_strategy_hours * 3600 - (time.time() - self.pause_start_time)) / 3600
                        logger.info(f"策略暂停中，剩余时间: {remaining_time:.2f}小时")
                        time.sleep(300)  # 5分钟后再检查
                        continue
                
                # 获取最新K线数据
                df = self.fetch_klines(limit=50)
                if df.empty:
                    logger.warning("未能获取有效的K线数据")
                    time.sleep(60)
                    continue
                
                # 更新订单状态
                self.update_order_status()
                
                # 检查止损条件
                if self.check_stop_loss(df):
                    logger.warning("触发止损，平掉所有仓位并暂停策略")
                    self.close_all_positions()
                    self.cancel_all_orders()
                    self.strategy_paused = True
                    self.pause_start_time = time.time()
                    continue
                
                # 检查突破条件
                if not self.breakout_detected:
                    breakout_direction = self.check_breakout(df)
                    if breakout_direction:
                        self.breakout_detected = True
                        self.adjust_grid(breakout_direction)
                
                # 休眠一段时间
                time.sleep(60)  # 每分钟检查一次
                
            except KeyboardInterrupt:
                logger.info("策略执行被用户中断")
                # 尝试平掉所有仓位
                self.close_all_positions()
                self.cancel_all_orders()
                break
            except Exception as e:
                logger.error(f"策略执行出错: {str(e)}")
                time.sleep(300)

if __name__ == "__main__":
    # 解析命令行参数（从Web界面传递）
    symbol = DEFAULT_SYMBOL
    testnet = False
    grid_levels = 10  # 默认网格档位数量
    grid_range_pct = 0.08  # 默认网格区间百分比
    
    # 从命令行参数获取配置
    if len(sys.argv) > 1:
        symbol = sys.argv[1]
    if len(sys.argv) > 2:
        testnet = sys.argv[2].lower() == 'true' or sys.argv[2].lower() == '1'
    if len(sys.argv) > 3:
        try:
            grid_levels = int(sys.argv[3])
        except ValueError:
            logger.warning(f"无效的网格档位数量: {sys.argv[3]}，使用默认值{grid_levels}")
    if len(sys.argv) > 4:
        try:
            grid_range_pct = float(sys.argv[4]) / 100  # 转换为小数
        except ValueError:
            logger.warning(f"无效的网格区间百分比: {sys.argv[4]}，使用默认值{grid_range_pct*100}%")
    
    from config import BINANCE_API_KEY, BINANCE_SECRET_KEY
    API_KEY = BINANCE_API_KEY
    API_SECRET = BINANCE_SECRET_KEY

    print(f"启动网格交易策略 - 交易对: {symbol}, 测试网络: {'是' if testnet else '否'}")
    print(f"网格参数 - 档位数量: {grid_levels}, 区间百分比: {grid_range_pct*100:.2f}%")
    
    strategy = GridTradingStrategy(
        api_key=API_KEY,
        api_secret=API_SECRET,
        testnet=testnet,
        grid_levels=grid_levels,
        grid_range_pct=grid_range_pct
    )
    
    # 修改策略的交易对
    strategy.symbol = symbol
    
    try:
        strategy.execute_strategy()
    except Exception as e:
        logger.error(f"策略执行异常: {str(e)}")
        # 尝试平掉所有仓位
        if strategy.holdings:
            strategy.close_all_positions()