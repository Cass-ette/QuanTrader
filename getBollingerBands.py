import requests
import pandas as pd
import sys
from config import BINANCE_FUTURES_BASE_URL, DEFAULT_TIMEOUT, DEFAULT_SYMBOL


def get_bollinger_bands(symbol='BTCUSDT', interval='5m', period=20, std_dev=2.0):
    """获取指定交易对和时间周期的布林带指标数据"""
    url = f'{BINANCE_FUTURES_BASE_URL}/fapi/v1/klines?symbol={symbol}&interval={interval}&limit=100'
    r = requests.get(url=url, timeout=DEFAULT_TIMEOUT)
    r.raise_for_status()
    r = r.json()

    df = pd.DataFrame(r)
    df = df.drop(columns=[5, 6, 7, 8, 9, 10, 11])
    df.columns = ['opentime', 'open', 'high', 'low', 'close']

    df['close'] = df['close'].astype(float)

    middle_band = df['close'].rolling(window=period).mean()
    df['std_dev'] = df['close'].rolling(window=period).std(ddof=0)

    df['middle_band'] = middle_band
    df['upper_band'] = middle_band + (df['std_dev'] * std_dev)
    df['lower_band'] = middle_band - (df['std_dev'] * std_dev)
    df['band_width'] = ((df['upper_band'] - df['lower_band']) / df['middle_band']) * 100

    latest_data = df.iloc[-1]
    if latest_data['close'] > latest_data['upper_band']:
        status = "超买"
        signal = "可能做空"
    elif latest_data['close'] < latest_data['lower_band']:
        status = "超卖"
        signal = "可能做多"
    else:
        status = "正常"
        signal = "观望"

    return {
        'close': latest_data['close'],
        'middle_band': latest_data['middle_band'],
        'upper_band': latest_data['upper_band'],
        'lower_band': latest_data['lower_band'],
        'band_width': latest_data['band_width'],
        'status': status,
        'signal': signal,
        'std_dev': latest_data['std_dev']
    }


if __name__ == "__main__":
    symbol = DEFAULT_SYMBOL
    interval = '1h'
    period = 20
    std_dev = 2.0

    if len(sys.argv) > 1:
        symbol = sys.argv[1]
    if len(sys.argv) > 2:
        interval = sys.argv[2]
    if len(sys.argv) > 3:
        try:
            period = int(sys.argv[3])
        except ValueError:
            print(f"警告: 周期参数无效，使用默认值 {period}")
    if len(sys.argv) > 4:
        try:
            std_dev = float(sys.argv[4])
        except ValueError:
            print(f"警告: 标准差参数无效，使用默认值 {std_dev}")

    print(f"计算{symbol} {interval}周期的布林带指标(周期={period}, 标准差={std_dev})...")

    bb_data = get_bollinger_bands(symbol, interval=interval, period=period, std_dev=std_dev)

    print("\n最新布林带数据:")
    print(f"收盘价: {bb_data['close']:.2f}")
    print(f"上轨: {bb_data['upper_band']:.2f}")
    print(f"中轨: {bb_data['middle_band']:.2f}")
    print(f"下轨: {bb_data['lower_band']:.2f}")
    print(f"带宽: {bb_data['band_width']:.2f}%")
    print(f"状态: {bb_data['status']}")
    print(f"信号: {bb_data['signal']}")
    print(f"标准差: {bb_data['std_dev']:.2f}")
