import requests
import pandas as pd
import numpy as np
import sys
from config import BINANCE_FUTURES_BASE_URL, DEFAULT_TIMEOUT, DEFAULT_SYMBOL


def calculate_kdj_macd(symbol='BTCUSDT', interval='5m', limit=1000):
    """计算KDJ和MACD指标"""
    url = f'{BINANCE_FUTURES_BASE_URL}/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}'
    r = requests.get(url=url, timeout=DEFAULT_TIMEOUT)
    r.raise_for_status()
    r = r.json()

    df = pd.DataFrame(r)
    df = df.drop(columns=[5, 6, 7, 8, 9, 10, 11])
    df.columns = ['timestamp', 'open', 'high', 'low', 'close']

    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms').dt.tz_localize('UTC').dt.tz_convert('Asia/Shanghai')

    df['close'] = df['close'].astype(float)
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)

    # MACD
    short_period = 12
    long_period = 26
    signal_period = 9

    df['ema_short'] = df['close'].ewm(span=short_period, adjust=False).mean()
    df['ema_long'] = df['close'].ewm(span=long_period, adjust=False).mean()
    df['dif'] = df['ema_short'] - df['ema_long']
    df['dea'] = df['dif'].ewm(span=signal_period, adjust=False).mean()
    df['macd_histogram'] = (df['dif'] - df['dea']) * 2

    # KDJ
    kdj_period = 9
    kdj_slow_period = 3

    df['low_min'] = df['low'].rolling(window=kdj_period).min()
    df['high_max'] = df['high'].rolling(window=kdj_period).max()

    # BUG FIX: 使用 np.where 逐元素安全除法，避免除零错误
    denominator = df['high_max'] - df['low_min']
    df['rsv'] = np.where(
        denominator != 0,
        (df['close'] - df['low_min']) / denominator * 100,
        50.0  # 当最高价等于最低价时默认 RSV 为 50
    )

    df['k'] = df['rsv'].ewm(com=kdj_slow_period - 1, adjust=False).mean()
    df['d'] = df['k'].ewm(com=kdj_slow_period - 1, adjust=False).mean()
    df['j'] = 3 * df['k'] - 2 * df['d']

    return df


def analyze_kdj_macd(df, symbol='BTCUSDT'):
    """分析KDJ和MACD指标并输出结果"""
    print(f"{symbol} MACD和KDJ指标数据（最近10条）:")
    print(df[['datetime', 'close', 'dif', 'dea', 'macd_histogram', 'k', 'd', 'j']].tail(10))
    print("\n时间已统一为中国时区 (UTC+8)")

    latest_data = df.iloc[-1]
    print("\n最新MACD和KDJ指标数据:")
    print("=== MACD指标 ===")
    print(f"收盘价: {latest_data['close']}")
    print(f"DIF (MACD线): {latest_data['dif']}")
    print(f"DEA (信号线): {latest_data['dea']}")
    print(f"MACD柱状: {latest_data['macd_histogram']}")
    print("\n=== KDJ指标 ===")
    print(f"K值: {latest_data['k']}")
    print(f"D值: {latest_data['d']}")
    print(f"J值: {latest_data['j']}")

    # KDJ信号
    current_k = latest_data['k']
    current_d = latest_data['d']
    previous_k = df.iloc[-2]['k'] if len(df) > 1 else current_k
    previous_d = df.iloc[-2]['d'] if len(df) > 1 else current_d

    if latest_data['j'] > 80:
        kdj_signal = "超买区域，建议谨慎或卖出"
    elif latest_data['j'] < 20:
        kdj_signal = "超卖区域，可能是买入机会"
    elif current_k > current_d and previous_k <= previous_d:
        kdj_signal = "金叉信号，可能是买入机会"
    elif current_k < current_d and previous_k >= previous_d:
        kdj_signal = "死叉信号，可能是卖出信号"
    else:
        kdj_signal = "趋势不明，观望为主"

    print(f"KDJ信号判断: {kdj_signal}")

    # MACD信号
    current_histogram = latest_data['macd_histogram']
    previous_histogram = df.iloc[-2]['macd_histogram'] if len(df) > 1 else current_histogram

    if current_histogram > 0 and previous_histogram <= 0:
        macd_signal = "MACD柱状由负转正，可能是买入机会"
    elif current_histogram < 0 and previous_histogram >= 0:
        macd_signal = "MACD柱状由正转负，可能是卖出信号"
    elif latest_data['dif'] > latest_data['dea']:
        macd_signal = "MACD线在信号线之上，多头市场"
    else:
        macd_signal = "MACD线在信号线之下，空头市场"

    print(f"MACD信号判断: {macd_signal}")


if __name__ == '__main__':
    symbol = DEFAULT_SYMBOL
    interval = '5m'

    if len(sys.argv) > 1:
        symbol = sys.argv[1]
    if len(sys.argv) > 2:
        interval = sys.argv[2]

    df = calculate_kdj_macd(symbol, interval)
    analyze_kdj_macd(df, symbol)
