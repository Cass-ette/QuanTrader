import time
import traceback
from datetime import datetime
from binance_client import signed_request, public_request


def get_all_positions():
    """获取账户所有持仓信息"""
    try:
        data = signed_request('GET', '/fapi/v2/positionRisk')
        print(f"成功获取到数据，数据长度: {len(data) if isinstance(data, list) else '非列表类型'}")
        return data
    except Exception as e:
        print(f"请求异常: {str(e)}")
        traceback.print_exc()
        return []


def test_time_sync():
    """测试时间同步"""
    try:
        data = public_request('/fapi/v1/time')
        server_time = data.get('serverTime', 0)
        local_time = int(round(time.time() * 1000))
        diff = abs(server_time - local_time)
        print(f"时间同步测试: 本地时间={local_time}, 服务器时间={server_time}")
        print(f"时间差异: {diff}ms")
        if diff > 10000:
            print(f"警告: 时间差异超过10秒，可能导致API请求失败")
        return True
    except Exception as e:
        print(f"时间同步测试异常: {str(e)}")
        return False


def check_positions():
    """检查并显示所有持仓信息"""
    print('正在查询账户持仓信息...')
    print(f'查询时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} (UTC+8)')
    print('-' * 80)

    print("执行时间同步测试...")
    test_time_sync()
    print("-" * 50)

    positions = get_all_positions()

    if not positions:
        print('未获取到持仓信息或无持仓')
        return

    active_positions = [p for p in positions if float(p['positionAmt']) != 0]

    if not active_positions:
        print('当前没有任何持仓')
    else:
        print(f'发现 {len(active_positions)} 个有持仓的交易对:')
        print('-' * 80)
        print('{:<10} {:<10} {:<15} {:<15} {:<15} {:<10}'.format(
            '交易对', '持仓方向', '持仓数量', '平均成本', '未实现盈亏', '杠杆倍率'))
        print('-' * 80)

        for pos in active_positions:
            symbol = pos['symbol']
            position_amt = float(pos['positionAmt'])
            direction = '多头' if position_amt > 0 else '空头'

            print('{:<10} {:<10} {:<15.6f} {:<15.2f} {:<15.2f} {:<10}'.format(
                symbol,
                direction,
                abs(position_amt),
                float(pos['entryPrice']),
                float(pos['unRealizedProfit']),
                float(pos['leverage'])
            ))

    print('-' * 80)
    print('查询完成')


if __name__ == '__main__':
    check_positions()
