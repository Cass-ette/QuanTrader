import requests
import pandas as pd
import ta
import sys
from config import BINANCE_FUTURES_BASE_URL, DEFAULT_TIMEOUT, DEFAULT_SYMBOL


def calculate_rsi(symbol='BTCUSDT', interval='5m', period=14, limit=1000):
    """计算RSI指标"""
    url = f'{BINANCE_FUTURES_BASE_URL}/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}'
    r = requests.get(url=url, timeout=DEFAULT_TIMEOUT)
    r.raise_for_status()
    r = r.json()

    df = pd.DataFrame(r)
    df = df.drop(columns=[5, 6, 7, 8, 9, 10, 11])
    df.columns = ['timestamp', 'open', 'high', 'low', 'close']

    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms').dt.tz_localize('UTC').dt.tz_convert('Asia/Shanghai')

    for col in ['open', 'high', 'low', 'close']:
        df[col] = df[col].astype(float)

    df['rsi_14'] = ta.momentum.rsi(df['close'], window=period)
    df['rsi_7'] = ta.momentum.rsi(df['close'], window=7)
    df['rsi_21'] = ta.momentum.rsi(df['close'], window=21)
    df['rsi_14_signal'] = df['rsi_14'].rolling(window=9).mean()

    df['rsi_signal'] = '中性'
    df.loc[df['rsi_14'] > 70, 'rsi_signal'] = '超买'
    df.loc[df['rsi_14'] < 30, 'rsi_signal'] = '超卖'

    df['price_change'] = df['close'].pct_change()
    df['rsi_change'] = df['rsi_14'].pct_change()
    df['divergence'] = '无'
    df.loc[(df['price_change'] > 0) & (df['rsi_change'] < 0), 'divergence'] = '顶背离'
    df.loc[(df['price_change'] < 0) & (df['rsi_change'] > 0), 'divergence'] = '底背离'

    bbands = ta.volatility.BollingerBands(df['close'])
    df['bb_upper'] = bbands.bollinger_hband()
    df['bb_middle'] = bbands.bollinger_mavg()
    df['bb_lower'] = bbands.bollinger_lband()

    macd = ta.trend.MACD(df['close'])
    df['macd'] = macd.macd()
    df['macd_signal'] = macd.macd_signal()
    df['macd_diff'] = macd.macd_diff()

    df['sma_50'] = ta.trend.sma_indicator(df['close'], window=50)
    df['ema_20'] = ta.trend.ema_indicator(df['close'], window=20)

    return df


def analyze_rsi(df):
    """分析RSI数据并给出建议"""
    print(f"RSI指标数据（最近20条）:")
    print(df[['datetime', 'close', 'rsi_7', 'rsi_14', 'rsi_21', 'rsi_signal', 'divergence']].tail(20))
    print("\n时间已统一为中国时区 (UTC+8)")

    latest_data = df.iloc[-1]

    print("\n最新RSI指标分析:")
    print(f"收盘价: {latest_data['close']:.2f}")
    print(f"7周期RSI: {latest_data['rsi_7']:.2f}")
    print(f"14周期RSI: {latest_data['rsi_14']:.2f}")
    print(f"21周期RSI: {latest_data['rsi_21']:.2f}")
    print(f"RSI信号: {latest_data['rsi_signal']}")
    print(f"背离状态: {latest_data['divergence']}")
    print(f"布林带中轨示例值: {latest_data['bb_middle']:.2f}")
    print(f"MACD示例值: {latest_data['macd']:.4f}")
    print(f"50周期简单移动平均线示例值: {latest_data['sma_50']:.2f}")

    if latest_data['rsi_14'] > 70:
        recommendation = "RSI处于超买区域，可能面临回调风险，建议谨慎或考虑做空"
    elif latest_data['rsi_14'] < 30:
        recommendation = "RSI处于超卖区域，可能是反弹机会，建议关注或考虑做多"
    elif latest_data['divergence'] == '底背离':
        recommendation = "出现底背离信号，可能即将反转上涨，建议关注"
    elif latest_data['divergence'] == '顶背离':
        recommendation = "出现顶背离信号，可能即将反转下跌，建议谨慎"
    else:
        recommendation = "RSI处于正常区间，建议结合其他指标综合判断"

    print(f"\n交易建议: {recommendation}")
    return recommendation


if __name__ == "__main__":
    symbol = DEFAULT_SYMBOL
    interval = '5m'
    period = 14

    if len(sys.argv) > 1:
        symbol = sys.argv[1]
    if len(sys.argv) > 2:
        interval = sys.argv[2]
    if len(sys.argv) > 3:
        try:
            period = int(sys.argv[3])
        except ValueError:
            print(f"警告: RSI周期参数无效，使用默认值 {period}")

    try:
        print(f"计算{symbol} {interval}周期的RSI指标(周期={period})...")
        rsi_df = calculate_rsi(symbol, interval, period=period)
        analyze_rsi(rsi_df)
        print(f"\n脚本已完成{symbol} {interval}周期的RSI指标计算和分析。")
    except Exception as e:
        print(f'执行出错: {str(e)}')
