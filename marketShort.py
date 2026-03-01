import time
import sys
from datetime import datetime
from binance_client import signed_request
from config import DEFAULT_SYMBOL


def market_short(symbol, quantity, position_side='SHORT'):
    """执行币安期货市价开空操作

    参数:
        symbol: 交易对，如 'BTCUSDT'
        quantity: 卖出数量
        position_side: 仓位方向，'SHORT'(双向持仓) 或 'BOTH'(单向持仓)

    返回:
        dict: API响应，成功时包含orderId
    """
    params = {
        'symbol': symbol,
        'side': 'SELL',
        'type': 'MARKET',
        'quantity': quantity,
        'positionSide': position_side,
    }

    print(f"当前本地时间(中国时区UTC+8)：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (UTC+8)")

    try:
        r = signed_request('POST', '/fapi/v1/order', params)
        if 'code' in r:
            print(f'开空失败: {symbol} - 错误代码: {r["code"]}, 消息: {r["msg"]}')
            print(f'时间: {time.strftime("%Y-%m-%d %H:%M:%S")}')
            print(f'建议: 检查账户设置中的持仓模式，当前使用的position_side: {position_side}')
        else:
            print(f'开空成功: {symbol}')
            print(f'时间: {time.strftime("%Y-%m-%d %H:%M:%S")}')
            print(f'数量: {quantity}')
            print(f'订单详情: {r}')
        return r
    except Exception as e:
        print(f'请求异常: {str(e)}')
        return None


if __name__ == "__main__":
    symbol = DEFAULT_SYMBOL
    quantity = 0.006
    position_side = 'SHORT'

    if len(sys.argv) > 1:
        symbol = sys.argv[1]
    if len(sys.argv) > 2:
        try:
            quantity = float(sys.argv[2])
        except ValueError:
            print(f"警告: 数量参数无效，使用默认值 {quantity}")
    if len(sys.argv) > 3:
        try:
            leverage = int(sys.argv[3])
            print(f"设置杠杆倍数: {leverage}x")
        except ValueError:
            print("警告: 杠杆参数无效，使用账户默认杠杆")

    try:
        print(f"执行开空操作: {symbol}, 数量: {quantity}, 仓位模式: {position_side}")
        market_short(symbol, quantity, position_side=position_side)
    except Exception as e:
        print(f'执行出错: {str(e)}')
