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

def market_short(symbol, quantity, position_side='SHORT'):  # 市价开空，添加position_side参数
    """执行币安期货市价开空操作
    
    参数:
        symbol: 交易对，如 'ETHUSDT'
        quantity: 卖出数量
        position_side: 仓位方向，'SHORT'(双向持仓) 或 'BOTH'(单向持仓)
    """
    url = 'https://fapi.binance.com/fapi/v1/order'
    # 当前时间戳（用于API请求，API需要UTC时间戳）
    timestamp = int(round(time.time() * 1000))
    query_string = 'timestamp=%s&symbol=%s&side=SELL&type=MARKET&quantity=%s&positionSide=%s' % (str(timestamp), symbol, str(quantity), position_side)
    signature = hashing(query_string)
    params = {
        'timestamp': timestamp,
        'signature': signature,
        'symbol': symbol,
        'side': 'SELL',  # 卖出（做空）
        'type': 'MARKET',
        'quantity': quantity,
        'positionSide': position_side  # 添加仓位方向参数
    }
    
    print(f"交易请求时间戳(API使用UTC)：{timestamp}")
    print(f"当前本地时间(中国时区UTC+8)：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (UTC+8)")
     # 注意：交易执行代码保持不变，用于正常交易操作，但使用前请确认
    try:
        r = requests.post(url=url, headers=headers, params=params).json()
        if 'code' in r:
            print(f'开空失败: {symbol} - 错误代码: {r["code"]}, 消息: {r["msg"]}')
            print(f'时间: {time.strftime("%Y-%m-%d %H:%M:%S")}')
            print(f'建议: 检查账户设置中的持仓模式，当前使用的position_side: {position_side}')
        else:
            print(f'开空成功: {symbol}')
            print(f'时间: {time.strftime("%Y-%m-%d %H:%M:%S")}')
            print(f'数量: {quantity}')
            print(f'订单详情: {r}')
    except Exception as e:
        print(f'请求异常: {str(e)}')

# 主函数，接受命令行参数
if __name__ == "__main__":
    import sys
    
    # 默认参数
    symbol = 'ETHUSDT'
    quantity = 0.006
    position_side = 'SHORT'
    
    # 从命令行获取参数
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
            # 注意：这里可以添加设置杠杆的代码，但需要额外的API调用
        except ValueError:
            print("警告: 杠杆参数无效，使用账户默认杠杆")
    
    # 执行开空操作
    try:
        print(f"执行开空操作: {symbol}, 数量: {quantity}, 仓位模式: {position_side}")
        market_short(symbol, quantity, position_side=position_side)
    except Exception as e:
        print(f'执行出错: {str(e)}')