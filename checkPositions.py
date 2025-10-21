import requests
import hashlib
import hmac
import time
import os
import traceback
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

def get_all_positions():
    """获取账户所有持仓信息"""
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
        # 打印请求信息（不包含密钥）
        print(f"请求URL: {url}")
        print(f"请求参数: timestamp={timestamp}, signature=*****")
        
        # 添加超时设置
        response = requests.get(url=url, headers=headers, params=params, timeout=15)
        
        # 打印响应状态码
        print(f"响应状态码: {response.status_code}")
        
        # 检查响应内容
        if response.status_code != 200:
            print(f"API错误响应: {response.text}")
            return []
            
        # 尝试解析JSON
        try:
            data = response.json()
            print(f"成功获取到数据，数据长度: {len(data) if isinstance(data, list) else '非列表类型'}")
            return data
        except ValueError as json_error:
            print(f"JSON解析错误: {str(json_error)}")
            print(f"原始响应内容: {response.text}")
            return []
            
    except requests.exceptions.RequestException as req_error:
        print(f"请求异常: {str(req_error)}")
        print("详细错误信息:")
        traceback.print_exc()
    except Exception as e:
        print(f"未知异常: {str(e)}")
        print("详细错误信息:")
        traceback.print_exc()
    
    return []

def test_time_sync():
    """测试时间同步"""
    try:
        url = 'https://fapi.binance.com/fapi/v1/time'
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            server_time = response.json().get('serverTime', 0)
            local_time = int(round(time.time() * 1000))
            diff = abs(server_time - local_time)
            print(f"时间同步测试: 本地时间={local_time}, 服务器时间={server_time}")
            print(f"时间差异: {diff}ms")
            if diff > 10000:  # 10秒差异
                print(f"警告: 时间差异超过10秒，可能导致API请求失败")
            return True
        else:
            print(f"时间同步测试失败: 状态码={response.status_code}")
            return False
    except Exception as e:
        print(f"时间同步测试异常: {str(e)}")
        return False

def check_positions():
    """检查并显示所有持仓信息"""
    print('正在查询账户持仓信息...')
    print(f'查询时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} (UTC+8)')
    print('-' * 80)
    
    # 先测试时间同步
    print("执行时间同步测试...")
    test_time_sync()
    print("-" * 50)
    
    positions = get_all_positions()
    
    if not positions:
        print('未获取到持仓信息或无持仓')
        return
    
    # 过滤出有持仓的交易对
    active_positions = [p for p in positions if float(p['positionAmt']) != 0]
    
    if not active_positions:
        print('当前没有任何持仓')
    else:
        print(f'发现 {len(active_positions)} 个有持仓的交易对:')
        print('-' * 80)
        print('{:<10} {:<10} {:<15} {:<15} {:<15} {:<10}'.format(
            '交易对', '持仓方向', '持仓数量', '平均成本', '未实现盈亏', '杠杆倍率'))
        print('-' * 80)
        
        for pos in active_positions:
            symbol = pos['symbol']
            position_amt = float(pos['positionAmt'])
            
            # 确定持仓方向
            if position_amt > 0:
                direction = '多头'
            else:
                direction = '空头'
            
            # 格式化输出
            print('{:<10} {:<10} {:<15.6f} {:<15.2f} {:<15.2f} {:<10}'.format(
                symbol,
                direction,
                abs(position_amt),
                float(pos['entryPrice']),
                float(pos['unRealizedProfit']),
                float(pos['leverage'])
            ))
    
    print('-' * 80)
    print('查询完成')

if __name__ == '__main__':
    check_positions()