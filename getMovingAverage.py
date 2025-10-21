import requests
import pandas as pd
import sys

# 计算移动平均线
def calculate_moving_averages(symbol='ETHUSDT', interval='15m', limit=15):
    # 币安期货 K 线数据接口
    url = f'https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}'
    r = requests.get(url=url).json()
    
    # 将返回的 JSON 数据转换为 DataFrame
    df = pd.DataFrame(r)
    # 删除不需要的列
    df = df.drop(columns=[5, 6, 7, 8, 9, 10, 11])
    # 为列命名
    df.columns = ['opentime', 'open', 'high', 'low', 'close']
    
    # 计算 7 日移动均线
    df['7_day_ma'] = df['close'].rolling(window=7).mean()
    
    return df

# 分析并打印移动平均线数据
def analyze_moving_averages(df):
    # 打印整个 DataFrame
    print(df)
    # 打印实时的均线数据（取最后一行，因为索引从 0 开始）
    print("实时的MA7均线数据是", df['7_day_ma'].iloc[-1])

# 主程序执行
def main(symbol='ETHUSDT', interval='15m'):
    print(f"计算{symbol} {interval} K线移动平均线指标")
    ma_data = calculate_moving_averages(symbol, interval=interval)
    analyze_moving_averages(ma_data)

if __name__ == '__main__':
    # 默认参数
    symbol = 'ETHUSDT'
    interval = '15m'
    
    # 从命令行获取参数
    if len(sys.argv) > 1:
        symbol = sys.argv[1]
    if len(sys.argv) > 2:
        interval = sys.argv[2]
    
    main(symbol, interval)