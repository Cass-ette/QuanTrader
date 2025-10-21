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

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("moving_average_144_strategy.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("moving_average_144_strategy")

# 配置decimal精度
getcontext().prec = 8

class MovingAverage144Strategy:
    def __init__(self, api_key=None, api_secret=None, testnet=False):
        # 优先使用传入的API密钥，如果没有则从环境变量读取
        self.api_key = api_key or os.environ.get('BINANCE_API_KEY', 'D3gzp96Lv20e1KCx2WZRPT5xOsavT9jTtATfeVRe6kotuajCdoQjb0lohRoHcBa6')
        self.api_secret = api_secret or os.environ.get('BINANCE_SECRET_KEY', 'dV1tDLMczFlopnF9ZFXKBJ0oJt9JogJlxnMmeo7TGUhxRwgm5jxdReoUfMJF55XQ')
        self.testnet = testnet
        self.exchange = self._init_exchange()
        self.symbol = 'ETHUSDT'  # 默认交易对，可以在初始化后修改
        self.timeframe = '5m'  # 五分钟K线
        
        # 策略参数
        self.ma_period = 144  # 144日均线
        self.open_threshold_pct = 1.0  # 开仓阈值百分比（1%）
        self.risk_per_trade = 0.01  # 单笔交易风险（1%）
        self.max_daily_trades = 5  # 每日最大交易次数
        
        # 交易状态
        self.current_position = None
        self.entry_price = None
        self.entry_time = None
        self.position_size = None
        
        # 交易统计
        self.trade_history = []
        self.trade_count_today = 0
        
        # 加载历史交易记录
        self._load_trade_history()
        
    def _init_exchange(self):
        """初始化交易所连接，避免自动加载市场数据触发现货API"""
        try:
            # 关键配置：禁用自动加载市场数据
            config = {
                'apiKey': self.api_key,
                'secret': self.api_secret,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'future',  # 强制使用期货API
                    'adjustForTimeDifference': True,
                    'fetchMarkets': False  # 禁用自动加载市场数据
                }
            }
            
            # 创建交易所实例
            exchange = ccxt.binance(config)
            
            # 确保options正确设置
            if not hasattr(exchange, 'options'):
                exchange.options = {}
            exchange.options['defaultType'] = 'future'
            exchange.options['fetchMarkets'] = False  # 再次确认禁用自动加载
            
            # 手动设置市场数据，避免调用load_markets
            # 确保markets是一个字典
            if not hasattr(exchange, 'markets') or exchange.markets is None:
                exchange.markets = {}
            
            # 添加默认交易对的市场数据
            default_symbol = 'BTCUSDT'  # 使用默认交易对进行初始化
            exchange.markets[default_symbol] = {
                'symbol': default_symbol,
                'id': default_symbol,
                'base': 'BTC',  # 基础货币
                'quote': 'USDT',  # 报价货币
                'type': 'future',
                'spot': False,
                'future': True,
                'contract': True
            }
            
            # 设置markets_loaded标志为True，防止ccxt自动调用load_markets
            if not hasattr(exchange, 'markets_loaded'):
                exchange.markets_loaded = True
            else:
                exchange.markets_loaded = True
            
            # 设置测试网模式
            if self.testnet:
                exchange.set_sandbox_mode(True)
                logger.info("使用测试网络模式")
            else:
                logger.info("[重要提示]：本程序处于实际交易模式，将执行真实交易操作！")
            
            # 记录初始化信息
            logger.info(f"交易所初始化完成，使用期货模式: future")
            logger.info(f"手动设置默认市场数据，避免自动加载触发现货API")
            
            # 验证连接 - 使用直接的HTTP请求验证期货API连接
            try:
                # 直接使用期货API端点验证连接
                import requests
                import time
                import hmac
                import hashlib
                
                timestamp = int(time.time() * 1000)
                params = {'timestamp': timestamp, 'recvWindow': 5000}
                query_string = '&'.join([f"{k}={v}" for k, v in sorted(params.items())])
                signature = hmac.new(
                    self.api_secret.encode('utf-8'),
                    query_string.encode('utf-8'),
                    hashlib.sha256
                ).hexdigest()
                
                base_url = 'https://testnet.binancefuture.com' if self.testnet else 'https://fapi.binance.com'
                url = f'{base_url}/fapi/v1/ping'
                headers = {'X-MBX-APIKEY': self.api_key}
                params['signature'] = signature
                
                response = requests.get(url, headers=headers, params=params, timeout=10)
                if response.status_code == 200:
                    logger.info(f"期货API连接验证成功")
                else:
                    logger.warning(f"期货API连接验证返回非200状态码: {response.status_code}")
            except Exception as verify_error:
                logger.warning(f"期货API连接验证异常: {str(verify_error)}")
            
            return exchange
        except Exception as e:
            logger.error(f"初始化交易所失败: {str(e)}")
            import traceback
            logger.error(f"错误详情: {traceback.format_exc()}")
            raise
    
    def _load_trade_history(self):
        """加载交易历史记录"""
        try:
            with open('ma144_trade_history.json', 'r', encoding='utf-8') as f:
                self.trade_history = json.load(f)
            logger.info(f"加载交易历史记录，共{len(self.trade_history)}笔交易")
        except FileNotFoundError:
            logger.info("未找到交易历史记录文件，创建新的交易历史")
            self.trade_history = []
    
    def _save_trade_history(self):
        """保存交易历史记录"""
        try:
            with open('ma144_trade_history.json', 'w', encoding='utf-8') as f:
                json.dump(self.trade_history, f, indent=2, ensure_ascii=False)
            logger.info(f"保存交易历史记录，共{len(self.trade_history)}笔交易")
        except Exception as e:
            logger.error(f"保存交易历史记录失败: {str(e)}")
    
    def get_account_balance(self):
        """获取期货账户余额，避免使用现货API"""
        try:
            # 使用ccxt的fetch_balance方法，但明确指定type为'future'
            try:
                # 直接使用fetch_balance并指定type参数
                account = self.exchange.fetch_balance({'type': 'future'})
                
                # 安全地访问余额数据
                if 'total' in account and 'USDT' in account['total']:
                    balance = account['total']['USDT']
                    logger.info(f"成功获取USDT期货余额: {balance}")
                    return float(balance)
                elif 'USDT' in account:
                    # 处理ccxt可能的不同返回格式
                    if isinstance(account['USDT'], dict) and 'total' in account['USDT']:
                        balance = account['USDT']['total']
                        logger.info(f"成功获取USDT期货余额: {balance}")
                        return float(balance)
            except Exception as ccxt_error:
                logger.warning(f"CCXT获取余额失败，尝试直接期货API: {str(ccxt_error)}")
                
                # 如果ccxt方法失败，使用原始期货API请求
                timestamp = int(time.time() * 1000)
                params = {'timestamp': timestamp, 'recvWindow': 5000}
                query_string = '&'.join([f"{k}={v}" for k, v in sorted(params.items())])
                signature = hmac.new(
                    self.api_secret.encode('utf-8'),
                    query_string.encode('utf-8'),
                    hashlib.sha256
                ).hexdigest()
                
                # 根据测试网络模式选择正确的期货API端点
                base_url = 'https://testnet.binancefuture.com' if self.testnet else 'https://fapi.binance.com'
                url = f'{base_url}/fapi/v2/balance'
                headers = {'X-MBX-APIKEY': self.api_key}
                params['signature'] = signature
                
                # 添加超时和错误处理
                response = requests.get(url, headers=headers, params=params, timeout=15)
                
                if response.status_code == 200:
                    data = response.json()
                    for asset in data:
                        if asset.get('asset') == 'USDT':
                            balance = float(asset.get('availableBalance', 0))
                            logger.info(f"成功通过原始API获取USDT期货余额: {balance}")
                            return balance
                else:
                    logger.error(f"期货API请求失败，状态码: {response.status_code}, 响应: {response.text}")
            
            logger.warning("未能获取到有效的余额数据")
            return 0.0
        except Exception as e:
            logger.error(f"获取账户余额时发生异常: {str(e)}")
            import traceback
            logger.error(f"错误详情: {traceback.format_exc()}")
            # 出错时返回一个合理的默认值用于测试
            return 1000.0
    
    def fetch_klines(self, limit=200):
        """获取K线数据，直接使用期货API，添加重试机制"""
        max_retries = 3
        retry_delay = 2  # 秒
        
        for attempt in range(max_retries):
            try:
                # 确保市场数据已手动设置
                future_symbol = self.symbol.replace('/', '')  # 使用BTCUSDT格式
                
                # 确保我们手动设置的市场数据存在
                if future_symbol not in self.exchange.markets:
                    logger.warning(f"交易对{future_symbol}未在手动设置的市场数据中，正在添加")
                    # 动态添加当前需要的交易对市场数据
                    if not hasattr(self.exchange, 'markets') or self.exchange.markets is None:
                        self.exchange.markets = {}
                    self.exchange.markets[future_symbol] = {
                        'symbol': future_symbol,
                        'id': future_symbol,
                        'base': future_symbol[:-4] if len(future_symbol) > 4 else future_symbol[:-3],
                        'quote': future_symbol[-4:] if len(future_symbol) > 4 else future_symbol[-3:],
                        'type': 'future',
                        'spot': False,
                        'future': True,
                        'contract': True
                    }
                
                logger.info(f"尝试获取期货K线(尝试{attempt+1}/{max_retries}): 符号={future_symbol}, 时间周期={self.timeframe}, 数量={limit}")
                
                # 构建直接的HTTP请求来获取K线数据
                import requests
                import time
                import hmac
                import hashlib
                
                # 准备API请求参数
                timestamp = int(time.time() * 1000)
                params = {
                    'symbol': future_symbol,
                    'interval': self.timeframe,
                    'limit': limit,
                    'timestamp': timestamp,
                    'recvWindow': 10000  # 增加接收窗口
                }
                
                # 生成签名
                query_string = '&'.join([f"{k}={v}" for k, v in sorted(params.items())])
                signature = hmac.new(
                    self.api_secret.encode('utf-8'),
                    query_string.encode('utf-8'),
                    hashlib.sha256
                ).hexdigest()
                
                # 构建完整URL
                base_url = 'https://testnet.binancefuture.com' if self.testnet else 'https://fapi.binance.com'
                url = f'{base_url}/fapi/v1/klines'
                headers = {'X-MBX-APIKEY': self.api_key}
                params['signature'] = signature
                
                # 发送请求，添加超时和错误处理
                try:
                    # 添加会话重用和连接池
                    session = requests.Session()
                    session.mount('https://', requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=100, max_retries=2))
                    
                    logger.info(f"发送期货API请求: {base_url}/fapi/v1/klines (带签名)")
                    response = session.get(url, headers=headers, params=params, timeout=20)
                    session.close()
                except requests.exceptions.RequestException as req_error:
                    logger.error(f"网络请求异常: {str(req_error)}")
                    if attempt < max_retries - 1:
                        logger.info(f"{retry_delay}秒后重试...")
                        time.sleep(retry_delay)
                        continue
                    raise
                
                # 处理响应
                if response.status_code == 200:
                    try:
                        klines_data = response.json()
                        if not klines_data:
                            logger.warning("未能获取有效的K线数据，API返回空")
                            return pd.DataFrame()
                        
                        # 转换为DataFrame格式
                        df = pd.DataFrame(klines_data, columns=[
                            'timestamp', 'open', 'high', 'low', 'close', 'volume',
                            'close_time', 'quote_volume', 'trades', 'taker_base_volume',
                            'taker_quote_volume', 'ignore'
                        ])
                        
                        # 只保留需要的列
                        df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
                        
                        # 转换数据类型
                        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                        numeric_columns = ['open', 'high', 'low', 'close', 'volume']
                        df[numeric_columns] = df[numeric_columns].astype(float)
                        
                        df.set_index('timestamp', inplace=True)
                        logger.info(f"成功通过直接期货API获取{len(df)}条K线数据")
                        return df
                    except Exception as json_error:
                        logger.error(f"处理API响应数据异常: {str(json_error)}")
                        if attempt < max_retries - 1:
                            logger.info(f"{retry_delay}秒后重试...")
                            time.sleep(retry_delay)
                            continue
                else:
                    logger.error(f"期货API请求失败，状态码: {response.status_code}")
                    logger.error(f"响应内容: {response.text}")
                    
                    # 特定错误码处理
                    if response.status_code == 401:
                        logger.error("API认证失败，请检查API密钥和密钥")
                        return pd.DataFrame()
                    elif response.status_code == 429:
                        logger.warning("API请求频率限制，增加延迟后重试")
                        retry_delay *= 2
                    elif response.status_code == 418:
                        logger.warning("IP被暂时禁止，稍后再试")
                        return pd.DataFrame()
                    
                    if attempt < max_retries - 1:
                        logger.info(f"{retry_delay}秒后重试...")
                        time.sleep(retry_delay)
                        continue
                        
            except Exception as e:
                logger.error(f"获取K线数据异常(尝试{attempt+1}): {str(e)}")
                import traceback
                logger.error(f"错误详情: {traceback.format_exc()}")
                
                if attempt < max_retries - 1:
                    logger.info(f"{retry_delay}秒后重试...")
                    time.sleep(retry_delay)
                    continue
        
        # 所有重试都失败
        logger.error(f"在{max_retries}次尝试后仍未能获取K线数据")
        return pd.DataFrame()
    
    def calculate_indicators(self, df):
        """计算技术指标"""
        if df.empty:
            return df
        
        # 计算144日均线
        df[f'ma_{self.ma_period}'] = df['close'].rolling(window=self.ma_period).mean()
        
        # 计算价格与均线的百分比差
        df['price_ma_diff_pct'] = ((df['close'] - df[f'ma_{self.ma_period}']) / df[f'ma_{self.ma_period}']) * 100
        
        # 记录最近的几个K线数据和均线值，帮助调试
        if len(df) >= self.ma_period:
            recent_data = df.tail(5)
            logger.info(f"最近5个K线数据和均线值:")
            for idx, row in recent_data.iterrows():
                ma_value = row[f'ma_{self.ma_period}'] if pd.notna(row[f'ma_{self.ma_period}']) else "N/A"
                logger.info(f"时间: {idx}, 收盘价: {row['close']:.2f}, {self.ma_period}日均线: {ma_value}")
        
        return df
    
    def update_daily_stats(self):
        """更新每日交易统计"""
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        
        # 过滤出今天的交易
        today_trades = [t for t in self.trade_history if t['date'].startswith(today)]
        self.trade_count_today = len(today_trades)
        
        logger.info(f"今日交易次数: {self.trade_count_today}/{self.max_daily_trades}")
    
    def check_trade_allowed(self):
        """检查是否允许交易"""
        self.update_daily_stats()
        
        # 检查每日交易次数限制
        if self.trade_count_today >= self.max_daily_trades:
            logger.info(f"已达到每日最大交易次数限制: {self.trade_count_today}/{self.max_daily_trades}")
            return False
        
        # 检查是否有未平仓的头寸
        if self.current_position is not None:
            logger.info("有未平仓的头寸，不允许开新仓")
            return False
        
        return True
    
    def calculate_position_size(self, balance):
        """计算仓位大小"""
        try:
            ticker = self.exchange.fetch_ticker(self.symbol)
            current_price = ticker['last']
            
            # 计算风险金额
            risk_amount = balance * self.risk_per_trade
            
            # 基于风险金额计算仓位
            position_size = risk_amount / current_price
            
            # 转换为合约数量
            contract_size = Decimal(str(position_size))
            
            # 确保合约数量不超过交易所限制（这里简化处理）
            contract_size = float(contract_size.quantize(Decimal('0.001')))  # 保留3位小数
            
            return contract_size, current_price
        except Exception as e:
            logger.error(f"计算仓位大小失败: {str(e)}")
            return 0.1, 0  # 默认值
    
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
            # 平仓（多单平仓为卖出）
            order = self.exchange.create_market_order(self.symbol, 'sell', abs(self.position_size))
            
            # 计算盈亏
            ticker = self.exchange.fetch_ticker(self.symbol)
            exit_price = ticker['last']
            profit_loss = (exit_price - self.entry_price) * self.position_size
            
            # 记录交易
            trade_record = {
                'date': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'symbol': self.symbol,
                'direction': 'long',
                'entry_price': self.entry_price,
                'exit_price': exit_price,
                'quantity': self.position_size,
                'profit_loss': profit_loss,
                'holding_time': (time.time() - self.entry_time) / 60  # 分钟
            }
            
            self.trade_history.append(trade_record)
            self._save_trade_history()
            
            logger.info(f"平仓成功: sell {abs(self.position_size)} {self.symbol}, 盈亏: {profit_loss:.2f} USDT")
            
            # 重置当前仓位信息
            self.current_position = None
            self.entry_price = None
            self.entry_time = None
            self.position_size = None
            
            return trade_record
        except Exception as e:
            logger.error(f"平仓失败: {str(e)}")
            return None
    
    def check_entry_condition(self, df):
        """检查开仓条件：价格大于均线上方1%"""
        if df.empty or len(df) < self.ma_period:
            logger.info(f"K线数据不足: {len(df)}条，需要至少{self.ma_period}条计算均线")
            return False
        
        latest = df.iloc[-1]
        
        # 确保均线值有效
        if pd.isna(latest[f'ma_{self.ma_period}']):
            logger.warning(f"{self.ma_period}日均线值无效")
            return False
        
        # 详细记录价格和均线信息
        current_price = latest['close']
        ma_value = latest[f'ma_{self.ma_period}']
        price_ma_diff_pct = latest['price_ma_diff_pct']
        
        logger.info(f"价格: {current_price:.2f}, {self.ma_period}日均线: {ma_value:.2f}, 差值: {price_ma_diff_pct:.2f}%")
        logger.info(f"开仓阈值: {self.open_threshold_pct}%")
        
        # 检查价格是否大于均线上方1%
        is_above_threshold = price_ma_diff_pct > self.open_threshold_pct
        
        if is_above_threshold:
            logger.info(f"触发开仓条件: 价格高于{self.ma_period}均线上方{price_ma_diff_pct:.2f}%")
        else:
            logger.info(f"未触发开仓条件: 价格仅高于均线{price_ma_diff_pct:.2f}%，低于阈值{self.open_threshold_pct}%")
        
        return is_above_threshold
    
    def check_exit_condition(self, df):
        """检查平仓条件：价格小于均线"""
        if df.empty or len(df) < self.ma_period or self.current_position is None:
            return False
        
        latest = df.iloc[-1]
        
        # 确保均线值有效
        if pd.isna(latest[f'ma_{self.ma_period}']):
            return False
        
        # 检查价格是否小于均线
        is_below_ma = latest['price_ma_diff_pct'] < 0
        
        if is_below_ma:
            logger.info(f"触发平仓条件: 价格低于{self.ma_period}均线{abs(latest['price_ma_diff_pct']):.2f}%")
        
        return is_below_ma
    
    def execute_strategy(self):
        """执行策略主逻辑"""
        logger.info(f"开始执行5分钟周期144日均线策略")
        logger.info(f"开仓条件: 价格大于{self.ma_period}均线上方{self.open_threshold_pct}%")
        logger.info(f"平仓条件: 价格小于{self.ma_period}均线")
        logger.info(f"交易环境: {'测试网' if self.testnet else '实盘'}")
        
        while True:
            try:
                # 首先验证交易所连接状态
                if self.exchange is None:
                    logger.error("交易所连接未初始化，尝试重新连接")
                    self.exchange = self._init_exchange()
                    time.sleep(10)
                    continue
                
                # 获取K线数据并计算指标
                df = self.fetch_klines(limit=self.ma_period * 2)  # 获取足够的数据计算均线
                if df.empty:
                    logger.warning("未能获取有效的K线数据")
                    time.sleep(60)
                    continue
                
                df = self.calculate_indicators(df)
                if df.empty:
                    logger.warning("计算指标失败")
                    time.sleep(60)
                    continue
                
                # 检查是否应该平仓
                if self.current_position is not None:
                    logger.info("检查平仓条件...")
                    if self.check_exit_condition(df):
                        self.close_position()
                    
                    # 休眠一段时间再检查
                    time.sleep(30)  # 每30秒检查一次出场条件
                    continue
                
                # 检查是否允许开仓
                if not self.check_trade_allowed():
                    logger.info("当前不满足交易条件，等待下一个检查周期")
                    time.sleep(60)  # 1分钟后再检查
                    continue
                
                # 检查开仓条件
                if self.check_entry_condition(df):
                    # 计算仓位并开仓
                    balance = self.get_account_balance()
                    if balance <= 0:
                        logger.warning(f"账户余额不足: {balance} USDT")
                        time.sleep(60)
                        continue
                    
                    position_size, entry_price = self.calculate_position_size(balance)
                    
                    if position_size <= 0:
                        logger.warning("计算的仓位大小无效")
                        time.sleep(60)
                        continue
                    
                    # 开仓
                    order = self.place_market_order('buy', position_size)
                    
                    if order:
                        # 更新当前仓位信息
                        self.current_position = order
                        self.entry_price = entry_price
                        self.entry_time = time.time()
                        self.position_size = position_size
                        
                        logger.info(f"开仓成功: long {position_size} {self.symbol}, 入场价: {entry_price}")
                    else:
                        logger.error("开仓失败，订单未创建")
                
                # 休眠一段时间
                time.sleep(30)  # 每30秒检查一次
                
            except KeyboardInterrupt:
                logger.info("策略执行被用户中断")
                # 尝试平仓
                if self.current_position is not None:
                    self.close_position()
                break
            except ccxt.BaseError as e:
                logger.error(f"交易所API错误: {str(e)}")
                # 检查是否是认证问题
                if 'authentication' in str(e).lower() or 'api key' in str(e).lower():
                    logger.error("API密钥认证失败，请检查密钥配置")
                # 检查是否是端点问题
                if 'endpoint' in str(e).lower() or 'sapi/v1/capital/config/getall' in str(e):
                    logger.error("检测到API端点错误，可能是交易所类型配置不正确")
                    # 尝试重新初始化交易所连接
                    self.exchange = self._init_exchange()
                time.sleep(60)
            except Exception as e:
                logger.error(f"策略执行出错: {str(e)}")
                import traceback
                logger.error(f"错误详情: {traceback.format_exc()}")
                time.sleep(60)

if __name__ == "__main__":
    # 解析命令行参数（从Web界面传递）
    symbol = 'ETHUSDT'  # 默认交易对
    testnet = False  # 默认使用实盘
    api_key = None
    api_secret = None
    
    # 从命令行参数获取配置
    if len(sys.argv) > 1:
        symbol = sys.argv[1]
    if len(sys.argv) > 2:
        testnet = sys.argv[2].lower() == 'true' or sys.argv[2].lower() == '1'
    if len(sys.argv) > 4:  # 如果传入了API密钥和密钥
        api_key = sys.argv[3]
        api_secret = sys.argv[4]
    
    # 打印启动信息
    print(f"启动5分钟周期144日均线策略 - 交易对: {symbol}, 测试网络: {'是' if testnet else '否'}")
    print(f"API密钥配置: {'已提供' if api_key else '使用环境变量或默认值'}")
    
    # 初始化策略实例
    strategy = MovingAverage144Strategy(
        api_key=api_key,  # 可能为None，此时会在构造函数中从环境变量读取
        api_secret=api_secret,
        testnet=testnet
    )
    
    # 修改策略的交易对
    strategy.symbol = symbol
    
    try:
        strategy.execute_strategy()
    except Exception as e:
        logger.error(f"策略执行异常: {str(e)}")
        # 尝试平仓
        if hasattr(strategy, 'current_position') and strategy.current_position is not None:
            strategy.close_position()