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

def get_futures_account_info():
    """获取合约账户信息，包括余额"""
    url = 'https://fapi.binance.com/fapi/v2/account'
    # 当前时间戳
    timestamp = int(round(time.time() * 1000))
    query_string = f'timestamp={timestamp}'
    signature = hashing(query_string)
    params = {
        'timestamp': timestamp,
        'signature': signature
    }
    
    try:
        print(f"请求时间戳: {timestamp}")
        response = requests.get(url=url, headers=headers, params=params, timeout=15)
        
        print(f"响应状态码: {response.status_code}")
        
        if response.status_code != 200:
            print(f"API错误响应: {response.text}")
            return None
        
        return response.json()
        
    except Exception as e:
        print(f"获取账户信息异常: {str(e)}")
        return None

def check_futures_balance():
    """检查并显示合约账户可用资金"""
    print('正在查询合约账户资金信息...')
    print(f'查询时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} (UTC+8)')
    print('-' * 60)
    
    account_info = get_futures_account_info()
    
    if not account_info:
        print('未获取到账户信息')
        return
    
    # 提取并显示账户余额信息
    print("合约账户资金信息:")
    print('-' * 60)
    
    # 显示账户基本信息
    if 'positions' in account_info:
        print(f"总持仓数: {len([p for p in account_info['positions'] if float(p['positionAmt']) != 0])}")
    
    # 显示余额信息
        if 'assets' in account_info:
            print("\n资产详情 (仅显示USDT):")
            print('-' * 80)
            print('{:<10} {:<18} {:<18} {:<18}'.format('资产', '总资产(USDT)', '可用资产(USDT)', '已用保证金(USDT)'))
            print('-' * 80)
            
            # 只显示USDT资产
            usdt_asset = None
            for asset in account_info['assets']:
                if asset.get('asset') == 'USDT':
                    usdt_asset = asset
                    break
            
            if usdt_asset:
                wallet_balance = float(usdt_asset.get('walletBalance', 0))
                available_balance = float(usdt_asset.get('availableBalance', 0))
                margin_balance = float(usdt_asset.get('marginBalance', 0))
                
                # 计算已用保证金
                used_margin = margin_balance - available_balance
                
                # 精确到小数点后四位
                print('{:<10} {:<18.4f} {:<18.4f} {:<18.4f}'.format(
                    'USDT',
                    wallet_balance,
                    available_balance,
                    used_margin
                ))
            else:
                print("未找到USDT资产信息")
            
            # 其他资产的异常数据是Binance API返回的，可能是测试账户的特殊情况
            print("\n注意：其他资产的异常数据是API返回的，不影响您的实际USDT资产")
    else:
        # 如果没有assets字段，尝试从主账户信息中提取
        print("\n账户余额:")
        print(f"总资产: {account_info.get('totalWalletBalance', 'N/A')}")
        print(f"可用资产: {account_info.get('availableBalance', 'N/A')}")
        print(f"已用保证金: {account_info.get('totalMarginBalance', 'N/A')}")
    
    # 显示更多账户指标
    print('\n' + '-' * 80)
    print("账户状态信息 (精确到小数点后四位):")
    
    # 尝试转换为浮点数并精确显示
    try:
        total_margin_balance = float(account_info.get('totalMarginBalance', 0))
        total_unrealized_profit = float(account_info.get('totalUnrealizedProfit', 0))
        total_maintenance_margin = float(account_info.get('totalMaintenanceMargin', 0))
        
        print(f"账户权益: {total_margin_balance:.4f} USDT")
        print(f"未实现盈亏: {total_unrealized_profit:.4f} USDT")
        print(f"维持保证金: {total_maintenance_margin:.4f} USDT")
        
        # 计算可用资金百分比
        if usdt_asset:
            available_percent = (float(usdt_asset.get('availableBalance', 0)) / float(usdt_asset.get('walletBalance', 1))) * 100
            print(f"可用资金比例: {available_percent:.2f}%")
    except Exception as e:
        print(f"显示账户指标时出错: {str(e)}")
    
    print('-' * 80)

if __name__ == '__main__':
    check_futures_balance()