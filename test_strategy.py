"""
测试脚本 - 快速验证策略功能
仅测试少量股票以快速验证逻辑
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from strategy import *

def test_strategy():
    print("=" * 60)
    print("  评分制选股 V5.1 - 测试模式")
    print("=" * 60)
    
    # 测试股票列表（一些常见的大盘股）
    test_stocks = [
        {'代码': '600519', '名称': '贵州茅台'},
        {'代码': '000001', '名称': '平安银行'},
        {'代码': '600036', '名称': '招商银行'},
        {'代码': '000858', '名称': '五粮液'},
        {'代码': '601318', '名称': '中国平安'},
    ]
    
    print(f"\n测试 {len(test_stocks)} 只股票...")
    
    selected = []
    
    for stock in test_stocks:
        code = stock['代码']
        name = stock['名称']
        
        print(f"\n处理: {code} {name}")
        
        # 获取实时数据
        realtime = get_realtime_data(code)
        if not realtime:
            print(f"  ✗ 获取实时数据失败")
            continue
        
        print(f"  价格: {realtime['price']:.2f}, 涨幅: {realtime['change_pct']:.2f}%")
        
        # 计算评分
        try:
            score, details = calculate_score(code, realtime)
            print(f"  得分: {score}分")
            
            if details:
                for key, value in details.items():
                    print(f"    {key}: {value}")
            
            if score >= 50:
                selected.append({
                    'code': code,
                    'name': name,
                    'score': score,
                    'details': details,
                    **realtime
                })
                print(f"  ★ 入选!")
        except Exception as e:
            print(f"  ✗ 计算评分失败: {str(e)}")
            import traceback
            traceback.print_exc()
    
    print(f"\n{'=' * 60}")
    print(f"测试完成! 共 {len(selected)} 只股票入选（≥50分）")
    
    if selected:
        print("\n入选股票:")
        for s in selected:
            print(f"  {s['code']} {s['name']} - {s['score']}分")
    
    # 测试PushPlus推送
    print(f"\n{'=' * 60}")
    print("测试PushPlus推送...")
    
    push_content = f"""
    <h2>📊 评分制选股 V5.1 - 测试推送</h2>
    <p>测试时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    <p>测试股票数：{len(test_stocks)}</p>
    <p>入选股票数：{len(selected)}</p>
    <hr>
    """
    
    if selected:
        push_content += "<h3>入选股票</h3><ul>"
        for s in selected:
            push_content += f"<li>{s['code']} {s['name']} - {s['score']}分</li>"
        push_content += "</ul>"
    else:
        push_content += "<p>暂无股票入选</p>"
    
    push_content += "<p><small>⚠️ 这是一条测试推送</small></p>"
    
    success = send_pushplus("📊 评分制选股V5.1 - 测试推送", push_content, template='html')
    
    if success:
        print("✓ PushPlus推送测试成功!")
    else:
        print("✗ PushPlus推送测试失败，请检查Token配置")
    
    print(f"{'=' * 60}\n")

if __name__ == '__main__':
    test_strategy()
