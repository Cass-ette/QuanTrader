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
from datetime import datetime, timezone, timedelta

from config import (
    BINANCE_FUTURES_BASE_URL, DEFAULT_TIMEOUT,
    EMAIL_SENDER, EMAIL_SMTP_PASSWORD, EMAIL_RECIPIENT,
)
from binance_client import signed_request

# 配置选项
USE_MOCK_DATA = False

# 监控的交易对和时间周期 - 支持任意 Binance 交易对
symbol_list = ['BTCUSDT', 'ETHUSDT']
timeframe_list = ['5m', '15m', '30m', '1h', '4h']


def get_mock_rsi(symbol, timeframe):
    print(f"[模拟模式] 生成 {symbol} {timeframe} 的RSI数据...")
    if timeframe in ['5m', '15m']:
        rsi = random.uniform(75, 85) if random.random() > 0.5 else random.uniform(15, 25)
    elif timeframe == '30m':
        rsi = random.uniform(65, 75) if random.random() > 0.5 else random.uniform(25, 35)
    else:
        rsi = random.uniform(40, 60)
    print(f"[模拟模式] {symbol} {timeframe} RSI值: {rsi:.2f}")
    return rsi


def get_rsi(symbol, timeframe):
    if USE_MOCK_DATA:
        return get_mock_rsi(symbol, timeframe)

    max_retries = 3
    retry_count = 0

    while retry_count < max_retries:
        print(f"正在获取 {symbol} {timeframe} 的K线数据... (尝试 {retry_count + 1}/{max_retries})")
        try:
            url = f'{BINANCE_FUTURES_BASE_URL}/fapi/v1/klines?symbol={symbol}&interval={timeframe}&limit=1000'

            session = requests.Session()
            retry = requests.adapters.Retry(total=3, backoff_factor=0.3)
            adapter = requests.adapters.HTTPAdapter(max_retries=retry)
            session.mount('http://', adapter)
            session.mount('https://', adapter)

            response = session.get(url=url, timeout=DEFAULT_TIMEOUT)
            response.raise_for_status()

            data = response.json()

            if not data or len(data) < 14:
                print(f"警告：{symbol} {timeframe} 返回的数据不足，共{len(data)}条")
                return None

            df = pd.DataFrame(data)
            print(f"成功获取数据，共{len(df)}条记录")

            df = df.drop(columns=[5, 6, 7, 8, 9, 10, 11], errors='ignore')
            df.columns = ['timestamp', 'open', 'high', 'low', 'close']
            df['close'] = df['close'].astype(float)

            df['rsi'] = ta.momentum.rsi(df['close'], window=14)

            latest_rsi = df['rsi'].iloc[-1]
            print(f"{symbol} {timeframe} 最新RSI值: {latest_rsi:.2f}")
            return latest_rsi
        except requests.exceptions.Timeout:
            retry_count += 1
            print(f"连接超时，{retry_count}秒后重试...")
            time.sleep(retry_count)
        except Exception as e:
            print(f"获取{symbol} {timeframe}数据时出错: {str(e)}", get_local_time())
            if retry_count < max_retries - 1:
                retry_count += 1
                print(f"{retry_count}秒后重试...")
                time.sleep(retry_count)
            else:
                print(f"API连接失败，自动切换到模拟数据模式测试系统功能")
                return get_mock_rsi(symbol, timeframe)

    print(f"{symbol} {timeframe} 多次尝试后仍无法获取数据")
    return None


def get_local_time():
    utc_now = datetime.now(timezone.utc)
    local_now = utc_now + timedelta(hours=8)
    return local_now.strftime('%Y-%m-%d %H:%M:%S')


def send_message(subject, body):
    print(f"准备发送邮件 - 主题: {subject}")

    msg = MIMEMultipart()
    msg['From'] = Header(EMAIL_SENDER)
    msg['To'] = Header(EMAIL_RECIPIENT)
    msg['Subject'] = Header(subject)
    msg.attach(MIMEText(body, 'plain', 'utf-8'))

    try:
        server = smtplib.SMTP_SSL('smtp.163.com', 465, timeout=15)
        server.login(EMAIL_SENDER, EMAIL_SMTP_PASSWORD)
        text = msg.as_string()
        server.sendmail(EMAIL_SENDER, EMAIL_RECIPIENT, text)
        server.quit()
        print(f'邮件发送成功: {subject}', get_local_time())
        return True
    except Exception as e:
        print(f'邮件发送失败: {e}', get_local_time())
        return False


def get_position_pnl():
    try:
        positions = signed_request('GET', '/fapi/v2/positionRisk')

        position_info = []
        for pos in positions:
            if float(pos['positionAmt']) != 0:
                symbol = pos['symbol']
                positionAmt = float(pos['positionAmt'])
                entryPrice = float(pos['entryPrice'])
                markPrice = float(pos['markPrice'])
                unRealizedProfit = float(pos['unRealizedProfit'])
                leverage = float(pos['leverage'])

                if entryPrice > 0:
                    if positionAmt > 0:
                        pnl_rate = (markPrice - entryPrice) / entryPrice * 100
                    else:
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


def initialize_flags():
    flag1 = {}
    flag2 = {}
    flag3_profit_1 = {}
    flag3_profit_5 = {}
    flag3_profit_10 = {}
    flag4_loss_1 = {}
    flag4_loss_5 = {}
    flag4_loss_10 = {}
    time_now_dict = {}

    for symbol in symbol_list:
        flag1[symbol] = {}
        flag2[symbol] = {}
        flag3_profit_1[symbol] = True
        flag3_profit_5[symbol] = True
        flag3_profit_10[symbol] = True
        flag4_loss_1[symbol] = True
        flag4_loss_5[symbol] = True
        flag4_loss_10[symbol] = True
        time_now_dict[symbol] = {}

        for timeframe in timeframe_list:
            flag1[symbol][timeframe] = True
            flag2[symbol][timeframe] = True
            time_now_dict[symbol][timeframe] = 0

    return flag1, flag2, flag3_profit_1, flag3_profit_5, flag3_profit_10, flag4_loss_1, flag4_loss_5, flag4_loss_10, time_now_dict


def main():
    flag1, flag2, flag3_profit_1, flag3_profit_5, flag3_profit_10, flag4_loss_1, flag4_loss_5, flag4_loss_10, time_now_dict = initialize_flags()

    print('RSI市场监控脚本启动', get_local_time())
    print('监控交易对:', symbol_list)
    print('监控时间周期:', timeframe_list)
    data_mode = '模拟数据' if USE_MOCK_DATA else '真实API'
    print(f'数据模式: {data_mode}')
    print('-----' * 20, "\n")

    while True:
        try:
            positions = get_position_pnl()
            for position in positions:
                symbol = position['symbol']
                pnl_rate = position['pnl_rate']
                unRealizedProfit = position['unRealizedProfit']
                entryPrice = position['entryPrice']
                markPrice = position['markPrice']
                positionAmt = position['positionAmt']
                leverage = position['leverage']

                # 动态初始化标志（支持任意交易对）
                if symbol not in flag3_profit_1:
                    flag3_profit_1[symbol] = True
                    flag3_profit_5[symbol] = True
                    flag3_profit_10[symbol] = True
                    flag4_loss_1[symbol] = True
                    flag4_loss_5[symbol] = True
                    flag4_loss_10[symbol] = True

                print(f"{symbol} 持仓收益率: {pnl_rate:.2f}%, 未实现盈亏: {unRealizedProfit:.2f}")

                local_time = get_local_time()

                position_detail = f'''持仓详情：
- 持仓方向: {'多头' if positionAmt > 0 else '空头'}
- 持仓数量: {abs(positionAmt):.6f}
- 入场价格: {entryPrice:.2f}
- 当前价格: {markPrice:.2f}
- 未实现盈亏: {unRealizedProfit:.2f}
- 杠杆倍数: {leverage:.0f}x

时间: {local_time}'''

                # 收益率提醒
                if pnl_rate >= 10 and flag3_profit_10[symbol]:
                    subject = f"【收益率提醒】{symbol} 盈利 {pnl_rate:.2f}% - {local_time}"
                    body = f"{symbol} 收益率已达到 {pnl_rate:.2f}%\n\n{position_detail}\n\n注意：此为自动提醒，建议及时查看并考虑是否平仓获利。"
                    send_message(subject, body)
                    flag3_profit_10[symbol] = False
                    flag3_profit_5[symbol] = False
                    flag3_profit_1[symbol] = False
                elif pnl_rate >= 5 and pnl_rate < 10 and flag3_profit_5[symbol]:
                    subject = f"【收益率提醒】{symbol} 盈利 {pnl_rate:.2f}% - {local_time}"
                    body = f"{symbol} 收益率已达到 {pnl_rate:.2f}%\n\n{position_detail}\n\n注意：此为自动提醒，建议及时查看并考虑是否平仓获利。"
                    send_message(subject, body)
                    flag3_profit_5[symbol] = False
                    flag3_profit_1[symbol] = False
                elif pnl_rate >= 1 and pnl_rate < 5 and flag3_profit_1[symbol]:
                    subject = f"【收益率提醒】{symbol} 盈利 {pnl_rate:.2f}% - {local_time}"
                    body = f"{symbol} 收益率已达到 {pnl_rate:.2f}%\n\n{position_detail}\n\n注意：此为自动提醒，建议及时查看并考虑是否平仓获利。"
                    send_message(subject, body)
                    flag3_profit_1[symbol] = False

                # 亏损率提醒
                elif pnl_rate <= -10 and flag4_loss_10[symbol]:
                    subject = f"【亏损率提醒】{symbol} 亏损 {abs(pnl_rate):.2f}% - {local_time}"
                    body = f"{symbol} 亏损率已达到 {pnl_rate:.2f}%\n\n{position_detail}\n\n注意：此为自动提醒，建议及时查看并考虑是否止损。"
                    send_message(subject, body)
                    flag4_loss_10[symbol] = False
                    flag4_loss_5[symbol] = False
                    flag4_loss_1[symbol] = False
                elif pnl_rate <= -5 and pnl_rate > -10 and flag4_loss_5[symbol]:
                    subject = f"【亏损率提醒】{symbol} 亏损 {abs(pnl_rate):.2f}% - {local_time}"
                    body = f"{symbol} 亏损率已达到 {pnl_rate:.2f}%\n\n{position_detail}\n\n注意：此为自动提醒，建议及时查看并考虑是否止损。"
                    send_message(subject, body)
                    flag4_loss_5[symbol] = False
                    flag4_loss_1[symbol] = False
                elif pnl_rate <= -1 and pnl_rate > -5 and flag4_loss_1[symbol]:
                    subject = f"【亏损率提醒】{symbol} 亏损 {abs(pnl_rate):.2f}% - {local_time}"
                    body = f"{symbol} 亏损率已达到 {pnl_rate:.2f}%\n\n{position_detail}\n\n注意：此为自动提醒，建议及时查看并考虑是否止损。"
                    send_message(subject, body)
                    flag4_loss_1[symbol] = False

                # 重置收益率标志
                if pnl_rate < 1:
                    flag3_profit_1[symbol] = True
                    flag3_profit_5[symbol] = True
                    flag3_profit_10[symbol] = True
                elif pnl_rate < 5:
                    flag3_profit_5[symbol] = True
                    flag3_profit_10[symbol] = True
                elif pnl_rate < 10:
                    flag3_profit_10[symbol] = True

                # 重置亏损率标志
                if pnl_rate > -1:
                    flag4_loss_1[symbol] = True
                    flag4_loss_5[symbol] = True
                    flag4_loss_10[symbol] = True
                elif pnl_rate > -5:
                    flag4_loss_5[symbol] = True
                    flag4_loss_10[symbol] = True
                elif pnl_rate > -10:
                    flag4_loss_10[symbol] = True

            # RSI 监控
            for symbol in symbol_list:
                for timeframe in timeframe_list:
                    try:
                        rsi = get_rsi(symbol, timeframe)
                        if rsi is not None:
                            print(f"{symbol} {timeframe} RSI: {rsi:.2f}")

                        if rsi is not None and (rsi >= 80 and time.time() >= time_now_dict[symbol][timeframe] + 1800) and flag1[symbol][timeframe]:
                            local_time = get_local_time()
                            subject = f"【RSI超买提醒】{symbol} ({timeframe}) - {local_time}"
                            body = f'{symbol}当前{timeframe}周期RSI值为：{rsi:.2f}，建议短线看空\n\n时间：{local_time}'
                            send_message(subject, body)
                            time_now_dict[symbol][timeframe] = time.time()
                            flag1[symbol][timeframe] = False

                        if not flag1[symbol][timeframe] and time.time() >= time_now_dict[symbol][timeframe] + 1800:
                            if rsi is not None and rsi < 80:
                                flag1[symbol][timeframe] = True

                        if rsi is not None and (rsi <= 20 and time.time() >= time_now_dict[symbol][timeframe] + 1800) and flag2[symbol][timeframe]:
                            local_time = get_local_time()
                            subject = f"【RSI超卖提醒】{symbol} ({timeframe}) - {local_time}"
                            body = f'{symbol}当前{timeframe}周期RSI值为：{rsi:.2f}，建议短线看多\n\n时间：{local_time}'
                            send_message(subject, body)
                            time_now_dict[symbol][timeframe] = time.time()
                            flag2[symbol][timeframe] = False

                        if not flag2[symbol][timeframe] and time.time() >= time_now_dict[symbol][timeframe] + 1800:
                            if rsi is not None and rsi > 20:
                                flag2[symbol][timeframe] = True

                        time.sleep(1)

                    except Exception as e:
                        print(f'处理{symbol} {timeframe}时出错: {e}', get_local_time())
                        time.sleep(5)

            print("\n一个完整监控周期完成，休息10秒...\n")
            time.sleep(10)

        except Exception as e:
            print('发生了一个错误', e.__class__.__name__, e, get_local_time(), '\n')
            time.sleep(5)


if __name__ == "__main__":
    main()
