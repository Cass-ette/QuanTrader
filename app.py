from flask import Flask, request, jsonify, send_from_directory, render_template
import subprocess
import os
import time
from datetime import datetime

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

ALLOWED_SCRIPTS = {
    'check_positions': 'checkPositions.py',
    'check_balance': 'check_futures_balance.py',
    'market_long': 'marketLong.py',
    'market_short': 'marketShort.py',
    'close_long': 'closeLong.py',
    'close_short': 'closeShort.py',
    'get_rsi': 'getRSI.py',
    'get_macd': 'getKDJ_MACD.py',
    'get_moving_average': 'getMovingAverage.py',
    'get_bollinger_bands': 'getBollingerBands.py',
    'trend_strategy': 'trendVolatilityStrategy.py',
    'volume_price_strategy': 'volumePriceStrategy.py',
    'grid_trading': 'gridTradingStrategy.py',
    'moving_average_144': 'movingAverage144Strategy.py'
}

API_PARAM_SCRIPTS = {'moving_average_144'}

# 参数顺序必须与脚本 sys.argv 的读取顺序一致
SCRIPT_PARAMS = {
    'market_long': [
        {'name': 'symbol', 'type': 'text', 'label': '交易对', 'default': 'BTCUSDT'},
        {'name': 'quantity', 'type': 'number', 'label': '数量', 'default': 0.001},
        {'name': 'leverage', 'type': 'number', 'label': '杠杆倍数', 'default': 10}
    ],
    'market_short': [
        {'name': 'symbol', 'type': 'text', 'label': '交易对', 'default': 'BTCUSDT'},
        {'name': 'quantity', 'type': 'number', 'label': '数量', 'default': 0.001},
        {'name': 'leverage', 'type': 'number', 'label': '杠杆倍数', 'default': 10}
    ],
    'close_long': [
        {'name': 'symbol', 'type': 'text', 'label': '交易对', 'default': 'BTCUSDT'}
    ],
    'close_short': [
        {'name': 'symbol', 'type': 'text', 'label': '交易对', 'default': 'BTCUSDT'}
    ],
    'get_rsi': [
        {'name': 'symbol', 'type': 'text', 'label': '交易对', 'default': 'BTCUSDT'},
        {'name': 'interval', 'type': 'select', 'label': '时间周期', 'options': ['1h', '4h', '1d'], 'default': '4h'},
        {'name': 'period', 'type': 'number', 'label': 'RSI周期', 'default': 14}
    ],
    'get_macd': [
        {'name': 'symbol', 'type': 'text', 'label': '交易对', 'default': 'BTCUSDT'},
        {'name': 'interval', 'type': 'select', 'label': '时间周期', 'options': ['1h', '4h', '1d'], 'default': '4h'}
    ],
    'get_moving_average': [
        {'name': 'symbol', 'type': 'text', 'label': '交易对', 'default': 'BTCUSDT'},
        {'name': 'interval', 'type': 'select', 'label': '时间周期', 'options': ['1h', '4h', '1d'], 'default': '4h'}
    ],
    'get_bollinger_bands': [
        {'name': 'symbol', 'type': 'text', 'label': '交易对', 'default': 'BTCUSDT'},
        {'name': 'interval', 'type': 'select', 'label': '时间周期', 'options': ['1h', '4h', '1d'], 'default': '4h'},
        {'name': 'period', 'type': 'number', 'label': '周期', 'default': 20},
        {'name': 'std_dev', 'type': 'number', 'label': '标准差倍数', 'default': 2}
    ],
    'trend_strategy': [
        {'name': 'symbol', 'type': 'text', 'label': '交易对', 'default': 'BTCUSDT'},
        {'name': 'interval', 'type': 'select', 'label': '时间周期', 'options': ['1h', '4h', '1d'], 'default': '4h'},
        {'name': 'risk_percent', 'type': 'number', 'label': '风险比例(%)', 'default': 2}
    ],
    'volume_price_strategy': [
        {'name': 'symbol', 'type': 'text', 'label': '交易对', 'default': 'BTCUSDT'},
        {'name': 'testnet', 'type': 'checkbox', 'label': '使用测试网络', 'default': False}
    ],
    'grid_trading': [
        {'name': 'symbol', 'type': 'text', 'label': '交易对', 'default': 'BTCUSDT'},
        {'name': 'testnet', 'type': 'checkbox', 'label': '使用测试网络', 'default': False},
        {'name': 'levels', 'type': 'number', 'label': '网格档位数量', 'default': 10},
        {'name': 'range', 'type': 'number', 'label': '网格区间百分比(%)', 'default': 8}
    ],
    'moving_average_144': [
        {'name': 'symbol', 'type': 'text', 'label': '交易对', 'default': 'BTCUSDT'}
    ]
}


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(os.path.join(BASE_DIR, 'static'), filename)


@app.route('/run_script', methods=['POST'])
def run_script():
    script_key = request.json.get('script')
    params = request.json.get('params', {})

    if script_key not in ALLOWED_SCRIPTS:
        return jsonify({'status': 'error', 'message': f'不支持的脚本: {script_key}'})

    script_path = os.path.join(BASE_DIR, ALLOWED_SCRIPTS[script_key])

    if not os.path.exists(script_path):
        return jsonify({'status': 'error', 'message': f'脚本文件不存在: {script_path}'})

    try:
        cmd = ['python', script_path]

        if script_key in SCRIPT_PARAMS:
            for param_def in SCRIPT_PARAMS[script_key]:
                name = param_def['name']
                if name in params:
                    cmd.append(str(params[name]))

        start_time = time.time()

        env = os.environ.copy()
        if script_key in API_PARAM_SCRIPTS:
            if 'api_key' in params:
                env['API_KEY'] = params['api_key']
            if 'api_secret' in params:
                env['API_SECRET'] = params['api_secret']

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=BASE_DIR,
            env=env
        )

        output = []
        for line in iter(process.stdout.readline, ''):
            output.append(line.strip())

        process.wait()
        end_time = time.time()

        stderr = process.stderr.read()
        if stderr:
            return jsonify({
                'status': 'error',
                'message': '脚本执行出错',
                'output': '\n'.join(output),
                'error': stderr,
                'execution_time': f"{end_time - start_time:.2f}秒"
            })

        # BUG FIX: 原代码此处缩进错误，导致成功返回路径被嵌套在 if stderr 内部
        log_params = {k: v for k, v in params.items() if k not in ['api_key', 'api_secret']}
        print(f"脚本 {script_key} 执行成功，参数: {log_params}")

        return jsonify({
            'status': 'success',
            'message': '脚本执行成功',
            'output': '\n'.join(output),
            'execution_time': f"{end_time - start_time:.2f}秒"
        })

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'执行脚本时发生异常: {str(e)}'
        })


@app.route('/get_account_info')
def get_account_info():
    """获取账户基本信息（资金和持仓概览）"""
    try:
        balance_info = "未获取到账户余额信息"
        positions_info = "未获取到持仓信息"

        try:
            balance_process = subprocess.run(
                ['python', 'check_futures_balance.py'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=BASE_DIR,
                timeout=30
            )
            balance_info = balance_process.stdout
            if balance_process.stderr:
                print(f"check_futures_balance.py 错误输出: {balance_process.stderr}")
        except subprocess.TimeoutExpired:
            balance_info = "获取账户余额超时"
        except Exception as e:
            balance_info = f"获取账户余额时出错: {str(e)}"

        try:
            positions_process = subprocess.run(
                ['python', 'checkPositions.py'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=BASE_DIR,
                timeout=30
            )
            positions_info = positions_process.stdout
            if positions_process.stderr:
                print(f"checkPositions.py 错误输出: {positions_process.stderr}")
        except subprocess.TimeoutExpired:
            positions_info = "获取持仓信息超时"
        except Exception as e:
            positions_info = f"获取持仓信息时出错: {str(e)}"

        return jsonify({
            'status': 'success',
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'balance_info': balance_info,
            'positions_info': positions_info
        })
    except Exception as e:
        # BUG FIX: 原代码有两个连续的 except Exception，第二个永远不会执行
        print(f"get_account_info路由异常: {str(e)}")
        return jsonify({
            'status': 'error',
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'message': f"获取账户信息时发生错误: {str(e)}",
            'balance_info': "",
            'positions_info': ""
        }), 500


if __name__ == '__main__':
    print("Starting Flask server...")
    port = int(os.environ.get('PORT', 8888))
    print(f"Visit http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=True)
