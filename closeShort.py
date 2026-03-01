import sys
from datetime import datetime
from binance_client import signed_request
from config import DEFAULT_SYMBOL


def get_position_info(symbol):
    """获取指定交易对的持仓信息，特别关注SHORT方向"""
    try:
        all_positions = signed_request('GET', '/fapi/v2/positionRisk')

        print("所有持仓信息:")
        for pos in all_positions:
            if float(pos['positionAmt']) != 0:
                print(f"交易对: {pos['symbol']}, 方向: {pos['positionSide']}, 数量: {pos['positionAmt']}")

        for pos in all_positions:
            if pos['symbol'] == symbol and pos['positionSide'] == 'SHORT':
                return pos

        for pos in all_positions:
            if pos['symbol'] == symbol:
                return pos

        return None
    except Exception as e:
        print(f'获取持仓信息异常: {str(e)}')
        return None


def close_all_short(symbol, position_side='SHORT'):
    """执行币安期货全部平空操作"""
    print(f'正在查询{symbol}的持仓信息...')
    position_info = get_position_info(symbol)

    print(f'持仓信息原始数据: {position_info}')

    if not position_info:
        print(f'无法获取{symbol}的持仓信息')
        return None

    short_position_amt = float(position_info['positionAmt'])
    print(f'持仓数量(positionAmt): {short_position_amt}, 类型: {type(short_position_amt)}')

    if short_position_amt >= 0:
        print(f'{symbol}当前没有空头持仓 (positionAmt: {short_position_amt})')
        print(f'时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} (UTC+8)')
        return None

    quantity = abs(short_position_amt)
    print(f'检测到{symbol}空头持仓，数量: {quantity}')

    params = {
        'symbol': symbol,
        'side': 'BUY',
        'type': 'MARKET',
        'quantity': quantity,
        'positionSide': position_side,
    }

    print(f"当前本地时间(中国时区UTC+8)：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (UTC+8)")

    try:
        r = signed_request('POST', '/fapi/v1/order', params)
        if 'code' in r:
            print(f'平空失败: {symbol} - 错误代码: {r["code"]}, 消息: {r["msg"]}')
            print(f'时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} (UTC+8)')
            print(f'建议: 检查账户设置中的持仓模式，当前使用的position_side: {position_side}')
        else:
            print(f'平空成功: {symbol}')
            print(f'时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} (UTC+8)')
            print(f'平仓数量: {quantity}')
            print(f'订单详情: {r}')
        return r
    except Exception as e:
        print(f'请求异常: {str(e)}')
        return None


if __name__ == "__main__":
    symbol = DEFAULT_SYMBOL
    position_side = 'SHORT'

    if len(sys.argv) > 1:
        symbol = sys.argv[1]

    try:
        print(f"执行平空操作: {symbol}, 仓位模式: {position_side}")
        close_all_short(symbol, position_side=position_side)
    except Exception as e:
        print(f'执行出错: {str(e)}')
