"""
评分制选股策略 V5.1
========================
基于多指标评分系统的选股策略，满分100分，50分以上入选

评分标准：
1. 均线多头（MA5 > MA20）：+20分
2. BOLL开口（价格 > BOLL上轨 × 0.95）：+15分
3. MACD强势（DIF > 0）：+15分
4. 涨幅条件（2% ≤ 涨幅 ≤ 8%）：+15分
5. 量能放大（量比 > 1.5）：+10分
6. 成交活跃（成交额 > 1亿）：+10分
7. MACD金叉（MACD柱 > 0）：+15分

入选门槛：50分
"""

import numpy as np
import pandas as pd
import json
import os
import sys
import re
import requests
from datetime import datetime
from jinja2 import Template
import time

# ============================================================
# HTTP 基础设施
# ============================================================

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.0.0 Safari/537.36'
    ),
}
SESSION = requests.Session()
SESSION.headers.update(HEADERS)

# PushPlus配置
PUSHPLUS_TOKEN = "38e3c83f6d9447c4b0b9f304be03cc46"
PUSHPLUS_URL = "http://www.pushplus.plus/send"


# ============================================================
# PushPlus推送功能
# ============================================================

def send_pushplus(title, content, template='html'):
    """
    通过PushPlus发送推送消息
    :param title: 消息标题
    :param content: 消息内容
    :param template: 消息模板类型（html/txt/json等）
    """
    try:
        data = {
            'token': PUSHPLUS_TOKEN,
            'title': title,
            'content': content,
            'template': template
        }
        response = requests.post(PUSHPLUS_URL, json=data, timeout=30)
        result = response.json()
        if result.get('code') == 200:
            print(f"  ✓ PushPlus推送成功")
            return True
        else:
            print(f"  ✗ PushPlus推送失败: {result.get('msg', '未知错误')}")
            return False
    except Exception as e:
        print(f"  ✗ PushPlus推送异常: {str(e)}")
        return False


# ============================================================
# 数据获取层
# ============================================================

def get_all_a_stocks():
    """通过腾讯实时行情批量探测有效A股"""
    print("[1/5] 获取A股股票列表...")

    code_ranges = []
    code_ranges += [f"sz{str(i).zfill(6)}" for i in range(1, 1000)]
    code_ranges += [f"sz{str(i).zfill(6)}" for i in range(2001, 3000)]
    code_ranges += [f"sz{str(i).zfill(6)}" for i in range(300001, 302000)]
    code_ranges += [f"sh{str(i).zfill(6)}" for i in range(600000, 602000)]
    code_ranges += [f"sh{str(i).zfill(6)}" for i in range(603000, 604000)]
    code_ranges += [f"sh{str(i).zfill(6)}" for i in range(605000, 606000)]
    code_ranges += [f"sh{str(i).zfill(6)}" for i in range(688001, 690000)]

    all_stocks = []
    batch_size = 80

    for i in range(0, len(code_ranges), batch_size):
        batch = code_ranges[i:i + batch_size]
        query = ','.join(batch)
        url = f"https://qt.gtimg.cn/q={query}"
        try:
            resp = SESSION.get(url, timeout=20)
            if resp.status_code != 200:
                continue
            text = resp.text
            for entry in text.split(';'):
                entry = entry.strip()
                if not entry:
                    continue
                match = re.search(r'v_(\w+)="(\d+)~(.+?)~(\d+)~([^~]*)~', entry)
                if not match:
                    continue
                name = match.group(3).strip()
                code = match.group(4)
                price_str = match.group(5)
                if not name or not code or len(code) != 6:
                    continue
                if 'ST' in name or '退' in name or 'PT' in name:
                    continue
                try:
                    price = float(price_str)
                    if price <= 0:
                        continue
                except (ValueError, TypeError):
                    continue
                all_stocks.append({'代码': code, '名称': name})
        except Exception:
            continue

        if (i // batch_size) % 20 == 0 and i > 0:
            print(f"    已探测 {i}/{len(code_ranges)}，有效 {len(all_stocks)} 只...")
        time.sleep(0.05)

    df = pd.DataFrame(all_stocks)
    if df.empty:
        print("  股票列表获取失败!")
        return df
    df = df.drop_duplicates(subset='代码').reset_index(drop=True)
    print(f"  共 {len(df)} 只股票待筛选")
    return df


def get_realtime_data(stock_code):
    """获取股票实时行情数据（用于评分计算）"""
    if stock_code.startswith(('60', '68')):
        symbol = f"sh{stock_code}"
    else:
        symbol = f"sz{stock_code}"
    
    url = f"https://qt.gtimg.cn/q={symbol}"
    try:
        resp = SESSION.get(url, timeout=15)
        text = resp.text.strip()
        match = re.search(r'"(.+)"', text)
        if not match:
            return None
        parts = match.group(1).split('~')
        if len(parts) < 40:
            return None
        
        price = float(parts[3])
        prev_close = float(parts[4])
        open_price = float(parts[5])
        volume = float(parts[6])  # 成交量（手）
        turnover = float(parts[37])  # 成交额（万元）
        high = float(parts[33])
        low = float(parts[34])
        
        # 计算涨幅
        change_pct = (price - prev_close) / prev_close * 100 if prev_close > 0 else 0
        
        # 计算量比（当前成交量 / 过去5日平均成交量）
        # 简化处理：使用parts[38]作为量比（如果可用）
        volume_ratio = float(parts[49]) if len(parts) > 49 and parts[49] else 0
        
        return {
            'code': stock_code,
            'price': price,
            'prev_close': prev_close,
            'open': open_price,
            'high': high,
            'low': low,
            'volume': volume,
            'turnover': turnover,
            'change_pct': round(change_pct, 2),
            'volume_ratio': volume_ratio,
        }
    except Exception as e:
        return None


def _fetch_kline(symbol, period, count):
    """
    通用K线获取（腾讯财经前复权接口）
    period: 'week' / 'month' / 'day'
    返回 DataFrame(date, open, close, high, low, vol) 或空 DataFrame
    """
    period_map = {'week': 'qfqweek', 'month': 'qfqmonth', 'day': 'qfqday'}
    qfq_key = period_map.get(period, f'qfq{period}')

    url = (
        f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?"
        f"_var=kline_{period}qfq&param={symbol},{period},,,{count},qfq"
    )
    try:
        resp = SESSION.get(url, timeout=20)
        if resp.status_code != 200:
            return pd.DataFrame()
        text = resp.text.strip()
        if '=' in text:
            text = text.split('=', 1)[1]
        data = json.loads(text)
        if data.get('code') != 0:
            return pd.DataFrame()
        stock_data = data.get('data', {})
        if not stock_data:
            return pd.DataFrame()
        first_key = list(stock_data.keys())[0]
        klines = stock_data[first_key].get(qfq_key, [])
        if not klines:
            return pd.DataFrame()
        rows = []
        for k in klines:
            if len(k) >= 6:
                try:
                    rows.append({
                        'date':  k[0],
                        'open':  float(k[1]),
                        'close': float(k[2]),
                        'high':  float(k[3]),
                        'low':   float(k[4]),
                        'vol':   float(k[5]),
                    })
                except (ValueError, IndexError):
                    continue
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        df = df.sort_values('date').reset_index(drop=True)
        return df
    except Exception:
        return pd.DataFrame()


def get_kline(stock_code, period, count):
    """统一接口：按股票代码 + 周期获取K线"""
    if stock_code.startswith(('60', '68')):
        symbol = f"sh{stock_code}"
    else:
        symbol = f"sz{stock_code}"
    return _fetch_kline(symbol, period, count)


# ============================================================
# 技术指标计算工具
# ============================================================

def ema(series, n):
    return series.ewm(span=n, adjust=False).mean()

def ma(series, n):
    return series.rolling(window=n, min_periods=n).mean()

def std_dev(series, n):
    return series.rolling(window=n, min_periods=n).std(ddof=0)


# ============================================================
# 评分策略计算
# ============================================================

def calculate_score(stock_code, realtime_data):
    """
    计算股票评分（满分100分）
    返回：(总分, 详细得分字典) 或 (0, None)
    """
    if not realtime_data:
        return 0, None
    
    score = 0
    details = {}
    
    # 获取日K线数据（用于计算技术指标）
    df_day = get_kline(stock_code, 'day', 60)
    if df_day.empty or len(df_day) < 30:
        return 0, None
    
    close = df_day['close']
    high = df_day['high']
    low = df_day['low']
    current_price = realtime_data['price']
    
    # 1. 均线多头（MA5 > MA20）：+20分
    ma5 = ma(close, 5).iloc[-1]
    ma20 = ma(close, 20).iloc[-1]
    if pd.notna(ma5) and pd.notna(ma20) and ma5 > ma20:
        score += 20
        details['均线多头'] = f"✓ +20分 (MA5:{ma5:.2f} > MA20:{ma20:.2f})"
    else:
        details['均线多头'] = f"✗ 0分 (MA5:{ma5:.2f} ≤ MA20:{ma20:.2f})"
    
    # 2. BOLL开口（价格 > BOLL上轨 × 0.95）：+15分
    mid = ma(close, 20).iloc[-1]
    std = std_dev(close, 20).iloc[-1]
    upper = mid + 2 * std
    if pd.notna(upper) and current_price > upper * 0.95:
        score += 15
        details['BOLL开口'] = f"✓ +15分 (价格:{current_price:.2f} > 上轨×0.95:{upper*0.95:.2f})"
    else:
        details['BOLL开口'] = f"✗ 0分 (价格:{current_price:.2f} ≤ 上轨×0.95:{upper*0.95:.2f})"
    
    # 3. MACD强势（DIF > 0）：+15分
    dif = ema(close, 12) - ema(close, 26)
    dif_val = dif.iloc[-1]
    if pd.notna(dif_val) and dif_val > 0:
        score += 15
        details['MACD强势'] = f"✓ +15分 (DIF:{dif_val:.4f} > 0)"
    else:
        details['MACD强势'] = f"✗ 0分 (DIF:{dif_val:.4f} ≤ 0)"
    
    # 4. 涨幅条件（2% ≤ 涨幅 ≤ 8%）：+15分
    change_pct = realtime_data['change_pct']
    if 2 <= change_pct <= 8:
        score += 15
        details['涨幅条件'] = f"✓ +15分 (涨幅:{change_pct:.2f}%)"
    else:
        details['涨幅条件'] = f"✗ 0分 (涨幅:{change_pct:.2f}%)"
    
    # 5. 量能放大（量比 > 1.5）：+10分
    volume_ratio = realtime_data['volume_ratio']
    if volume_ratio > 1.5:
        score += 10
        details['量能放大'] = f"✓ +10分 (量比:{volume_ratio:.2f})"
    else:
        details['量能放大'] = f"✗ 0分 (量比:{volume_ratio:.2f})"
    
    # 6. 成交活跃（成交额 > 1亿）：+10分
    turnover_yi = realtime_data['turnover'] / 10000  # 万元转亿元
    if turnover_yi > 1:
        score += 10
        details['成交活跃'] = f"✓ +10分 (成交额:{turnover_yi:.2f}亿)"
    else:
        details['成交活跃'] = f"✗ 0分 (成交额:{turnover_yi:.2f}亿)"
    
    # 7. MACD金叉（MACD柱 > 0）：+15分
    dea = ema(dif, 9)
    macd_bar = (dif - dea).iloc[-1] * 2
    if pd.notna(macd_bar) and macd_bar > 0:
        score += 15
        details['MACD金叉'] = f"✓ +15分 (MACD柱:{macd_bar:.4f})"
    else:
        details['MACD金叉'] = f"✗ 0分 (MACD柱:{macd_bar:.4f})"
    
    return score, details


# ============================================================
# 主流程
# ============================================================

def run_strategy():
    print("=" * 60)
    print(f"  评分制选股 V5.1 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    stocks = get_all_a_stocks()
    if stocks.empty:
        print("无法获取股票列表，退出")
        return []

    selected = []
    total = len(stocks)
    failed = 0

    print(f"\n[2/5] 逐只计算评分（共 {total} 只）...")
    for idx, row in stocks.iterrows():
        code = row['代码']
        name = row['名称']

        if idx % 200 == 0:
            print(f"  进度: {idx}/{total} ({idx/total*100:.1f}%)")

        # 获取实时数据
        realtime = get_realtime_data(code)
        if not realtime:
            failed += 1
            time.sleep(0.05)
            continue

        try:
            score, details = calculate_score(code, realtime)
            
            # 入选门槛：50分
            if score >= 50:
                selected.append({
                    'code': code,
                    'name': name,
                    'score': score,
                    'details': details,
                    **realtime
                })
                print(f"  ★ 选中: {code} {name} - 得分: {score}分")
        except Exception as e:
            failed += 1
            time.sleep(0.05)
            continue

        time.sleep(0.15)

    print(f"\n  策略计算完成: 成功 {total - failed}, 失败 {failed}")
    print(f"\n[3/5] 共选出 {len(selected)} 只股票（≥50分）")
    
    # 按得分降序排序
    selected.sort(key=lambda x: x['score'], reverse=True)
    
    return selected


# ============================================================
# HTML 生成
# ============================================================

def generate_html(selected_stocks, output_path):
    print(f"\n[4/5] 生成展示页面...")

    template_str = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>评分制选股 V5.1</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC',
                 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
    background: #080c1a;
    color: #dde3ff;
    min-height: 100vh;
    padding-bottom: env(safe-area-inset-bottom);
}
.header {
    background: linear-gradient(135deg, #131836 0%, #0a0f28 100%);
    padding: 18px 16px 14px;
    border-bottom: 1px solid rgba(90, 120, 255, 0.18);
    position: sticky;
    top: 0;
    z-index: 100;
    backdrop-filter: blur(20px);
}
.header h1 {
    font-size: 21px;
    font-weight: 800;
    background: linear-gradient(90deg, #7ba4ff, #c084fc, #f472b6);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    letter-spacing: 1.5px;
}
.header .meta {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 7px;
    font-size: 12px;
    color: #6870a0;
}
.header .count {
    background: rgba(90,120,255,0.15);
    color: #8fa4ff;
    padding: 2px 10px;
    border-radius: 12px;
    font-weight: 700;
}
.strategy-desc {
    background: rgba(90,120,255,0.05);
    border: 1px solid rgba(90,120,255,0.12);
    border-radius: 10px;
    padding: 11px 13px;
    margin: 10px 12px 4px;
    font-size: 11px;
    color: #6870a0;
    line-height: 1.85;
}
.strategy-desc strong { color: #a0b0ff; }
.disclaimer {
    background: rgba(234,179,8,0.06);
    border: 1px solid rgba(234,179,8,0.14);
    border-radius: 10px;
    padding: 10px 13px;
    margin: 4px 12px 4px;
    font-size: 11px;
    color: #a89040;
    line-height: 1.5;
}
.stock-list { padding: 10px 12px; }
.stock-card {
    background: linear-gradient(135deg, rgba(20,26,60,0.85) 0%, rgba(10,14,36,0.92) 100%);
    border: 1px solid rgba(90,120,255,0.10);
    border-radius: 14px;
    padding: 14px;
    margin-bottom: 10px;
    position: relative;
    overflow: hidden;
    transition: transform 0.15s;
}
.stock-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, transparent, rgba(255,120,120,0.5), transparent);
}
.stock-card:active { transform: scale(0.985); }
.card-top {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
}
.stock-info { flex: 1; }
.stock-name { font-size: 17px; font-weight: 700; color: #e6eaff; }
.stock-code {
    font-size: 12px;
    color: #525880;
    margin-top: 2px;
    font-family: 'SF Mono','Fira Code',monospace;
}
.score-badge {
    background: linear-gradient(135deg, #f43f5e, #ec4899);
    color: white;
    font-size: 24px;
    font-weight: 800;
    padding: 8px 16px;
    border-radius: 10px;
    text-align: center;
    min-width: 80px;
}
.score-label {
    font-size: 10px;
    opacity: 0.8;
    margin-top: 2px;
}
.stock-price {
    display: flex;
    gap: 15px;
    margin-top: 12px;
    padding-top: 11px;
    border-top: 1px solid rgba(90,120,255,0.07);
}
.price-item { flex: 1; }
.price-label { font-size: 10px; color: #525880; }
.price-value {
    font-size: 15px;
    font-weight: 600;
    margin-top: 2px;
    font-family: 'SF Mono',monospace;
}
.up   { color: #f43f5e; }
.down { color: #10b981; }
.flat { color: #6870a0; }
.details {
    margin-top: 10px;
    padding-top: 9px;
    border-top: 1px solid rgba(90,120,255,0.07);
}
.detail-item {
    font-size: 11px;
    padding: 3px 0;
    color: #8890b0;
    font-family: 'SF Mono',monospace;
}
.empty-state {
    text-align: center;
    padding: 60px 20px;
    color: #525880;
}
.empty-state .icon { font-size: 48px; margin-bottom: 16px; }
.empty-state p { font-size: 14px; line-height: 1.7; }
.footer {
    text-align: center;
    padding: 18px;
    font-size: 11px;
    color: #363b5a;
    border-top: 1px solid rgba(90,120,255,0.06);
    margin-top: 8px;
}
</style>
</head>
<body>
<div class="header">
    <h1>评分制选股 V5.1</h1>
    <div class="meta">
        <span>{{ update_time }}</span>
        <span class="count">{{ stock_count }} 只</span>
    </div>
</div>

<div class="strategy-desc">
    <strong>评分标准（满分100分，≥50分入选）：</strong><br>
    均线多头(MA5>MA20)+20 | BOLL开口(价格>上轨×0.95)+15 | MACD强势(DIF>0)+15 | 
    涨幅适中(2%-8%)+15 | 量能放大(量比>1.5)+10 | 成交活跃(>1亿)+10 | MACD金叉(柱>0)+15
</div>

<div class="disclaimer">
    本页面仅为量化策略筛选结果展示，不构成任何投资建议。股市有风险，投资需谨慎。
</div>

<div class="stock-list">
{% if stocks %}
{% for s in stocks %}
<div class="stock-card">
    <div class="card-top">
        <div class="stock-info">
            <div class="stock-name">{{ s.name }}</div>
            <div class="stock-code">{{ s.code }}</div>
        </div>
        <div class="score-badge">
            {{ s.score }}
            <div class="score-label">分</div>
        </div>
    </div>
    <div class="stock-price">
        <div class="price-item">
            <div class="price-label">现价</div>
            <div class="price-value {% if s.change_pct > 0 %}up{% elif s.change_pct < 0 %}down{% else %}flat{% endif %}">
                {{ "%.2f"|format(s.price) }}
            </div>
        </div>
        <div class="price-item">
            <div class="price-label">涨幅</div>
            <div class="price-value {% if s.change_pct > 0 %}up{% elif s.change_pct < 0 %}down{% else %}flat{% endif %}">
                {% if s.change_pct > 0 %}+{% endif %}{{ "%.2f"|format(s.change_pct) }}%
            </div>
        </div>
        <div class="price-item">
            <div class="price-label">量比</div>
            <div class="price-value">{{ "%.2f"|format(s.volume_ratio) }}</div>
        </div>
        <div class="price-item">
            <div class="price-label">成交额</div>
            <div class="price-value">{{ "%.2f"|format(s.turnover/10000) }}亿</div>
        </div>
    </div>
    {% if s.details %}
    <div class="details">
        {% for key, value in s.details.items() %}
        <div class="detail-item">{{ key }}: {{ value }}</div>
        {% endfor %}
    </div>
    {% endif %}
</div>
{% endfor %}
{% else %}
<div class="empty-state">
    <div class="icon">📊</div>
    <p>今日暂无符合策略的股票<br>策略每个交易日自动更新</p>
</div>
{% endif %}
</div>

<div class="footer">
    <p>评分制选股 V5.1 · 多指标综合评分 · 数据来源：腾讯财经</p>
    <p style="margin-top:4px;">每个交易日自动更新 · PushPlus推送</p>
</div>
</body>
</html>"""

    template = Template(template_str)
    html = template.render(
        stocks=selected_stocks,
        stock_count=len(selected_stocks),
        update_time=datetime.now().strftime('%Y年%m月%d日 %H:%M 更新'),
    )
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"  页面已生成: {output_path}")
    return html


def save_data_json(selected_stocks, output_path):
    """保存选股结果为 JSON"""
    data = {
        'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'strategy': '评分制选股 V5.1',
        'scoring_rules': {
            '均线多头': 'MA5 > MA20 (+20分)',
            'BOLL开口': '价格 > BOLL上轨 × 0.95 (+15分)',
            'MACD强势': 'DIF > 0 (+15分)',
            '涨幅条件': '2% ≤ 涨幅 ≤ 8% (+15分)',
            '量能放大': '量比 > 1.5 (+10分)',
            '成交活跃': '成交额 > 1亿 (+10分)',
            'MACD金叉': 'MACD柱 > 0 (+15分)',
        },
        'threshold': 50,
        'count': len(selected_stocks),
        'stocks': selected_stocks,
    }
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  数据已保存: {output_path}")


def generate_push_content(selected_stocks):
    """生成PushPlus推送内容（HTML格式）"""
    if not selected_stocks:
        return """
        <h2>📊 评分制选股 V5.1</h2>
        <p>今日暂无符合策略的股票（≥50分）</p>
        <p><small>更新时间：{}</small></p>
        """.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    
    # 只推送前10只股票
    top_stocks = selected_stocks[:10]
    
    content = f"""
    <h2>📊 评分制选股 V5.1</h2>
    <p><strong>共选出 {len(selected_stocks)} 只股票（≥50分）</strong></p>
    <p><small>更新时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</small></p>
    <hr>
    <h3>🏆 Top 10 高分股票</h3>
    <table border="1" cellpadding="8" cellspacing="0" style="border-collapse:collapse; width:100%;">
        <tr style="background:#f0f0f0;">
            <th>排名</th>
            <th>代码</th>
            <th>名称</th>
            <th>得分</th>
            <th>现价</th>
            <th>涨幅</th>
        </tr>
    """
    
    for idx, stock in enumerate(top_stocks, 1):
        color = '#ff4444' if stock['change_pct'] > 0 else '#00aa00' if stock['change_pct'] < 0 else '#666666'
        content += f"""
        <tr>
            <td style="text-align:center;">{idx}</td>
            <td style="text-align:center; font-family:monospace;">{stock['code']}</td>
            <td>{stock['name']}</td>
            <td style="text-align:center; font-weight:bold; color:#ff6600;">{stock['score']}分</td>
            <td style="text-align:right; font-family:monospace;">{stock['price']:.2f}</td>
            <td style="text-align:right; font-family:monospace; color:{color};">
                {'+' if stock['change_pct'] > 0 else ''}{stock['change_pct']:.2f}%
            </td>
        </tr>
        """
    
    content += """
    </table>
    <hr>
    <p><small>评分标准：均线多头+20 | BOLL开口+15 | MACD强势+15 | 涨幅适中+15 | 量能放大+10 | 成交活跃+10 | MACD金叉+15</small></p>
    <p><small>⚠️ 本推送仅为策略筛选结果，不构成投资建议</small></p>
    """
    
    return content


if __name__ == '__main__':
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'docs')
    os.makedirs(output_dir, exist_ok=True)

    # 运行策略
    results = run_strategy()

    # 生成HTML
    html_path = os.path.join(output_dir, 'index.html')
    html_content = generate_html(results, html_path)

    # 保存JSON
    json_path = os.path.join(output_dir, 'data.json')
    save_data_json(results, json_path)

    # PushPlus推送
    print(f"\n[5/5] 发送PushPlus推送...")
    push_content = generate_push_content(results)
    push_title = f"📊 评分制选股V5.1 - 选出{len(results)}只股票"
    send_pushplus(push_title, push_content, template='html')

    print(f"\n{'=' * 60}")
    print(f"  完成! 共选出 {len(results)} 只股票（≥50分）")
    print(f"  HTML: {html_path}")
    print(f"  JSON: {json_path}")
    print(f"  PushPlus推送已发送")
    print(f"{'=' * 60}")
