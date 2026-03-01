import requests
import pandas as pd
import sys
from config import BINANCE_FUTURES_BASE_URL, DEFAULT_TIMEOUT, DEFAULT_SYMBOL


def calculate_moving_averages(symbol='BTCUSDT', interval='15m', limit=15):
    """计算移动平均线"""
    url = f'{BINANCE_FUTURES_BASE_URL}/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}'
    r = requests.get(url=url, timeout=DEFAULT_TIMEOUT)
    r.raise_for_status()
    r = r.json()

    df = pd.DataFrame(r)
    df = df.drop(columns=[5, 6, 7, 8, 9, 10, 11])
    df.columns = ['opentime', 'open', 'high', 'low', 'close']

    df['7_day_ma'] = df['close'].rolling(window=7).mean()

    return df


def analyze_moving_averages(df):
    """分析并打印移动平均线数据"""
    print(df)
    print("实时的MA7均线数据是", df['7_day_ma'].iloc[-1])


def main(symbol='BTCUSDT', interval='15m'):
    print(f"计算{symbol} {interval} K线移动平均线指标")
    ma_data = calculate_moving_averages(symbol, interval=interval)
    analyze_moving_averages(ma_data)


if __name__ == '__main__':
    symbol = DEFAULT_SYMBOL
    interval = '15m'

    if len(sys.argv) > 1:
        symbol = sys.argv[1]
    if len(sys.argv) > 2:
        interval = sys.argv[2]

    main(symbol, interval)
