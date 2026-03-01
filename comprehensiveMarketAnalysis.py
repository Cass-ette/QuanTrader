import requests
import pandas as pd
import ta
import numpy as np
from datetime import datetime
from config import BINANCE_FUTURES_BASE_URL, DEFAULT_TIMEOUT, DEFAULT_SYMBOL


class ComprehensiveMarketAnalyzer:
    def __init__(self, symbol='BTCUSDT', interval='5m', limit=1000):
        self.symbol = symbol
        self.interval = interval
        self.limit = limit
        self.df = None
        self.signals = {}
        self.market_sentiment = {}
        
    def fetch_data(self):
        """从币安期货API获取K线数据"""
        print(f"正在获取 {self.symbol} {self.interval} 数据...")
        url = f'{BINANCE_FUTURES_BASE_URL}/fapi/v1/klines?symbol={self.symbol}&interval={self.interval}&limit={self.limit}'
        response = requests.get(url, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        response = response.json()
        
        # 转换为DataFrame
        self.df = pd.DataFrame(response)
        self.df = self.df.drop(columns=[5, 6, 7, 8, 9, 10, 11])
        self.df.columns = ['timestamp', 'open', 'high', 'low', 'close']
        
        # 转换数据类型
        for col in ['open', 'high', 'low', 'close']:
            self.df[col] = self.df[col].astype(float)
            
        # 转换时间戳为可读时间（统一使用中国时区 UTC+8）
        self.df['datetime'] = pd.to_datetime(self.df['timestamp'], unit='ms').dt.tz_localize('UTC').dt.tz_convert('Asia/Shanghai')
        print(f"成功获取 {len(self.df)} 条数据")
    
    def calculate_indicators(self):
        """计算所有技术指标"""
        if self.df is None:
            raise ValueError("请先调用fetch_data()获取数据")
        
        print("正在计算技术指标...")
        
        # 1. 移动平均线
        self.df['ma7'] = self.df['close'].rolling(window=7).mean()
        self.df['ma20'] = self.df['close'].rolling(window=20).mean()
        self.df['ma50'] = self.df['close'].rolling(window=50).mean()
        
        # 2. 布林带
        bbands = ta.volatility.BollingerBands(self.df['close'], window=20)
        self.df['bb_upper'] = bbands.bollinger_hband()
        self.df['bb_middle'] = bbands.bollinger_mavg()
        self.df['bb_lower'] = bbands.bollinger_lband()
        self.df['bb_width'] = (self.df['bb_upper'] - self.df['bb_lower']) / self.df['bb_middle'] * 100
        
        # 3. RSI
        self.df['rsi_14'] = ta.momentum.rsi(self.df['close'], window=14)
        self.df['rsi_7'] = ta.momentum.rsi(self.df['close'], window=7)
        
        # 4. MACD
        macd = ta.trend.MACD(self.df['close'])
        self.df['macd_line'] = macd.macd()
        self.df['signal_line'] = macd.macd_signal()
        self.df['macd_hist'] = macd.macd_diff()
        
        # 5. KDJ (手动实现)
        self._calculate_kdj()
        
        print("技术指标计算完成")
    
    def _calculate_kdj(self):
        """计算KDJ指标"""
        n = 9  # KDJ周期
        m1 = 3  # K平滑因子
        m2 = 3  # D平滑因子
        
        # 计算RSV值
        self.df['low_min'] = self.df['low'].rolling(window=n).min()
        self.df['high_max'] = self.df['high'].rolling(window=n).max()
        
        # 避免除以零错误
        self.df['rsv'] = 50.0  # 默认值
        valid_mask = (self.df['high_max'] - self.df['low_min']) > 0
        self.df.loc[valid_mask, 'rsv'] = ((self.df.loc[valid_mask, 'close'] - self.df.loc[valid_mask, 'low_min']) / 
                                         (self.df.loc[valid_mask, 'high_max'] - self.df.loc[valid_mask, 'low_min'])) * 100
        
        # 计算K、D、J值（使用SMA计算）
        self.df['k'] = self.df['rsv'].rolling(window=m1).mean()
        self.df['d'] = self.df['k'].rolling(window=m2).mean()
        self.df['j'] = 3 * self.df['k'] - 2 * self.df['d']
    
    def analyze_trend(self):
        """分析市场趋势"""
        latest = self.df.iloc[-1]
        prev = self.df.iloc[-2] if len(self.df) > 1 else latest
        
        # 移动平均线趋势判断
        if latest['ma7'] > latest['ma20'] and latest['ma20'] > latest['ma50']:
            ma_trend = '强势上涨'
            ma_score = 3
        elif latest['ma7'] > latest['ma20']:
            ma_trend = '温和上涨'
            ma_score = 2
        elif latest['ma7'] < latest['ma20'] and latest['ma20'] < latest['ma50']:
            ma_trend = '强势下跌'
            ma_score = -3
        elif latest['ma7'] < latest['ma20']:
            ma_trend = '温和下跌'
            ma_score = -2
        else:
            ma_trend = '震荡'
            ma_score = 0
        
        # MACD趋势判断
        if latest['macd_hist'] > 0 and prev['macd_hist'] <= 0:
            macd_signal = '金叉上涨'
            macd_score = 3
        elif latest['macd_line'] > latest['signal_line']:
            macd_signal = '多头市场'
            macd_score = 2
        elif latest['macd_hist'] < 0 and prev['macd_hist'] >= 0:
            macd_signal = '死叉下跌'
            macd_score = -3
        elif latest['macd_line'] < latest['signal_line']:
            macd_signal = '空头市场'
            macd_score = -2
        else:
            macd_signal = '震荡'
            macd_score = 0
        
        # 综合趋势
        trend_score = ma_score + macd_score
        if trend_score >= 4:
            overall_trend = '强烈上涨'
        elif trend_score >= 1:
            overall_trend = '上涨'
        elif trend_score <= -4:
            overall_trend = '强烈下跌'
        elif trend_score <= -1:
            overall_trend = '下跌'
        else:
            overall_trend = '震荡'
        
        self.signals['trend'] = {
            'ma_trend': ma_trend,
            'macd_signal': macd_signal,
            'overall_trend': overall_trend,
            'score': trend_score
        }
    
    def analyze_momentum(self):
        """分析市场动量（超买超卖）"""
        latest = self.df.iloc[-1]
        
        # RSI分析
        if latest['rsi_14'] > 70:
            rsi_status = '超买'
            rsi_score = -3
        elif latest['rsi_14'] > 60:
            rsi_status = '偏强'
            rsi_score = -1
        elif latest['rsi_14'] < 30:
            rsi_status = '超卖'
            rsi_score = 3
        elif latest['rsi_14'] < 40:
            rsi_status = '偏弱'
            rsi_score = 1
        else:
            rsi_status = '中性'
            rsi_score = 0
        
        # KDJ分析
        if latest['j'] > 80:
            kdj_status = '超买'
            kdj_score = -3
        elif latest['j'] > 70:
            kdj_status = '偏强'
            kdj_score = -1
        elif latest['j'] < 20:
            kdj_status = '超卖'
            kdj_score = 3
        elif latest['j'] < 30:
            kdj_status = '偏弱'
            kdj_score = 1
        else:
            kdj_status = '中性'
            kdj_score = 0
        
        # 金叉死叉判断
        if latest['k'] > latest['d']:
            kdj_cross = '金叉'
            kdj_cross_score = 2
        elif latest['k'] < latest['d']:
            kdj_cross = '死叉'
            kdj_cross_score = -2
        else:
            kdj_cross = '平行'
            kdj_cross_score = 0
        
        momentum_score = rsi_score + kdj_score + kdj_cross_score
        
        self.signals['momentum'] = {
            'rsi_status': rsi_status,
            'kdj_status': kdj_status,
            'kdj_cross': kdj_cross,
            'score': momentum_score
        }
    
    def analyze_volatility(self):
        """分析市场波动性（基于布林带）"""
        latest = self.df.iloc[-1]
        
        # 布林带位置分析
        if latest['close'] >= latest['bb_upper']:
            bb_position = '上轨上方'
            bb_score = -2
        elif latest['close'] <= latest['bb_lower']:
            bb_position = '下轨下方'
            bb_score = 2
        elif latest['close'] >= latest['bb_middle']:
            bb_position = '中轨上方'
            bb_score = 1
        else:
            bb_position = '中轨下方'
            bb_score = -1
        
        # 布林带宽度分析（波动率）
        bb_width_avg = self.df['bb_width'].rolling(window=20).mean().iloc[-1]
        if latest['bb_width'] > bb_width_avg * 1.2:
            volatility_status = '高波动'
            volatility_score = 0  # 高波动中性，既可能突破也可能回调
        elif latest['bb_width'] < bb_width_avg * 0.8:
            volatility_status = '低波动（可能即将突破）'
            volatility_score = 1  # 低波动后可能有大行情
        else:
            volatility_status = '正常波动'
            volatility_score = 0
        
        volatility_total_score = bb_score + volatility_score
        
        self.signals['volatility'] = {
            'bb_position': bb_position,
            'volatility_status': volatility_status,
            'score': volatility_total_score
        }
    
    def generate_overall_sentiment(self):
        """生成综合市场情绪判断"""
        trend_score = self.signals['trend']['score']
        momentum_score = self.signals['momentum']['score']
        volatility_score = self.signals['volatility']['score']
        
        # 综合得分，给予趋势较高权重
        total_score = trend_score * 1.5 + momentum_score + volatility_score * 0.8
        
        # 判断市场情绪
        if total_score >= 7:
            sentiment = '强烈看多'
            confidence = '高'
        elif total_score >= 3:
            sentiment = '看多'
            confidence = '中'
        elif total_score <= -7:
            sentiment = '强烈看空'
            confidence = '高'
        elif total_score <= -3:
            sentiment = '看空'
            confidence = '中'
        else:
            sentiment = '中性'
            confidence = '低'
        
        self.market_sentiment = {
            'sentiment': sentiment,
            'confidence': confidence,
            'total_score': total_score,
            'trend_score': trend_score,
            'momentum_score': momentum_score,
            'volatility_score': volatility_score
        }
    
    def perform_ai_analysis(self):
        """执行AI增强分析
        基于现有技术指标，提供更深入的市场洞察和智能分析"""
        if self.df is None or len(self.signals) == 0:
            raise ValueError("请先调用calculate_indicators()和分析方法")
        
        latest = self.df.iloc[-1]
        # 获取足够的历史数据用于模式分析
        hist_data = self.df.dropna().tail(50).copy()
        
        ai_insights = {
            'indicator_divergence': {},
            'pattern_recognition': {},
            'market_structure': {},
            'risk_assessment': {},
            'smart_strategy': {}
        }
        
        # 1. 多指标协同分析和背离检测
        # RSI与价格背离检测
        price_change = (latest['close'] - hist_data['close'].iloc[-5]) / hist_data['close'].iloc[-5] * 100
        rsi_change = latest['rsi_14'] - hist_data['rsi_14'].iloc[-5]
        
        if price_change < -3 and rsi_change > 5:
            rsi_divergence = "RSI底背离：价格创新低但RSI未创新低，可能是反转信号"
            rsi_divergence_strength = "强"
        elif price_change > 3 and rsi_change < -5:
            rsi_divergence = "RSI顶背离：价格创新高但RSI未创新高，可能是反转信号"
            rsi_divergence_strength = "强"
        elif price_change < -1 and rsi_change > 2:
            rsi_divergence = "RSI轻微底背离"
            rsi_divergence_strength = "弱"
        elif price_change > 1 and rsi_change < -2:
            rsi_divergence = "RSI轻微顶背离"
            rsi_divergence_strength = "弱"
        else:
            rsi_divergence = "无明显RSI背离"
            rsi_divergence_strength = "无"
        
        ai_insights['indicator_divergence']['rsi'] = {
            'status': rsi_divergence,
            'strength': rsi_divergence_strength
        }
        
        # MACD与价格背离检测
        if len(hist_data) > 5:
            price_diff = latest['close'] - hist_data['close'].iloc[-5]
            macd_diff = latest['macd_hist'] - hist_data['macd_hist'].iloc[-5]
            
            if price_diff < 0 and macd_diff > 0:
                macd_divergence = "MACD底背离：价格下跌但MACD柱状图上升，可能是反转信号"
                macd_divergence_strength = "中"
            elif price_diff > 0 and macd_diff < 0:
                macd_divergence = "MACD顶背离：价格上涨但MACD柱状图下降，可能是反转信号"
                macd_divergence_strength = "中"
            else:
                macd_divergence = "无明显MACD背离"
                macd_divergence_strength = "无"
        else:
            macd_divergence = "数据不足，无法判断MACD背离"
            macd_divergence_strength = "无"
        
        ai_insights['indicator_divergence']['macd'] = {
            'status': macd_divergence,
            'strength': macd_divergence_strength
        }
        
        # 2. 历史模式识别（模拟）
        # 计算近期高低点
        recent_high = hist_data['high'].max()
        recent_low = hist_data['low'].min()
        recent_range = recent_high - recent_low
        
        # 识别可能的形态
        if (latest['close'] > hist_data['close'].iloc[:-1].mean() * 1.01 and 
            latest['close'] < recent_high * 1.005):
            pattern = "可能的突破形态：价格接近近期高点"
            pattern_probability = "中高"
        elif (latest['close'] < hist_data['close'].iloc[:-1].mean() * 0.99 and 
            latest['close'] > recent_low * 0.995):
            pattern = "可能的突破形态：价格接近近期低点"
            pattern_probability = "中高"
        elif abs(latest['close'] - hist_data['close'].mean()) < recent_range * 0.05:
            pattern = "整理形态：价格在近期波动区间中部"
            pattern_probability = "高"
        else:
            pattern = "趋势延续：价格沿当前方向移动"
            pattern_probability = "中"
        
        ai_insights['pattern_recognition'] = {
            'pattern': pattern,
            'probability': pattern_probability
        }
        
        # 3. 市场结构分析
        # 计算支撑/阻力位
        # 简单版本：使用近期高点低点作为关键位
        support_level = recent_low
        resistance_level = recent_high
        
        # 判断当前价格与关键位的关系
        if latest['close'] > resistance_level * 0.99:
            structure = "价格接近阻力位，可能面临回调或突破"
        elif latest['close'] < support_level * 1.01:
            structure = "价格接近支撑位，可能反弹或突破"
        else:
            structure = "价格在支撑阻力区间内运行"
        
        # 趋势通道分析
        if len(hist_data) > 20:
            # 简化的趋势斜率计算
            x = range(len(hist_data['close']))
            # 使用线性回归斜率判断趋势强度
            slope = np.polyfit(x, hist_data['close'], 1)[0]
            trend_strength = abs(slope) / recent_range * 1000  # 标准化趋势强度
            
            if trend_strength > 0.5:
                trend_strength_desc = "强趋势"
            elif trend_strength > 0.2:
                trend_strength_desc = "中等趋势"
            else:
                trend_strength_desc = "弱趋势或无趋势"
        else:
            trend_strength_desc = "数据不足，无法判断趋势强度"
        
        ai_insights['market_structure'] = {
            'structure': structure,
            'trend_strength': trend_strength_desc,
            'support': support_level,
            'resistance': resistance_level
        }
        
        # 4. 风险评估
        # 基于波动率和趋势计算风险分数
        volatility = hist_data['close'].pct_change().std() * 100
        
        if volatility > 0.5:
            volatility_risk = "高波动率，风险较高"
            risk_score = 7
        elif volatility > 0.2:
            volatility_risk = "中等波动率，风险适中"
            risk_score = 5
        else:
            volatility_risk = "低波动率，风险较低"
            risk_score = 3
        
        # 考虑趋势因素调整风险分数
        if self.signals['trend']['overall_trend'] in ['强烈上涨', '强烈下跌']:
            trend_risk = "强趋势，风险可控但需警惕反转"
            risk_score += 1
        elif self.signals['trend']['overall_trend'] == '震荡':
            trend_risk = "震荡市场，假突破风险高"
            risk_score += 2
        else:
            trend_risk = "趋势明确，风险中等"
        
        ai_insights['risk_assessment'] = {
            'volatility_risk': volatility_risk,
            'trend_risk': trend_risk,
            'risk_score': risk_score,  # 1-10分，越高风险越大
            'risk_level': '高' if risk_score > 7 else '中' if risk_score > 4 else '低'
        }
        
        # 5. 智能交易策略建议
        # 结合所有AI洞察提供更精细的策略
        smart_advice = []
        
        # 基于背离
        if rsi_divergence_strength == '强' or macd_divergence_strength == '中':
            if '底背离' in rsi_divergence or '底背离' in macd_divergence:
                smart_advice.append("背离信号强烈，建议关注潜在的反转机会，可以考虑设置分批买入策略")
            elif '顶背离' in rsi_divergence or '顶背离' in macd_divergence:
                smart_advice.append("背离信号强烈，建议减仓或设置保护性止损，关注潜在的回调风险")
        
        # 基于市场结构
        if structure.startswith("价格接近阻力位"):
            if self.signals['momentum']['rsi_status'] == '超买':
                smart_advice.append("价格接近阻力位且RSI超买，谨慎追多，可考虑减仓或小仓位做空")
            else:
                smart_advice.append("价格接近阻力位，可设置突破确认后的跟进策略")
        elif structure.startswith("价格接近支撑位"):
            if self.signals['momentum']['rsi_status'] == '超卖':
                smart_advice.append("价格接近支撑位且RSI超卖，可考虑小仓位做多")
            else:
                smart_advice.append("价格接近支撑位，关注反弹机会")
        
        # 基于风险评估
        if ai_insights['risk_assessment']['risk_level'] == '高':
            smart_advice.append(f"当前市场风险评级为{ai_insights['risk_assessment']['risk_level']}，建议降低仓位，严格控制止损")
        elif ai_insights['risk_assessment']['risk_level'] == '低':
            smart_advice.append(f"当前市场风险评级为{ai_insights['risk_assessment']['risk_level']}，可以适当提高仓位")
        
        # 基于趋势强度
        if trend_strength_desc == "强趋势":
            if self.signals['trend']['overall_trend'] in ['上涨', '强烈上涨']:
                smart_advice.append("强上升趋势，可采用均线跟踪策略，回调至短期均线附近考虑加仓")
            elif self.signals['trend']['overall_trend'] in ['下跌', '强烈下跌']:
                smart_advice.append("强下降趋势，反弹至短期均线附近考虑加仓做空")
        
        # 如果没有特定建议，提供一般建议
        if not smart_advice:
            smart_advice.append("根据综合分析，建议按照常规交易策略执行，严格控制风险")
        
        ai_insights['smart_strategy'] = {
            'advice': smart_advice,
            'time_horizon': '短期' if trend_strength_desc == "弱趋势或无趋势" else '中期',
            'confidence': self.market_sentiment['confidence']
        }
        
        # 保存AI分析结果
        self.ai_insights = ai_insights
    
    def generate_trading_advice(self):
        """生成交易建议"""
        sentiment = self.market_sentiment['sentiment']
        confidence = self.market_sentiment['confidence']
        latest = self.df.iloc[-1]
        
        if sentiment == '强烈看多':
            advice = f"强烈看多信号，建议：\n1. 考虑建立多头头寸\n2. 设置较小止损（如当前价格的1-2%）\n3. 关注布林带上轨突破情况"
        elif sentiment == '看多':
            advice = f"看多信号，建议：\n1. 可尝试轻仓做多\n2. 设置合理止损\n3. 观察RSI是否有回落再入场机会"
        elif sentiment == '强烈看空':
            advice = f"强烈看空信号，建议：\n1. 考虑建立空头头寸\n2. 设置较小止损（如当前价格的1-2%）\n3. 关注布林带下轨突破情况"
        elif sentiment == '看空':
            advice = f"看空信号，建议：\n1. 可尝试轻仓做空\n2. 设置合理止损\n3. 观察RSI是否有反弹再入场机会"
        else:  # 中性
            # 基于具体指标给出更细致的建议
            if latest['rsi_14'] < 30:
                advice = f"市场中性，但RSI显示超卖，建议：\n1. 可考虑小仓位试探性做多\n2. 设置严格止损\n3. 等待MACD金叉确认"
            elif latest['rsi_14'] > 70:
                advice = f"市场中性，但RSI显示超买，建议：\n1. 可考虑小仓位试探性做空\n2. 设置严格止损\n3. 等待MACD死叉确认"
            elif self.df['bb_width'].iloc[-1] < self.df['bb_width'].rolling(window=20).mean().iloc[-1] * 0.8:
                advice = f"市场中性，但布林带收窄，建议：\n1. 密切关注，准备突破行情\n2. 可设置双向突破单\n3. 突破确认后再入场"
            else:
                advice = "市场处于震荡整理阶段，建议：\n1. 观望为主，避免频繁交易\n2. 等待明确信号出现\n3. 可考虑高抛低吸策略"
        
        return advice
    
    def run_analysis(self):
        """运行完整分析流程"""
        self.fetch_data()
        self.calculate_indicators()
        self.analyze_trend()
        self.analyze_momentum()
        self.analyze_volatility()
        self.generate_overall_sentiment()
        self.perform_ai_analysis()
    
    def display_results(self):
        """显示分析结果"""
        if not self.market_sentiment or not hasattr(self, 'ai_insights'):
            raise ValueError("请先调用run_analysis()进行分析")
        
        latest = self.df.iloc[-1]
        
        print("\n" + "="*60)
        print(f"{self.symbol} 市场综合分析报告")
        # 分析时间（中国时区 UTC+8）
        print(f"分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (UTC+8)")
        # 数据时间（已转换为中国时区 UTC+8）
        print(f"数据时间: {latest['datetime'].strftime('%Y-%m-%d %H:%M:%S')} (UTC+8)")
        print(f"最新价格: {latest['close']:.2f}")
        print("="*60)
        
        # 显示各项指标分析
        print("\n【趋势分析】")
        print(f"- 移动平均线状态: {self.signals['trend']['ma_trend']}")
        print(f"- MACD信号: {self.signals['trend']['macd_signal']}")
        print(f"- 综合趋势判断: {self.signals['trend']['overall_trend']} (得分: {self.signals['trend']['score']})")
        
        print("\n【动量分析】")
        print(f"- RSI(14)状态: {self.signals['momentum']['rsi_status']} ({latest['rsi_14']:.2f})")
        print(f"- KDJ状态: {self.signals['momentum']['kdj_status']} (K:{latest['k']:.2f}, D:{latest['d']:.2f}, J:{latest['j']:.2f})")
        print(f"- KDJ交叉: {self.signals['momentum']['kdj_cross']}")
        print(f"- 动量综合得分: {self.signals['momentum']['score']}")
        
        print("\n【波动性分析】")
        print(f"- 布林带位置: {self.signals['volatility']['bb_position']}")
        print(f"- 波动率状态: {self.signals['volatility']['volatility_status']}")
        print(f"- 波动性得分: {self.signals['volatility']['score']}")
        
        print("\n【市场情绪总结】")
        print(f"- 综合判断: {self.market_sentiment['sentiment']}")
        print(f"- 置信度: {self.market_sentiment['confidence']}")
        print(f"- 综合得分: {self.market_sentiment['total_score']:.2f}")
        
        # 显示AI增强分析
        print("\n" + "="*60)
        print("【AI增强分析】")
        print("="*60)
        
        # 指标背离分析
        print("\n【指标背离分析】")
        print(f"- RSI背离: {self.ai_insights['indicator_divergence']['rsi']['status']}")
        print(f"- MACD背离: {self.ai_insights['indicator_divergence']['macd']['status']}")
        
        # 模式识别
        print("\n【模式识别】")
        print(f"- 识别模式: {self.ai_insights['pattern_recognition']['pattern']}")
        print(f"- 识别概率: {self.ai_insights['pattern_recognition']['probability']}")
        
        # 市场结构分析
        print("\n【市场结构分析】")
        print(f"- 当前结构: {self.ai_insights['market_structure']['structure']}")
        print(f"- 趋势强度: {self.ai_insights['market_structure']['trend_strength']}")
        print(f"- 支撑位: {self.ai_insights['market_structure']['support']:.2f}")
        print(f"- 阻力位: {self.ai_insights['market_structure']['resistance']:.2f}")
        
        # 风险评估
        print("\n【风险评估】")
        print(f"- 波动率风险: {self.ai_insights['risk_assessment']['volatility_risk']}")
        print(f"- 趋势风险: {self.ai_insights['risk_assessment']['trend_risk']}")
        print(f"- 风险等级: {self.ai_insights['risk_assessment']['risk_level']} (风险分数: {self.ai_insights['risk_assessment']['risk_score']}/10)")
        
        # 智能策略建议
        print("\n【AI智能交易策略】")
        print(f"- 投资周期建议: {self.ai_insights['smart_strategy']['time_horizon']}")
        print(f"- 策略置信度: {self.ai_insights['smart_strategy']['confidence']}")
        print("- AI策略建议:")
        for i, suggestion in enumerate(self.ai_insights['smart_strategy']['advice'], 1):
            print(f"  {i}. {suggestion}")
        
        print("\n【常规交易建议】")
        advice = self.generate_trading_advice()
        print(advice)
        print("\n" + "="*60)
        print("免责声明: 以上分析仅供参考，不构成投资建议。市场有风险，交易需谨慎。")
        print("AI分析基于历史数据和统计模型，不保证预测准确性。")

# 主函数
if __name__ == "__main__":
    # 创建分析器实例
    analyzer = ComprehensiveMarketAnalyzer(
        symbol=DEFAULT_SYMBOL,
        interval='5m',     # 可更改为其他时间周期
        limit=1000         # 数据量
    )
    
    # 运行分析并显示结果
    analyzer.run_analysis()
    analyzer.display_results()