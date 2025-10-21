import requests
import hashlib
import hmac
import time
import os
from datetime import datetime

# 从环境变量读取API密钥
api_key = os.environ.get('BINANCE_API_KEY', 'D3gzp96Lv20e1KCx2WZRPT5xOsavT9jTtATfeVRe6kotuajCdoQjb0lohRoHcBa6')
secret_key = os.environ.get('BINANCE_SECRET_KEY', 'dV1tDLMczFlopnF9ZFXKBJ0oJt9JogJlxnMmeo7TGUhxRwgm5jxdReoUfMJF55XQ')
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.0.0 Safari/537.36',
    'X-MBX-APIKEY': api_key
}

def hashing(query_string):  # 获取签名
    return hmac.new(secret_key.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()

def get_position_info(symbol):
    """获取指定交易对的持仓信息，特别关注SHORT方向"""
    url = 'https://fapi.binance.com/fapi/v2/positionRisk'
    # 当前时间戳（用于API请求，API需要UTC时间戳）
    timestamp = int(round(time.time() * 1000))
    query_string = f'timestamp={timestamp}'
    print(f"查询持仓时间戳(API使用UTC)：{timestamp}")
    signature = hashing(query_string)
    params = {
        'timestamp': timestamp,
        'signature': signature
    }
    
    try:
        # 获取所有持仓
        all_positions = requests.get(url=url, headers=headers, params=params).json()
        
        # 打印所有持仓用于调试
        print("所有持仓信息:")
        for pos in all_positions:
            if float(pos['positionAmt']) != 0:
                print(f"交易对: {pos['symbol']}, 方向: {pos['positionSide']}, 数量: {pos['positionAmt']}")
        
        # 优先返回SHORT方向的持仓，如果有
        for pos in all_positions:
            if pos['symbol'] == symbol and pos['positionSide'] == 'SHORT':
                return pos
        
        # 否则返回该交易对的任一持仓
        for pos in all_positions:
            if pos['symbol'] == symbol:
                return pos
        
        return None
    except Exception as e:
        print(f'获取持仓信息异常: {str(e)}')
        return None

def close_all_short(symbol, position_side='SHORT'):
    """执行币安期货全部平空操作
    
    参数:
        symbol: 交易对，如 'ETHUSDT'
        position_side: 仓位方向，'SHORT'(双向持仓) 或 'BOTH'(单向持仓)
    """
    # 先查询当前持仓情况
    print(f'正在查询{symbol}的持仓信息...')
    position_info = get_position_info(symbol)
    
    # 调试输出
    print(f'持仓信息原始数据: {position_info}')
    
    if not position_info:
        print(f'无法获取{symbol}的持仓信息')
        return None
    
    # 检查空头持仓
    short_position_amt = float(position_info['positionAmt'])
    print(f'持仓数量(positionAmt): {short_position_amt}, 类型: {type(short_position_amt)}')
    
    if short_position_amt >= 0:
        print(f'{symbol}当前没有空头持仓 (positionAmt: {short_position_amt})')
        print(f'时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} (UTC+8)')
        return None
    
    # 空头持仓数量为负数，取绝对值作为平仓数量
    quantity = abs(short_position_amt)
    print(f'检测到{symbol}空头持仓，数量: {quantity}')
    
    # 执行市价平仓操作
    url = 'https://fapi.binance.com/fapi/v1/order'
    # 当前时间戳（用于API请求，API需要UTC时间戳）
    timestamp = int(round(time.time() * 1000))
    query_string = f'timestamp={timestamp}&symbol={symbol}&side=BUY&type=MARKET&quantity={quantity}&positionSide={position_side}'
    print(f"平仓请求时间戳(API使用UTC)：{timestamp}")
    print(f"当前本地时间(中国时区UTC+8)：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (UTC+8)")
    # 注意：交易执行代码保持不变，用于正常交易操作，但使用前请确认
    signature = hashing(query_string)
    params = {
        'timestamp': timestamp,
        'signature': signature,
        'symbol': symbol,
        'side': 'BUY',  # 买入（平空）
        'type': 'MARKET',
        'quantity': quantity,
        'positionSide': position_side  # 指定平仓的仓位方向
    }
    
    try:
        r = requests.post(url=url, headers=headers, params=params).json()
        if 'code' in r:
            print(f'平空失败: {symbol} - 错误代码: {r["code"]}, 消息: {r["msg"]}')
            print(f'时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} (UTC+8)')
            print(f'建议: 检查账户设置中的持仓模式，当前使用的position_side: {position_side}')
        else:
            print(f'平空成功: {symbol}')
            print(f'时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} (UTC+8)')
            print(f'平仓数量: {quantity}')
            print(f'订单详情: {r}')
    except Exception as e:
        print(f'请求异常: {str(e)}')

# 主函数，接受命令行参数
if __name__ == "__main__":
    import sys
    
    # 默认参数
    symbol = 'ETHUSDT'
    position_side = 'SHORT'
    
    # 从命令行获取参数
    if len(sys.argv) > 1:
        symbol = sys.argv[1]
    
    # 执行平空操作
    try:
        print(f"执行平空操作: {symbol}, 仓位模式: {position_side}")
        close_all_short(symbol, position_side=position_side)
    except Exception as e:
        print(f'执行出错: {str(e)}')