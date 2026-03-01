import time
import requests
from datetime import datetime
from config import (
    BINANCE_API_KEY, BINANCE_SECRET_KEY,
    BINANCE_FUTURES_BASE_URL, DEFAULT_TIMEOUT, validate_binance_config
)
from binance_client import get_signature, get_headers


validate_binance_config()


def get_position_info(symbol, position_side=None):
    """获取指定交易对的持仓信息"""
    timestamp = int(time.time() * 1000)
    query_string = f"timestamp={timestamp}"
    signature = get_signature(query_string)

    headers = get_headers()
    url = f"{BINANCE_FUTURES_BASE_URL}/fapi/v2/positionRisk?{query_string}&signature={signature}"

    try:
        response = requests.get(url, headers=headers, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        all_positions = response.json()

        print("所有非零持仓:")
        for pos in all_positions:
            if float(pos['positionAmt']) != 0:
                print(f"交易对: {pos['symbol']}, 持仓方向: {pos['positionSide']}, 持仓数量: {pos['positionAmt']}")

        symbol_positions = [pos for pos in all_positions if pos['symbol'] == symbol]
        if not symbol_positions:
            print(f"未找到 {symbol} 的持仓信息")
            return None

        if position_side:
            for pos in symbol_positions:
                if pos['positionSide'] == position_side and float(pos['positionAmt']) != 0:
                    print(f"找到 {symbol} {position_side} 方向持仓")
                    return pos

        for pos in symbol_positions:
            if float(pos['positionAmt']) != 0:
                print(f"找到 {symbol} 持仓，方向: {pos['positionSide']}")
                return pos

        print(f"{symbol} 存在持仓记录，但持仓数量为0")
        return symbol_positions[0]

    except Exception as e:
        print(f"获取持仓信息时出错: {e}")
        return None


def place_stop_market_order(symbol, side, quantity, stop_price):
    """下市价止损单"""
    timestamp = int(time.time() * 1000)

    params = {
        'symbol': symbol,
        'side': side,
        'type': 'STOP_MARKET',
        'quantity': quantity,
        'stopPrice': stop_price,
        'timestamp': timestamp,
        'timeInForce': 'GTC'
    }

    query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
    signature = get_signature(query_string)

    headers = get_headers()
    url = f"{BINANCE_FUTURES_BASE_URL}/fapi/v1/order?{query_string}&signature={signature}"

    # BUG FIX: 初始化 response 为 None，避免异常时 NameError
    response = None
    try:
        response = requests.post(url, headers=headers, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"下单时出错: {e}")
        if response is not None:
            try:
                print(f"错误详情: {response.json()}")
            except ValueError:
                print(f"错误响应: {response.text}")
        return None


def set_stop_loss(symbol, position_side=None, stop_percent=1.0):
    """为指定交易对设置市价止损"""
    print(f"正在设置 {symbol} 的市价止损...")

    position_info = get_position_info(symbol, position_side)
    if not position_info:
        print(f"无法获取 {symbol} 的持仓信息，取消止损设置")
        return False

    print(f"持仓信息原始数据: {position_info}")

    position_amt = float(position_info['positionAmt'])
    entry_price = float(position_info['entryPrice'])
    actual_position_side = position_info['positionSide']

    print(f"持仓数量(positionAmt): {position_amt} (类型: {type(position_amt)})")
    print(f"平均成本(entryPrice): {entry_price}")
    print(f"实际持仓方向: {actual_position_side}")

    if position_amt == 0:
        print(f"{symbol} 当前没有持仓，无法设置止损")
        return False

    if actual_position_side == 'LONG' or (position_amt > 0 and actual_position_side == 'BOTH'):
        side = 'SELL'
        stop_price = entry_price * (1 - stop_percent / 100)
        quantity = abs(position_amt)
        print(f"检测到多头持仓，将设置卖出止损")
    elif actual_position_side == 'SHORT' or (position_amt < 0 and actual_position_side == 'BOTH'):
        side = 'BUY'
        stop_price = entry_price * (1 + stop_percent / 100)
        quantity = abs(position_amt)
        print(f"检测到空头持仓，将设置买入止损")
    else:
        print(f"未知的持仓方向: {actual_position_side}")
        return False

    print(f"计算的止损价格: {stop_price}, 止损数量: {quantity}, 交易方向: {side}")

    order_result = place_stop_market_order(symbol, side, quantity, stop_price)
    if order_result:
        print(f"止损单已成功下单!")
        print(f"订单详情: {order_result}")
        return True
    else:
        print("止损单下单失败")
        return False


if __name__ == "__main__":
    print("注意: 此脚本将为指定交易对设置市价止损单")
    print("当前功能为自动检测持仓并设置市价止损")
    print(f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (UTC+8)")

    # 保持注释状态，等待用户确认后再执行
    # set_stop_loss('BTCUSDT', stop_percent=1.0)
    # set_stop_loss('BTCUSDT', position_side='LONG', stop_percent=1.5)
