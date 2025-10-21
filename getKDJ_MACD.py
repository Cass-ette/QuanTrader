import requests
import pandas as pd

# 币安期货K线数据接口，获取ETHUSDT 5分钟周期的最近1000根K线
url = 'https://fapi.binance.com/fapi/v1/klines?symbol=ETHUSDT&interval=5m&limit=1000'
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
df['close'] = df['close'].astype(float)
df['high'] = df['high'].astype(float)
df['low'] = df['low'].astype(float)

# 计算MACD指标
short_period = 12
long_period = 26
signal_period = 9

# 计算短期和长期的EMA
df['ema_short'] = df['close'].ewm(span=short_period, adjust=False).mean()
df['ema_long'] = df['close'].ewm(span=long_period, adjust=False).mean()

# 计算DIF（MACD线）
df['dif'] = df['ema_short'] - df['ema_long']
# 计算DEA（信号线）
df['dea'] = df['dif'].ewm(span=signal_period, adjust=False).mean()
# 计算MACD柱状
df['macd_histogram'] = (df['dif'] - df['dea']) * 2

# 计算KDJ指标
kdj_period = 9
kdj_slow_period = 3

# 计算RSV值
df['low_min'] = df['low'].rolling(window=kdj_period).min()
df['high_max'] = df['high'].rolling(window=kdj_period).max()
df['rsv'] = (df['close'] - df['low_min']) / (df['high_max'] - df['low_min']) * 100 if (df['high_max'] - df['low_min']).any() else 0

# 计算K、D、J值
df['k'] = df['rsv'].ewm(com=kdj_slow_period-1, adjust=False).mean()
df['d'] = df['k'].ewm(com=kdj_slow_period-1, adjust=False).mean()
df['j'] = 3 * df['k'] - 2 * df['d']

# 打印最近10条MACD和KDJ指标数据
print("ETHUSDT MACD和KDJ指标数据（最近10条）:")
print(df[['datetime', 'close', 'dif', 'dea', 'macd_histogram', 'k', 'd', 'j']].tail(10))
print("\n时间已统一为中国时区 (UTC+8)")

# 打印最新的MACD和KDJ数据
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

# KDJ买卖信号判断
# 获取当前和前一行的k、d值
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

# MACD买卖信号判断
# 获取当前和前一行的macd_histogram值
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