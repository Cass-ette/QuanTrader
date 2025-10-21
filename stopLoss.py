import os
import time
import hashlib
import hmac
import requests
from datetime import datetime

# 从环境变量获取API密钥和密钥
api_key = os.environ.get('BINANCE_API_KEY')
api_secret = os.environ.get('BINANCE_API_SECRET')

# 确保API密钥和密钥已设置
if not api_key or not api_secret:
    print("错误: 未设置API密钥或密钥，请设置环境变量 BINANCE_API_KEY 和 BINANCE_API_SECRET")
    exit(1)

# 币安期货API基础URL
BASE_URL = 'https://fapi.binance.com'

def generate_signature(query_string, secret_key):
    """生成请求签名"""
    return hmac.new(secret_key.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()

def get_position_info(symbol, position_side=None):
    """
    获取指定交易对的持仓信息
    优先返回指定方向的持仓（LONG/SHORT），如果未指定或不存在，则返回该交易对的任一持仓
    """
    timestamp = int(time.time() * 1000)
    query_string = f"timestamp={timestamp}"
    signature = generate_signature(query_string, api_secret)
    
    headers = {'X-MBX-APIKEY': api_key}
    url = f"{BASE_URL}/fapi/v2/positionRisk?{query_string}&signature={signature}"
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        all_positions = response.json()
        
        # 打印所有非零持仓，用于调试
        print("所有非零持仓:")
        non_zero_positions = []
        for pos in all_positions:
            pos_amt = float(pos['positionAmt'])
            if pos_amt != 0:
                non_zero_positions.append(pos)
                print(f"交易对: {pos['symbol']}, 持仓方向: {pos['positionSide']}, 持仓数量: {pos['positionAmt']}")
        
        # 筛选指定交易对的持仓
        symbol_positions = [pos for pos in all_positions if pos['symbol'] == symbol]
        if not symbol_positions:
            print(f"未找到 {symbol} 的持仓信息")
            return None
        
        # 如果指定了持仓方向，优先返回该方向的持仓
        if position_side:
            for pos in symbol_positions:
                if pos['positionSide'] == position_side and float(pos['positionAmt']) != 0:
                    print(f"找到 {symbol} {position_side} 方向持仓")
                    return pos
        
        # 否则返回该交易对的任一非零持仓
        for pos in symbol_positions:
            if float(pos['positionAmt']) != 0:
                print(f"找到 {symbol} 持仓，方向: {pos['positionSide']}")
                return pos
        
        print(f"{symbol} 存在持仓记录，但持仓数量为0")
        return symbol_positions[0]  # 返回持仓数量为0的记录
    
    except Exception as e:
        print(f"获取持仓信息时出错: {e}")
        return None

def place_stop_market_order(symbol, side, quantity, stop_price):
    """
    下市价止损单
    side: BUY 或 SELL
    quantity: 数量
    stop_price: 止损价格
    """
    timestamp = int(time.time() * 1000)
    
    # 构建请求参数
    params = {
        'symbol': symbol,
        'side': side,
        'type': 'STOP_MARKET',
        'quantity': quantity,
        'stopPrice': stop_price,
        'timestamp': timestamp,
        'timeInForce': 'GTC'  # 有效期限：Good Till Canceled
    }
    
    # 构建查询字符串
    query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
    signature = generate_signature(query_string, api_secret)
    
    headers = {'X-MBX-APIKEY': api_key}
    url = f"{BASE_URL}/fapi/v1/order?{query_string}&signature={signature}"
    
    try:
        response = requests.post(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"下单时出错: {e}")
        if hasattr(response, 'json'):
            print(f"错误详情: {response.json()}")
        return None

def set_stop_loss(symbol, position_side=None, stop_percent=1.0):
    """
    为指定交易对设置市价止损
    symbol: 交易对，如 ETHUSDT
    position_side: 持仓方向，LONG 或 SHORT，默认为None（自动检测）
    stop_percent: 止损百分比，默认为1.0%（相对入场价格）
    """
    print(f"正在设置 {symbol} 的市价止损...")
    
    # 获取持仓信息
    position_info = get_position_info(symbol, position_side)
    if not position_info:
        print(f"无法获取 {symbol} 的持仓信息，取消止损设置")
        return False
    
    # 打印持仓信息原始数据，用于调试
    print(f"持仓信息原始数据: {position_info}")
    
    # 获取持仓数量和平均成本
    position_amt = float(position_info['positionAmt'])
    entry_price = float(position_info['entryPrice'])
    actual_position_side = position_info['positionSide']
    
    print(f"持仓数量(positionAmt): {position_amt} (类型: {type(position_amt)})")
    print(f"平均成本(entryPrice): {entry_price}")
    print(f"实际持仓方向: {actual_position_side}")
    
    # 检查是否有持仓
    if position_amt == 0:
        print(f"{symbol} 当前没有持仓，无法设置止损")
        return False
    
    # 根据持仓方向确定止损价格和交易方向
    if actual_position_side == 'LONG' or (position_amt > 0 and actual_position_side == 'BOTH'):
        # 多头持仓，设置卖出止损
        side = 'SELL'
        stop_price = entry_price * (1 - stop_percent / 100)
        quantity = abs(position_amt)
        print(f"检测到多头持仓，将设置卖出止损")
    elif actual_position_side == 'SHORT' or (position_amt < 0 and actual_position_side == 'BOTH'):
        # 空头持仓，设置买入止损
        side = 'BUY'
        stop_price = entry_price * (1 + stop_percent / 100)
        quantity = abs(position_amt)
        print(f"检测到空头持仓，将设置买入止损")
    else:
        print(f"未知的持仓方向: {actual_position_side}")
        return False
    
    print(f"计算的止损价格: {stop_price}, 止损数量: {quantity}, 交易方向: {side}")
    
    # 下单
    order_result = place_stop_market_order(symbol, side, quantity, stop_price)
    if order_result:
        print(f"止损单已成功下单!")
        print(f"订单详情: {order_result}")
        return True
    else:
        print("止损单下单失败")
        return False

# 主程序
if __name__ == "__main__":
    print("注意: 此脚本将为指定交易对设置市价止损单")
    print("当前功能为自动检测持仓并设置市价止损")
    # 当前时间（中国时区 UTC+8）
    print(f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (UTC+8)")
    
    # 保持注释状态，等待用户确认后再执行
    # 设置ETHUSDT的止损，止损百分比为1%（可根据需要调整）
    # set_stop_loss('ETHUSDT', stop_percent=1.0)  # 执行止损设置操作
    
    # 也可以指定持仓方向
    # set_stop_loss('ETHUSDT', position_side='LONG', stop_percent=1.5)  # 只为多头设置1.5%止损