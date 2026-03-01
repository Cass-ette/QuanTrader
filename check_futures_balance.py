from datetime import datetime
from binance_client import signed_request


def get_futures_account_info():
    """获取合约账户信息，包括余额"""
    try:
        return signed_request('GET', '/fapi/v2/account')
    except Exception as e:
        print(f"获取账户信息异常: {str(e)}")
        return None


def check_futures_balance():
    """检查并显示合约账户可用资金"""
    print('正在查询合约账户资金信息...')
    print(f'查询时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} (UTC+8)')
    print('-' * 60)

    account_info = get_futures_account_info()

    if not account_info:
        print('未获取到账户信息')
        return

    print("合约账户资金信息:")
    print('-' * 60)

    if 'positions' in account_info:
        print(f"总持仓数: {len([p for p in account_info['positions'] if float(p['positionAmt']) != 0])}")

    # BUG FIX: 原代码 'if assets' 错误嵌套在 'if positions' 内部
    usdt_asset = None
    if 'assets' in account_info:
        print("\n资产详情 (仅显示USDT):")
        print('-' * 80)
        print('{:<10} {:<18} {:<18} {:<18}'.format('资产', '总资产(USDT)', '可用资产(USDT)', '已用保证金(USDT)'))
        print('-' * 80)

        for asset in account_info['assets']:
            if asset.get('asset') == 'USDT':
                usdt_asset = asset
                break

        if usdt_asset:
            wallet_balance = float(usdt_asset.get('walletBalance', 0))
            available_balance = float(usdt_asset.get('availableBalance', 0))
            margin_balance = float(usdt_asset.get('marginBalance', 0))
            used_margin = margin_balance - available_balance

            print('{:<10} {:<18.4f} {:<18.4f} {:<18.4f}'.format(
                'USDT',
                wallet_balance,
                available_balance,
                used_margin
            ))
        else:
            print("未找到USDT资产信息")

        print("\n注意：其他资产的异常数据是API返回的，不影响您的实际USDT资产")
    else:
        print("\n账户余额:")
        print(f"总资产: {account_info.get('totalWalletBalance', 'N/A')}")
        print(f"可用资产: {account_info.get('availableBalance', 'N/A')}")
        print(f"已用保证金: {account_info.get('totalMarginBalance', 'N/A')}")

    print('\n' + '-' * 80)
    print("账户状态信息 (精确到小数点后四位):")

    try:
        total_margin_balance = float(account_info.get('totalMarginBalance', 0))
        total_unrealized_profit = float(account_info.get('totalUnrealizedProfit', 0))
        total_maintenance_margin = float(account_info.get('totalMaintenanceMargin', 0))

        print(f"账户权益: {total_margin_balance:.4f} USDT")
        print(f"未实现盈亏: {total_unrealized_profit:.4f} USDT")
        print(f"维持保证金: {total_maintenance_margin:.4f} USDT")

        if usdt_asset:
            wallet = float(usdt_asset.get('walletBalance', 1))
            if wallet > 0:
                available_percent = (float(usdt_asset.get('availableBalance', 0)) / wallet) * 100
                print(f"可用资金比例: {available_percent:.2f}%")
    except Exception as e:
        print(f"显示账户指标时出错: {str(e)}")

    print('-' * 80)


if __name__ == '__main__':
    check_futures_balance()
