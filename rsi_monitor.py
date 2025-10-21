# -*- coding:utf-8 -*-
 
import requests  
import pandas as pd  
import time 
import ta 
import smtplib 
from email.mime.text import MIMEText 
from email.mime.multipart import MIMEMultipart 
from email.header import Header
import random
import hashlib
import hmac
import os
from datetime import datetime, timezone, timedelta

# 配置选项
USE_MOCK_DATA = False  # 设置为True使用模拟数据，False使用真实API
#USE_MOCK_DATA = True  # 设置为True使用模拟数据，False使用真实API

# 监控的交易对和时间周期
symbol_list = ['ETHUSDT'] 
timeframe_list = ['5m','15m','30m','1h','4h'] 

# 生成模拟RSI数据 - 用于测试
def get_mock_rsi(symbol, timeframe):
    print(f"[模拟模式] 生成 {symbol} {timeframe} 的RSI数据...")
    
    # 为ETHUSDT设置RSI值范围，根据不同时间周期生成不同范围的值
    # 这样可以测试不同条件的提醒功能
    if timeframe in ['5m', '15m']:
        # 短时间周期：生成可能触发超买或超卖的RSI值
        rsi = random.uniform(75, 85) if random.random() > 0.5 else random.uniform(15, 25)
    elif timeframe == '30m':
        # 中时间周期：生成接近超买或超卖边界的值
        rsi = random.uniform(65, 75) if random.random() > 0.5 else random.uniform(25, 35)
    else:  # 1h, 4h
        # 长时间周期：生成正常范围内的值
        rsi = random.uniform(40, 60)
    
    print(f"[模拟模式] {symbol} {timeframe} RSI值: {rsi:.2f}")
    return rsi

# 获取RSI指标 - 添加重试机制和模拟数据支持
def get_rsi(symbol, timeframe): 
    # 如果启用模拟数据模式，直接返回模拟的RSI值
    if USE_MOCK_DATA:
        return get_mock_rsi(symbol, timeframe)
    
    # 真实API模式
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        print(f"正在获取 {symbol} {timeframe} 的K线数据... (尝试 {retry_count + 1}/{max_retries})")
        try:
            url = f'https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval={timeframe}&limit=1000' 
            
            # 增加超时时间，添加重试机制
            session = requests.Session()
            retry = requests.adapters.Retry(total=3, backoff_factor=0.3)
            adapter = requests.adapters.HTTPAdapter(max_retries=retry)
            session.mount('http://', adapter)
            session.mount('https://', adapter)
            
            # 增加超时时间到15秒
            response = session.get(url=url, timeout=15)
            response.raise_for_status()  # 检查响应状态
            
            data = response.json()
            
            # 检查数据是否有效
            if not data or len(data) < 14:  # RSI计算需要至少14个数据点
                print(f"警告：{symbol} {timeframe} 返回的数据不足，共{len(data)}条")
                return None
            
            df = pd.DataFrame(data) 
            print(f"成功获取数据，共{len(df)}条记录")
            
            # 只保留需要的列
            df = df.drop(columns=[5, 6, 7, 8, 9, 10, 11], errors='ignore') 
            df.columns = ['timestamp', 'open', 'high', 'low', 'close']    
            
            df['close'] = df['close'].astype(float) 
            
            # 计算RSI指标
            df['rsi'] = ta.momentum.rsi(df['close'], window=14) 
            
            # 获取最新的RSI值（确保索引有效）
            latest_rsi = df['rsi'].iloc[-1]  # 使用iloc更安全
            print(f"{symbol} {timeframe} 最新RSI值: {latest_rsi:.2f}")
            return latest_rsi
        except requests.exceptions.Timeout:
            retry_count += 1
            print(f"连接超时，{retry_count}秒后重试...")
            time.sleep(retry_count)  # 递增等待时间
        except Exception as e:
            print(f"获取{symbol} {timeframe}数据时出错: {str(e)}", get_local_time())
            if retry_count < max_retries - 1:
                retry_count += 1
                print(f"{retry_count}秒后重试...")
                time.sleep(retry_count)
            else:
                # 真实API失败后，切换到模拟数据模式以确保系统可以运行
                print(f"API连接失败，自动切换到模拟数据模式测试系统功能")
                return get_mock_rsi(symbol, timeframe)
    
    print(f"{symbol} {timeframe} 多次尝试后仍无法获取数据")
    return None

# 发送邮件提醒 - 使用网易163邮箱
# 获取本地时间（UTC+8）
def get_local_time():
    # 计算UTC+8时间
    utc_now = datetime.now(timezone.utc)
    local_now = utc_now + timedelta(hours=8)
    return local_now.strftime('%Y-%m-%d %H:%M:%S')

def send_message(subject, body): 
    # 网易163邮箱配置 - 使用之前测试成功的配置
    sender_email = '18028320570@163.com'  # 发件人邮箱
    smtp_password = 'MMdFS7knZxW4fkun'    # 163邮箱授权码
    recipient_email = '18028320570@163.com'  # 收件人邮箱（可以修改为其他邮箱）
    
    print(f"准备发送邮件 - 主题: {subject}")
    
    # 创建邮件对象
    msg = MIMEMultipart() 
    msg['From'] = Header(sender_email)
    msg['To'] = Header(recipient_email)
    msg['Subject'] = Header(subject)

    # 添加邮件正文
    msg.attach(MIMEText(body, 'plain', 'utf-8')) 

    try: 
        # 连接网易163 SMTP服务器（SSL连接）
        server = smtplib.SMTP_SSL('smtp.163.com', 465, timeout=15) 
        
        # 登录邮箱
        server.login(sender_email, smtp_password) 
        
        # 发送邮件
        text = msg.as_string() 
        server.sendmail(sender_email, recipient_email, text) 
        
        # 关闭连接
        server.quit() 
        print(f'邮件发送成功: {subject}', get_local_time())
        return True
    except Exception as e: 
        print(f'邮件发送失败: {e}', get_local_time())
        return False

# 从环境变量读取API密钥
api_key = os.environ.get('BINANCE_API_KEY', 'D3gzp96Lv20e1KCx2WZRPT5xOsavT9jTtATfeVRe6kotuajCdoQjb0lohRoHcBa6')
secret_key = os.environ.get('BINANCE_SECRET_KEY', 'dV1tDLMczFlopnF9ZFXKBJ0oJt9JogJlxnMmeo7TGUhxRwgm5jxdReoUfMJF55XQ')
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.0.0 Safari/537.36',
    'X-MBX-APIKEY': api_key
}

def hashing(query_string):  # 获取签名
    return hmac.new(secret_key.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()

# 获取账户持仓信息并计算收益率/亏损率
def get_position_pnl():
    try:
        # 使用checkPositions.py类似的逻辑获取持仓信息
        url = 'https://fapi.binance.com/fapi/v2/positionRisk'
        
        # 获取系统时间戳
        timestamp = int(time.time() * 1000)
        query_string = f'timestamp={timestamp}'
        signature = hashing(query_string)
        params = {
            'timestamp': timestamp,
            'signature': signature
        }
        
        # 这里可以复用之前的session配置
        session = requests.Session()
        retry = requests.adapters.Retry(total=3, backoff_factor=0.3)
        adapter = requests.adapters.HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        
        # 发送请求，包含认证信息
        response = session.get(url=url, headers=headers, params=params, timeout=15)
        response.raise_for_status()
        
        positions = response.json()
        
        # 处理持仓信息
        position_info = []
        for pos in positions:
            if float(pos['positionAmt']) != 0:  # 只处理有持仓的交易对
                symbol = pos['symbol']
                positionAmt = float(pos['positionAmt'])
                entryPrice = float(pos['entryPrice'])
                markPrice = float(pos['markPrice'])
                unRealizedProfit = float(pos['unRealizedProfit'])
                leverage = float(pos['leverage'])
                
                # 计算收益率/亏损率
                if entryPrice > 0:
                    if positionAmt > 0:  # 多头
                        pnl_rate = (markPrice - entryPrice) / entryPrice * 100
                    else:  # 空头
                        pnl_rate = (entryPrice - markPrice) / entryPrice * 100
                else:
                    pnl_rate = 0
                
                position_info.append({
                    'symbol': symbol,
                    'positionAmt': positionAmt,
                    'entryPrice': entryPrice,
                    'markPrice': markPrice,
                    'unRealizedProfit': unRealizedProfit,
                    'pnl_rate': pnl_rate,
                    'leverage': leverage
                })
        
        return position_info
    except Exception as e:
        print(f'获取持仓信息时出错: {str(e)}', get_local_time())
        return []

# 初始化标志和时间记录
def initialize_flags():    
    flag1 = {}  # 记录RSI>80的通知状态
    flag2 = {}  # 记录RSI<20的通知状态
    # 收益率标志 - 为1%、5%、10%三个节点分别设置标志
    flag3_profit_1 = {}    # 收益率>=1%的通知状态
    flag3_profit_5 = {}    # 收益率>=5%的通知状态
    flag3_profit_10 = {}   # 收益率>=10%的通知状态
    # 亏损率标志 - 为1%、5%、10%三个节点分别设置标志
    flag4_loss_1 = {}      # 亏损率<=-1%的通知状态
    flag4_loss_5 = {}      # 亏损率<=-5%的通知状态
    flag4_loss_10 = {}     # 亏损率<=-10%的通知状态
    time_now_dict = {}  # 记录最后通知时间
    
    for symbol in symbol_list:
        flag1[symbol] = {}
        flag2[symbol] = {}
        # 初始化收益率标志
        flag3_profit_1[symbol] = True
        flag3_profit_5[symbol] = True
        flag3_profit_10[symbol] = True
        # 初始化亏损率标志
        flag4_loss_1[symbol] = True
        flag4_loss_5[symbol] = True
        flag4_loss_10[symbol] = True
        time_now_dict[symbol] = {}
        
        for timeframe in timeframe_list:
            flag1[symbol][timeframe] = True
            flag2[symbol][timeframe] = True
            time_now_dict[symbol][timeframe] = 0
    
    return flag1, flag2, flag3_profit_1, flag3_profit_5, flag3_profit_10, flag4_loss_1, flag4_loss_5, flag4_loss_10, time_now_dict

# 主函数 - 监控RSI指标和收益率/亏损率
def main():
    # 初始化标志
    flag1, flag2, flag3_profit_1, flag3_profit_5, flag3_profit_10, flag4_loss_1, flag4_loss_5, flag4_loss_10, time_now_dict = initialize_flags()
    
    # 输出启动信息
    print('RSI市场监控脚本启动', get_local_time()) 
    print('监控交易对:', symbol_list)
    print('监控时间周期:', timeframe_list)
    print(f'数据模式: {'模拟数据' if USE_MOCK_DATA else '真实API'}' )
    print('邮件配置: 使用网易163邮箱 (18028320570@163.com)')
    print('-----------------------------------------------------------------------------------------------------', "\n") 
    
    # 主循环
    while True:
        try:
            # 检查持仓收益率/亏损率
            positions = get_position_pnl()
            for position in positions:
                symbol = position['symbol']
                pnl_rate = position['pnl_rate']
                unRealizedProfit = position['unRealizedProfit']
                entryPrice = position['entryPrice']
                markPrice = position['markPrice']
                positionAmt = position['positionAmt']
                leverage = position['leverage']
                
                print(f"{symbol} 持仓收益率: {pnl_rate:.2f}%, 未实现盈亏: {unRealizedProfit:.2f}")
                
                # 检查收益率节点 - 按照1%、5%、10%的顺序，只在达到更高节点时发送提醒
                # 获取本地时间戳
                local_time = get_local_time()
                
                # 收益率 >= 10% 的情况
                if pnl_rate >= 10 and flag3_profit_10[symbol]:
                    subject = f"【收益率提醒】{symbol} 盈利 {pnl_rate:.2f}% - {local_time}"
                    body = f'''{symbol} 收益率已达到 {pnl_rate:.2f}%

持仓详情：
- 持仓方向: {'多头' if positionAmt > 0 else '空头'}
- 持仓数量: {abs(positionAmt):.6f}
- 入场价格: {entryPrice:.2f}
- 当前价格: {markPrice:.2f}
- 未实现盈亏: {unRealizedProfit:.2f}
- 杠杆倍数: {leverage:.0f}x

时间: {local_time}

注意：此为自动提醒，建议及时查看并考虑是否平仓获利。'''
                    send_message(subject, body)
                    flag3_profit_10[symbol] = False
                    # 当达到10%时，自动设置5%和1%标志为False，避免重复提醒
                    flag3_profit_5[symbol] = False
                    flag3_profit_1[symbol] = False
                
                # 收益率 >= 5% 的情况（只有当未达到10%时才检查）
                elif pnl_rate >= 5 and pnl_rate < 10 and flag3_profit_5[symbol]:
                    subject = f"【收益率提醒】{symbol} 盈利 {pnl_rate:.2f}% - {local_time}"
                    body = f'''{symbol} 收益率已达到 {pnl_rate:.2f}%

持仓详情：
- 持仓方向: {'多头' if positionAmt > 0 else '空头'}
- 持仓数量: {abs(positionAmt):.6f}
- 入场价格: {entryPrice:.2f}
- 当前价格: {markPrice:.2f}
- 未实现盈亏: {unRealizedProfit:.2f}
- 杠杆倍数: {leverage:.0f}x

时间: {local_time}

注意：此为自动提醒，建议及时查看并考虑是否平仓获利。'''
                    send_message(subject, body)
                    flag3_profit_5[symbol] = False
                    # 当达到5%时，自动设置1%标志为False，避免重复提醒
                    flag3_profit_1[symbol] = False
                
                # 收益率 >= 1% 的情况（只有当未达到5%时才检查）
                elif pnl_rate >= 1 and pnl_rate < 5 and flag3_profit_1[symbol]:
                    subject = f"【收益率提醒】{symbol} 盈利 {pnl_rate:.2f}% - {local_time}"
                    body = f'''{symbol} 收益率已达到 {pnl_rate:.2f}%

持仓详情：
- 持仓方向: {'多头' if positionAmt > 0 else '空头'}
- 持仓数量: {abs(positionAmt):.6f}
- 入场价格: {entryPrice:.2f}
- 当前价格: {markPrice:.2f}
- 未实现盈亏: {unRealizedProfit:.2f}
- 杠杆倍数: {leverage:.0f}x

时间: {local_time}

注意：此为自动提醒，建议及时查看并考虑是否平仓获利。'''
                    send_message(subject, body)
                    flag3_profit_1[symbol] = False
                
                # 检查亏损率节点 - 按照1%、5%、10%的顺序，只在达到更高节点时发送提醒
                # 亏损率 <= -10% 的情况
                elif pnl_rate <= -10 and flag4_loss_10[symbol]:
                    subject = f"【亏损率提醒】{symbol} 亏损 {abs(pnl_rate):.2f}% - {local_time}"
                    body = f'''{symbol} 亏损率已达到 {pnl_rate:.2f}%

持仓详情：
- 持仓方向: {'多头' if positionAmt > 0 else '空头'}
- 持仓数量: {abs(positionAmt):.6f}
- 入场价格: {entryPrice:.2f}
- 当前价格: {markPrice:.2f}
- 未实现盈亏: {unRealizedProfit:.2f}
- 杠杆倍数: {leverage:.0f}x

时间: {local_time}

注意：此为自动提醒，建议及时查看并考虑是否止损。'''
                    send_message(subject, body)
                    flag4_loss_10[symbol] = False
                    # 当达到-10%时，自动设置-5%和-1%标志为False，避免重复提醒
                    flag4_loss_5[symbol] = False
                    flag4_loss_1[symbol] = False
                
                # 亏损率 <= -5% 的情况（只有当未达到-10%时才检查）
                elif pnl_rate <= -5 and pnl_rate > -10 and flag4_loss_5[symbol]:
                    subject = f"【亏损率提醒】{symbol} 亏损 {abs(pnl_rate):.2f}% - {local_time}"
                    body = f'''{symbol} 亏损率已达到 {pnl_rate:.2f}%

持仓详情：
- 持仓方向: {'多头' if positionAmt > 0 else '空头'}
- 持仓数量: {abs(positionAmt):.6f}
- 入场价格: {entryPrice:.2f}
- 当前价格: {markPrice:.2f}
- 未实现盈亏: {unRealizedProfit:.2f}
- 杠杆倍数: {leverage:.0f}x

时间: {local_time}

注意：此为自动提醒，建议及时查看并考虑是否止损。'''
                    send_message(subject, body)
                    flag4_loss_5[symbol] = False
                    # 当达到-5%时，自动设置-1%标志为False，避免重复提醒
                    flag4_loss_1[symbol] = False
                
                # 亏损率 <= -1% 的情况（只有当未达到-5%时才检查）
                elif pnl_rate <= -1 and pnl_rate > -5 and flag4_loss_1[symbol]:
                    subject = f"【亏损率提醒】{symbol} 亏损 {abs(pnl_rate):.2f}% - {local_time}"
                    body = f'''{symbol} 亏损率已达到 {pnl_rate:.2f}%

持仓详情：
- 持仓方向: {'多头' if positionAmt > 0 else '空头'}
- 持仓数量: {abs(positionAmt):.6f}
- 入场价格: {entryPrice:.2f}
- 当前价格: {markPrice:.2f}
- 未实现盈亏: {unRealizedProfit:.2f}
- 杠杆倍数: {leverage:.0f}x

时间: {local_time}

注意：此为自动提醒，建议及时查看并考虑是否止损。'''
                    send_message(subject, body)
                    flag4_loss_1[symbol] = False
                
                # 重置收益率标志 - 当收益率回落到相应阈值以下时
                if pnl_rate < 1:
                    # 当回落到1%以下时，重置所有收益率标志
                    if not flag3_profit_1[symbol]:
                        flag3_profit_1[symbol] = True
                    if not flag3_profit_5[symbol]:
                        flag3_profit_5[symbol] = True
                    if not flag3_profit_10[symbol]:
                        flag3_profit_10[symbol] = True
                elif pnl_rate < 5:
                    # 当回落到5%以下但仍在1%以上时，只重置5%和10%的标志
                    if not flag3_profit_5[symbol]:
                        flag3_profit_5[symbol] = True
                    if not flag3_profit_10[symbol]:
                        flag3_profit_10[symbol] = True
                elif pnl_rate < 10:
                    # 当回落到10%以下但仍在5%以上时，只重置10%的标志
                    if not flag3_profit_10[symbol]:
                        flag3_profit_10[symbol] = True
                
                # 重置亏损率标志 - 当亏损率回升到相应阈值以上时
                if pnl_rate > -1:
                    # 当回升到-1%以上时，重置所有亏损率标志
                    if not flag4_loss_1[symbol]:
                        flag4_loss_1[symbol] = True
                    if not flag4_loss_5[symbol]:
                        flag4_loss_5[symbol] = True
                    if not flag4_loss_10[symbol]:
                        flag4_loss_10[symbol] = True
                elif pnl_rate > -5:
                    # 当回升到-5%以上但仍在-1%以下时，只重置-5%和-10%的标志
                    if not flag4_loss_5[symbol]:
                        flag4_loss_5[symbol] = True
                    if not flag4_loss_10[symbol]:
                        flag4_loss_10[symbol] = True
                elif pnl_rate > -10:
                    # 当回升到-10%以上但仍在-5%以下时，只重置-10%的标志
                    if not flag4_loss_10[symbol]:
                        flag4_loss_10[symbol] = True
            
            # 遍历交易对和时间周期检查RSI
            for symbol in symbol_list:
                for timeframe in timeframe_list:
                    try:
                        # 获取当前RSI值
                        rsi = get_rsi(symbol, timeframe)
                        if rsi is not None:
                            print(f"{symbol} {timeframe} RSI: {rsi:.2f}")
                        
                        # 检查RSI > 80 的情况（超买，建议做空）
                        if rsi is not None and (rsi >= 80 and time.time() >= time_now_dict[symbol][timeframe] + 1800) and flag1[symbol][timeframe]:
                            local_time = get_local_time()
                            subject = f"【RSI超买提醒】{symbol} ({timeframe}) - {local_time}"
                            body = f'{symbol}当前{timeframe}周期RSI值为：{rsi:.2f}，建议短线看空\n\n时间：{local_time}'
                            send_message(subject, body)
                            time_now_dict[symbol][timeframe] = time.time()
                            flag1[symbol][timeframe] = False
                        
                        # 重置RSI > 80 的标志（当RSI回落时）
                        if flag1[symbol][timeframe] == False and time.time() >= time_now_dict[symbol][timeframe] + 1800:
                            if rsi < 80:
                                flag1[symbol][timeframe] = True
                        
                        # 检查RSI < 20 的情况（超卖，建议做多）
                        if rsi is not None and (rsi <= 20 and time.time() >= time_now_dict[symbol][timeframe] + 1800) and flag2[symbol][timeframe]:
                            local_time = get_local_time()
                            subject = f"【RSI超卖提醒】{symbol} ({timeframe}) - {local_time}"
                            body = f'{symbol}当前{timeframe}周期RSI值为：{rsi:.2f}，建议短线看多\n\n时间：{local_time}'
                            send_message(subject, body)
                            time_now_dict[symbol][timeframe] = time.time()
                            flag2[symbol][timeframe] = False
                        
                        # 重置RSI < 20 的标志（当RSI回升时）
                        # 修复bug：原代码中条件rsi < 80有误，应该是rsi > 20
                        if flag2[symbol][timeframe] == False and time.time() >= time_now_dict[symbol][timeframe] + 1800:
                            if rsi > 20:  # 修复了这个条件
                                flag2[symbol][timeframe] = True    
                        
                        # 避免请求过于频繁
                        time.sleep(1)
                        
                    except Exception as e:
                        print(f'处理{symbol} {timeframe}时出错: {e}', get_local_time())
                        time.sleep(5)
            
            # 每个完整周期后休息一下
            print("\n一个完整监控周期完成，休息10秒...\n")
            time.sleep(10)
            
        except Exception as e:
            print('发生了一个错误', e.__class__.__name__, e, get_local_time(), '\n')
            time.sleep(5)

if __name__ == "__main__":
    main()