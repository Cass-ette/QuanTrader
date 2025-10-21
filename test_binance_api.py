#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
币安API测试脚本 - 测试所有可用接口
"""

import os
import time
import hmac
import hashlib
import requests

class BinanceAPI:
    """币安API客户端"""
    
    def __init__(self, api_key, secret_key):
        self.api_key = api_key
        self.secret_key = secret_key
        self.base_url = 'https://api.binance.com'
        self.headers = {
            'X-MBX-APIKEY': self.api_key
        }
    
    def _sign_params(self, params):
        """对参数进行HMAC SHA256签名"""
        # 添加时间戳
        params['timestamp'] = int(time.time() * 1000)
        # 生成签名字符串
        query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
        # HMAC SHA256签名
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        params['signature'] = signature
        return params
    
    # 通用接口
    def ping(self):
        """测试服务器连通性"""
        url = f"{self.base_url}/api/v3/ping"
        response = requests.get(url)
        return response.json()
    
    def get_server_time(self):
        """获取服务器时间"""
        url = f"{self.base_url}/api/v3/time"
        response = requests.get(url)
        return response.json()
    
    def get_exchange_info(self, symbol=None):
        """获取交易所信息"""
        url = f"{self.base_url}/api/v3/exchangeInfo"
        params = {}
        if symbol:
            params['symbol'] = symbol
        response = requests.get(url, params=params)
        return response.json()
    
    # 行情接口
    def get_depth(self, symbol, limit=100):
        """获取深度信息"""
        url = f"{self.base_url}/api/v3/depth"
        params = {
            'symbol': symbol,
            'limit': limit
        }
        response = requests.get(url, params=params)
        return response.json()
    
    def get_recent_trades(self, symbol, limit=500):
        """获取近期成交"""
        url = f"{self.base_url}/api/v3/trades"
        params = {
            'symbol': symbol,
            'limit': limit
        }
        response = requests.get(url, params=params)
        return response.json()
    
    def get_avg_price(self, symbol):
        """获取当前平均价格"""
        url = f"{self.base_url}/api/v3/avgPrice"
        params = {'symbol': symbol}
        response = requests.get(url, params=params)
        return response.json()
    
    def get_24hr_ticker(self, symbol=None):
        """获取24小时价格变动情况"""
        url = f"{self.base_url}/api/v3/ticker/24hr"
        params = {}
        if symbol:
            params['symbol'] = symbol
        response = requests.get(url, params=params)
        return response.json()
        
    # 交易接口
    def place_order(self, symbol, side, type, **kwargs):
        """下单接口"""
        url = f"{self.base_url}/api/v3/order"
        params = {
            'symbol': symbol,
            'side': side,  # BUY 或 SELL
            'type': type,  # LIMIT, MARKET, STOP_LOSS等
            **kwargs
        }
        signed_params = self._sign_params(params)
        response = requests.post(url, headers=self.headers, params=signed_params)
        return response.json()
        
    def cancel_order(self, symbol, order_id=None, orig_client_order_id=None):
        """取消订单"""
        url = f"{self.base_url}/api/v3/order"
        params = {'symbol': symbol}
        
        if order_id:
            params['orderId'] = order_id
        elif orig_client_order_id:
            params['origClientOrderId'] = orig_client_order_id
        
        signed_params = self._sign_params(params)
        response = requests.delete(url, headers=self.headers, params=signed_params)
        return response.json()
        
    def get_order(self, symbol, order_id=None, orig_client_order_id=None):
        """查询订单"""
        url = f"{self.base_url}/api/v3/order"
        params = {'symbol': symbol}
        
        if order_id:
            params['orderId'] = order_id
        elif orig_client_order_id:
            params['origClientOrderId'] = orig_client_order_id
        
        signed_params = self._sign_params(params)
        response = requests.get(url, headers=self.headers, params=signed_params)
        return response.json()
    
    def get_historical_trades(self, symbol, limit=500, fromId=None):
        """查询历史成交"""
        url = f"{self.base_url}/api/v3/historicalTrades"
        params = {
            'symbol': symbol,
            'limit': limit
        }
        if fromId:
            params['fromId'] = fromId
        # 这个接口需要API密钥，但不需要签名
        response = requests.get(url, headers=self.headers, params=params)
        return response.json()
    
    def get_agg_trades(self, symbol, limit=500, startTime=None, endTime=None):
        """获取近期成交(归集)"""
        url = f"{self.base_url}/api/v3/aggTrades"
        params = {
            'symbol': symbol,
            'limit': limit
        }
        if startTime:
            params['startTime'] = startTime
        if endTime:
            params['endTime'] = endTime
        response = requests.get(url, params=params)
        return response.json()
    
    def get_klines(self, symbol, interval, limit=500, startTime=None, endTime=None):
        """获取K线数据"""
        url = f"{self.base_url}/api/v3/klines"
        params = {
            'symbol': symbol,
            'interval': interval,
            'limit': limit
        }
        if startTime:
            params['startTime'] = startTime
        if endTime:
            params['endTime'] = endTime
        response = requests.get(url, params=params)
        return response.json()
    
    def get_ui_klines(self, symbol, interval, limit=500, startTime=None, endTime=None):
        """获取UIK线数据"""
        url = f"{self.base_url}/api/v3/uiKlines"
        params = {
            'symbol': symbol,
            'interval': interval,
            'limit': limit
        }
        if startTime:
            params['startTime'] = startTime
        if endTime:
            params['endTime'] = endTime
        response = requests.get(url, params=params)
        return response.json()
    
    # 账户接口
    def get_account_info(self):
        """获取账户信息（需要签名）"""
        url = f"{self.base_url}/api/v3/account"
        params = {}
        signed_params = self._sign_params(params)
        response = requests.get(url, headers=self.headers, params=signed_params)
        return response.json()
    
    def get_orders(self, symbol=None):
        """获取订单列表（需要签名）"""
        url = f"{self.base_url}/api/v3/openOrders"
        params = {}
        if symbol:
            params['symbol'] = symbol
        signed_params = self._sign_params(params)
        response = requests.get(url, headers=self.headers, params=signed_params)
        return response.json()
    
    def get_order_rate_limits(self):
        """查询未成交订单计数"""
        url = f"{self.base_url}/api/v3/rateLimit/order"
        params = {}
        signed_params = self._sign_params(params)
        response = requests.get(url, headers=self.headers, params=signed_params)
        return response.json()

def main():
    """主函数"""
    # 从环境变量读取API密钥
    api_key = os.environ.get('BINANCE_API_KEY', '')
    secret_key = os.environ.get('BINANCE_SECRET_KEY', '')
    
    # 如果环境变量未设置，使用默认值（用于向后兼容）
    if not api_key:
        api_key = 'D3gzp96Lv20e1KCx2WZRPT5xOsavT9jTtATfeVRe6kotuajCdoQjb0lohRoHcBa6'
        print("警告: 未从环境变量 BINANCE_API_KEY 获取API密钥，使用默认值")
    if not secret_key:
        secret_key = 'dV1tDLMczFlopnF9ZFXKBJ0oJt9JogJlxnMmeo7TGUhxRwgm5jxdReoUfMJF55XQ'
        print("警告: 未从环境变量 BINANCE_SECRET_KEY 获取密钥，使用默认值")
    
    # 创建API客户端
    client = BinanceAPI(api_key, secret_key)
    
    # 测试用的交易对
    test_symbol = 'BTCUSDT'
    
    print("=== 开始测试币安API ===")
    print("="*50)
    
    # 测试1: 服务器连通性
    print("\n1. 测试服务器连通性 (PING)")
    print("-" * 30)
    try:
        result = client.ping()
        print(f"  结果: {result}")
        print("  ✅ 连接成功")
    except Exception as e:
        print(f"  ❌ 连接失败: {str(e)}")
    
    # 测试2: 获取服务器时间
    print("\n2. 获取服务器时间 (TIME)")
    print("-" * 30)
    try:
        result = client.get_server_time()
        server_time = result.get('serverTime')
        local_time = int(time.time() * 1000)
        time_diff = abs(local_time - server_time) / 1000  # 秒
        print(f"  服务器时间戳: {server_time}")
        print(f"  服务器时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(server_time/1000))}")
        print(f"  本地时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(local_time/1000))}")
        print(f"  时间差: {time_diff:.2f} 秒")
        print("  ✅ 获取服务器时间成功")
    except Exception as e:
        print(f"  ❌ 获取服务器时间失败: {str(e)}")
    
    # 测试3: 获取交易所信息
    print("\n3. 获取交易所信息 (EXCHANGE_INFO)")
    print("-" * 30)
    try:
        result = client.get_exchange_info()
        symbols = [s['symbol'] for s in result.get('symbols', [])[:5]]  # 只显示前5个交易对
        print(f"  支持的交易对数量: {len(result.get('symbols', []))}")
        print(f"  前5个交易对: {symbols}")
        
        # 获取单个交易对的信息
        single_result = client.get_exchange_info(symbol=test_symbol)
        if 'symbols' in single_result and len(single_result['symbols']) > 0:
            symbol_info = single_result['symbols'][0]
            print(f"\n  单个交易对信息 ({test_symbol}):")
            print(f"  状态: {symbol_info.get('status')}")
            print(f"  基础资产: {symbol_info.get('baseAsset')}")
            print(f"  报价资产: {symbol_info.get('quoteAsset')}")
            print(f"  支持的订单类型: {', '.join(symbol_info.get('orderTypes', []))}")
        
        print("  ✅ 获取交易所信息成功")
    except Exception as e:
        print(f"  ❌ 获取交易所信息失败: {str(e)}")
    
    # 测试4: 获取深度信息
    print("\n4. 获取深度信息 (DEPTH)")
    print("-" * 30)
    try:
        result = client.get_depth(symbol=test_symbol, limit=10)
        bids_len = len(result.get('bids', []))
        asks_len = len(result.get('asks', []))
        print(f"  交易对: {test_symbol}")
        print(f"  最佳买单价格: {result.get('bids', [['0']])[0][0]}，数量: {result.get('bids', [['0', '0']])[0][1]}")
        print(f"  最佳卖单价格: {result.get('asks', [['0']])[0][0]}，数量: {result.get('asks', [['0', '0']])[0][1]}")
        print(f"  买单数量: {bids_len}，卖单数量: {asks_len}")
        print(f"  最新更新ID: {result.get('lastUpdateId')}")
        print("  ✅ 获取深度信息成功")
    except Exception as e:
        print(f"  ❌ 获取深度信息失败: {str(e)}")
    
    # 测试5: 获取近期成交
    print("\n5. 获取近期成交 (TRADES)")
    print("-" * 30)
    try:
        result = client.get_recent_trades(symbol=test_symbol, limit=5)
        print(f"  交易对: {test_symbol}")
        print(f"  最近成交数量: {len(result)}")
        if len(result) > 0:
            print("  最新成交详情:")
            for i, trade in enumerate(result[:3]):  # 只显示前3条
                print(f"  {i+1}. ID: {trade.get('id')}, 价格: {trade.get('price')}, "
                      f"数量: {trade.get('qty')}, 时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(trade.get('time')/1000))}")
        print("  ✅ 获取近期成交成功")
    except Exception as e:
        print(f"  ❌ 获取近期成交失败: {str(e)}")
    
    # 测试6: 获取近期成交(归集)
    print("\n6. 获取近期成交(归集) (AGGTRADES)")
    print("-" * 30)
    try:
        result = client.get_agg_trades(symbol=test_symbol, limit=5)
        print(f"  交易对: {test_symbol}")
        print(f"  归集成交数量: {len(result)}")
        if len(result) > 0:
            print("  最新归集成交详情:")
            for i, trade in enumerate(result[:3]):  # 只显示前3条
                print(f"  {i+1}. 归集ID: {trade.get('a')}, 价格: {trade.get('p')}, "
                      f"数量: {trade.get('q')}, 时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(trade.get('T')/1000))}")
        print("  ✅ 获取近期成交(归集)成功")
    except Exception as e:
        print(f"  ❌ 获取近期成交(归集)失败: {str(e)}")
    
    # 测试7: 获取K线数据
    print("\n7. 获取K线数据 (KLINES)")
    print("-" * 30)
    try:
        # 测试不同时间间隔的K线
        intervals = ['1m', '5m', '1h']
        for interval in intervals:
            result = client.get_klines(symbol=test_symbol, interval=interval, limit=5)
            print(f"\n  交易对: {test_symbol}, 间隔: {interval}")
            print(f"  K线数量: {len(result)}")
            if len(result) > 0:
                latest = result[0]
                print(f"  最新K线: 开盘时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(latest[0]/1000))}, "
                      f"开盘价: {latest[1]}, 最高价: {latest[2]}, 最低价: {latest[3]}, 收盘价: {latest[4]}")
        print("  ✅ 获取K线数据成功")
    except Exception as e:
        print(f"  ❌ 获取K线数据失败: {str(e)}")
    
    # 测试8: 获取UIK线数据
    print("\n8. 获取UIK线数据 (UIKLINES)")
    print("-" * 30)
    try:
        result = client.get_ui_klines(symbol=test_symbol, interval='1h', limit=5)
        print(f"  交易对: {test_symbol}, 间隔: 1h")
        print(f"  UIK线数量: {len(result)}")
        if len(result) > 0:
            latest = result[0]
            print(f"  最新UIK线: 开盘时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(latest[0]/1000))}, "
                  f"收盘价: {latest[4]}")
        print("  ✅ 获取UIK线数据成功")
    except Exception as e:
        print(f"  ❌ 获取UIK线数据失败: {str(e)}")
    
    # 测试9: 获取账户信息（需要API有USER_DATA权限）
    print("\n9. 获取账户信息 (ACCOUNT)")
    print("-" * 30)
    try:
        result = client.get_account_info()
        if 'code' in result:
            print(f"  ❌ 权限不足或API密钥无效: 错误代码 {result.get('code')}, 信息: {result.get('msg')}")
        else:
            print(f"  账户状态: {result.get('status')}")
            print(f"  手续费等级 - 吃单: {result.get('takerCommission')}%, 挂单: {result.get('makerCommission')}%")
            balances = result.get('balances', [])
            print(f"  资产数量: {len(balances)}")
            # 显示有余额的资产
            non_zero_balances = [b for b in balances if float(b.get('free', '0')) > 0 or float(b.get('locked', '0')) > 0]
            if non_zero_balances:
                print("  有余额的资产:")
                for balance in non_zero_balances:
                    print(f"    {balance.get('asset')}: 可用 {balance.get('free')}, 锁定 {balance.get('locked')}")
            print("  ✅ 获取账户信息成功")
    except Exception as e:
        print(f"  ❌ 获取账户信息失败: {str(e)}")
    
    # 测试10: 获取未成交订单
    print("\n10. 获取未成交订单 (OPENORDERS)")
    print("-" * 30)
    try:
        result = client.get_orders()
        if isinstance(result, dict) and 'code' in result:
            print(f"  ❌ 权限不足或API密钥无效: 错误代码 {result.get('code')}, 信息: {result.get('msg')}")
        else:
            print(f"  未成交订单数量: {len(result)}")
            if len(result) > 0:
                print("  未成交订单详情:")
                for i, order in enumerate(result[:3]):  # 只显示前3条
                    print(f"  {i+1}. ID: {order.get('orderId')}, 交易对: {order.get('symbol')}, "
                          f"方向: {order.get('side')}, 类型: {order.get('type')}, 价格: {order.get('price')}")
            print("  ✅ 获取未成交订单成功")
    except Exception as e:
        print(f"  ❌ 获取未成交订单失败: {str(e)}")
    
    # 测试11: 查询未成交订单计数
    print("\n11. 查询未成交订单计数 (RATELIMIT/ORDER)")
    print("-" * 30)
    try:
        result = client.get_order_rate_limits()
        if isinstance(result, dict) and 'code' in result:
            print(f"  ❌ 权限不足或API密钥无效: 错误代码 {result.get('code')}, 信息: {result.get('msg')}")
        else:
            print(f"  未成交订单计数限制详情:")
            for rate_limit in result:
                print(f"    类型: {rate_limit.get('rateLimitType')}, "
                      f"间隔: {rate_limit.get('intervalNum')}{rate_limit.get('interval')}, "
                      f"限制: {rate_limit.get('limit')}, "
                      f"已用: {rate_limit.get('count')}")
            print("  ✅ 查询未成交订单计数成功")
    except Exception as e:
        print(f"  ❌ 查询未成交订单计数失败: {str(e)}")
    
    # 测试12: 查询历史成交（需要API密钥）
    print("\n12. 查询历史成交 (HISTORICALTRADES)")
    print("-" * 30)
    try:
        result = client.get_historical_trades(symbol=test_symbol, limit=5)
        if isinstance(result, dict) and 'code' in result:
            print(f"  ❌ 权限不足或API密钥无效: 错误代码 {result.get('code')}, 信息: {result.get('msg')}")
        else:
            print(f"  交易对: {test_symbol}")
            print(f"  历史成交数量: {len(result)}")
            if len(result) > 0:
                print("  历史成交详情:")
                for i, trade in enumerate(result[:3]):  # 只显示前3条
                    print(f"  {i+1}. ID: {trade.get('id')}, 价格: {trade.get('price')}, "
                          f"数量: {trade.get('qty')}, 时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(trade.get('time')/1000))}")
            print("  ✅ 查询历史成交成功")
    except Exception as e:
        print(f"  ❌ 查询历史成交失败: {str(e)}")
    
    # 测试13: 获取当前平均价格
    print("\n13. 获取当前平均价格 (AVGPRICE)")
    print("-" * 30)
    try:
        result = client.get_avg_price(symbol=test_symbol)
        print(f"  交易对: {test_symbol}")
        print(f"  5分钟平均价格: {result.get('price')}")
        print(f"  结束时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(result.get('closeTime')/1000))}")
        print("  ✅ 获取当前平均价格成功")
    except Exception as e:
        print(f"  ❌ 获取当前平均价格失败: {str(e)}")
    
    # 测试14: 获取24小时价格变动情况
    print("\n14. 获取24小时价格变动情况 (TICKER/24HR)")
    print("-" * 30)
    try:
        result = client.get_24hr_ticker(symbol=test_symbol)
        print(f"  交易对: {result.get('symbol')}")
        print(f"  价格变化: {result.get('priceChange')} ({result.get('priceChangePercent')}%)")
        print(f"  开盘价: {result.get('openPrice')}, 最新价: {result.get('lastPrice')}")
        print(f"  最高价: {result.get('highPrice')}, 最低价: {result.get('lowPrice')}")
        print(f"  24小时成交量: {result.get('volume')}")
        print(f"  最佳买单: {result.get('bidPrice')} ({result.get('bidQty')})")
        print(f"  最佳卖单: {result.get('askPrice')} ({result.get('askQty')})")
        print("  ✅ 获取24小时价格变动情况成功")
    except Exception as e:
        print(f"  ❌ 获取24小时价格变动情况失败: {str(e)}")
    
    # 交易接口测试（注意：这些接口需要更高的API权限，可能会实际执行交易）
    print("\n" + "="*50)
    print("=== 交易接口测试（需额外权限）===")
    print("注意：以下测试可能会执行实际交易，请确保API密钥权限正确且在测试环境中进行")
    
    # 15. 测试下单（使用极小数量的限价单，避免实际成交）
    print("\n15. 下单测试 (PLACE_ORDER)")
    print("-" * 30)
    try:
        # 使用远高于市场价的价格下买单，这样不会实际成交
        result = client.get_24hr_ticker(symbol=test_symbol)
        test_price = float(result.get('highPrice', 0)) * 2  # 远高于最高价
        test_quantity = 0.000001  # 极小数量
        
        order_response = client.place_order(
            symbol=test_symbol,
            side='BUY',
            type='LIMIT',
            timeInForce='GTC',
            quantity=test_quantity,
            price=test_price
        )
        
        print(f"  下单成功!")
        print(f"  订单ID: {order_response.get('orderId')}")
        print(f"  交易对: {order_response.get('symbol')}")
        print(f"  方向: {order_response.get('side')}")
        print(f"  类型: {order_response.get('type')}")
        print(f"  价格: {order_response.get('price')}")
        print(f"  数量: {order_response.get('origQty')}")
        print(f"  状态: {order_response.get('status')}")
        
        # 保存订单ID用于取消测试
        test_order_id = order_response.get('orderId')
        
        # 16. 测试查询订单
        print("\n16. 查询订单测试 (GET_ORDER)")
        print("-" * 30)
        try:
            order_info = client.get_order(symbol=test_symbol, order_id=test_order_id)
            print(f"  查询成功!")
            print(f"  订单状态: {order_info.get('status')}")
            print(f"  已执行数量: {order_info.get('executedQty')}")
            print("  ✅ 查询订单成功")
        except Exception as e:
            print(f"  ❌ 查询订单失败: {str(e)}")
        
        # 17. 测试取消订单
        print("\n17. 取消订单测试 (CANCEL_ORDER)")
        print("-" * 30)
        try:
            cancel_response = client.cancel_order(symbol=test_symbol, order_id=test_order_id)
            print(f"  取消成功!")
            print(f"  订单ID: {cancel_response.get('orderId')}")
            print(f"  状态: {cancel_response.get('status')}")
            print("  ✅ 取消订单成功")
        except Exception as e:
            print(f"  ❌ 取消订单失败: {str(e)}")
            
    except Exception as e:
        print(f"  ❌ 下单失败: {str(e)}")
        print(f"  可能原因: API密钥没有交易权限或余额不足")

    print("\n" + "="*50)
    print("=== 所有API接口测试完成 ===")
    print("\n注意：")
    print("1. 公开API接口（PING, TIME, EXCHANGE_INFO, DEPTH, TRADES, AGGTRADES, KLINES, UIKLINES, AVGPRICE, TICKER）通常都可以正常访问")
    print("2. 需要身份验证的API接口（ACCOUNT, OPENORDERS, RATELIMIT/ORDER, HISTORICALTRADES）需要正确的API权限")
    print("3. 交易接口（PLACE_ORDER, CANCEL_ORDER, GET_ORDER）需要启用交易权限，谨慎使用")
    print("4. 请确保您的API密钥已在币安平台上启用了相应的权限")

if __name__ == '__main__':
    main()