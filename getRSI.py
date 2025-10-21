import requests
import pandas as pd
import ta  # 技术分析库，用于计算RSI等指标
import sys

def calculate_rsi(symbol='ETHUSDT', interval='5m', limit=1000):
    """计算RSI指标"""
    # 币安期货K线数据接口
    url = f'https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}'
    r = requests.get(url=url).json()
    
    # 将返回的JSON数据转换为DataFrame
    df = pd.DataFrame(r)
    # 删除不需要的列
    df = df.drop(columns=[5, 6, 7, 8, 9, 10, 11])
    # 为列命名
    df.columns = ['timestamp', 'open', 'high', 'low', 'close']
    
    # 转换时间戳为可读时间（统一使用中国时区 UTC+8）
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms').dt.tz_localize('UTC').dt.tz_convert('Asia/Shanghai')
    
    # 将数据类型转换为浮点数
    for col in ['open', 'high', 'low', 'close']:
        df[col] = df[col].astype(float)
    
    # 计算不同周期的RSI指标
    # 默认周期为14的RSI
    df['rsi_14'] = ta.momentum.rsi(df['close'])
    # 计算短期RSI（7周期）
    df['rsi_7'] = ta.momentum.rsi(df['close'], window=7)
    # 计算长期RSI（21周期）
    df['rsi_21'] = ta.momentum.rsi(df['close'], window=21)
    
    # 计算RSI信号线（RSI的简单移动平均线）
    df['rsi_14_signal'] = df['rsi_14'].rolling(window=9).mean()
    
    # RSI超买超卖信号判断
    df['rsi_signal'] = '中性'
    df.loc[df['rsi_14'] > 70, 'rsi_signal'] = '超买'
    df.loc[df['rsi_14'] < 30, 'rsi_signal'] = '超卖'
    
    # RSI背离判断（简化版）
    df['price_change'] = df['close'].pct_change()
    df['rsi_change'] = df['rsi_14'].pct_change()
    df['divergence'] = '无'
    df.loc[(df['price_change'] > 0) & (df['rsi_change'] < 0), 'divergence'] = '顶背离'
    df.loc[(df['price_change'] < 0) & (df['rsi_change'] > 0), 'divergence'] = '底背离'
    
    # 计算其他常用指标
    # 布林带
    bbands = ta.volatility.BollingerBands(df['close'])
    df['bb_upper'] = bbands.bollinger_hband()
    df['bb_middle'] = bbands.bollinger_mavg()
    df['bb_lower'] = bbands.bollinger_lband()
    
    # MACD
    macd = ta.trend.MACD(df['close'])
    df['macd'] = macd.macd()
    df['macd_signal'] = macd.macd_signal()
    df['macd_diff'] = macd.macd_diff()
    
    # 移动平均线
    df['sma_50'] = ta.trend.sma_indicator(df['close'], window=50)
    df['ema_20'] = ta.trend.ema_indicator(df['close'], window=20)
    
    return df

def analyze_rsi(df):
    """分析RSI数据并给出建议"""
    # 打印最近20条RSI数据和信号
    print(f"RSI指标数据（最近20条）:")
    print(df[['datetime', 'close', 'rsi_7', 'rsi_14', 'rsi_21', 'rsi_signal', 'divergence']].tail(20))
    print("\n时间已统一为中国时区 (UTC+8)")
    
    # ta库的其他常用指标示例（可选使用）
    print("\n=== ta库其他常用指标计算示例 ===")
    print("ta库没有直接的KDJ函数，但可以使用momentum指标作为替代或自行实现")
    
    # 现在获取最新数据，确保包含所有新计算的指标
    latest_data = df.iloc[-1]
    
    # 打印最新的RSI数据和分析
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
    
    # 交易建议
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

# 主函数，接受命令行参数
if __name__ == "__main__":
    # 默认参数
    symbol = 'ETHUSDT'
    interval = '5m'
    
    # 从命令行获取参数
    if len(sys.argv) > 1:
        symbol = sys.argv[1]
    if len(sys.argv) > 2:
        interval = sys.argv[2]
    
    try:
        print(f"计算{symbol} {interval}周期的RSI指标...")
        # 计算RSI
        rsi_df = calculate_rsi(symbol, interval)
        # 分析RSI
        analyze_rsi(rsi_df)
        print(f"\n脚本已完成{symbol} {interval}周期的RSI指标计算和分析。")
    except Exception as e:
        print(f'执行出错: {str(e)}')