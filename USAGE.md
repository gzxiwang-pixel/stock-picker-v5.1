# 使用说明

## 🚀 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/Jesse-J-whu/stock-picker-v5.1.git
cd stock-picker-v5.1
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置PushPlus Token

编辑 `strategy.py` 文件，修改第28行的Token：

```python
PUSHPLUS_TOKEN = "your_token_here"  # 替换为您的Token
```

**获取Token步骤：**
1. 访问 [PushPlus官网](http://www.pushplus.plus/)
2. 使用微信扫码登录
3. 在"一对一推送"页面复制您的Token
4. 将Token粘贴到代码中

### 4. 运行策略

#### 测试运行（推荐首次使用）

```bash
python test_strategy.py
```

测试脚本会：
- 测试5只常见大盘股
- 显示详细的评分过程
- 发送测试推送到您的微信

#### 完整运行

```bash
python strategy.py
```

完整运行会：
- 扫描所有A股（约5000只）
- 计算每只股票的评分
- 筛选出≥50分的股票
- 生成HTML展示页面
- 保存JSON数据文件
- 发送推送到您的微信

**注意：** 完整运行需要15-30分钟，建议在收盘后运行。

## 📊 查看结果

### 本地查看

运行完成后，在 `docs` 目录下会生成：

- `index.html` - 可视化展示页面
- `data.json` - 完整数据文件

直接用浏览器打开 `docs/index.html` 即可查看结果。

### 在线查看

如果您已配置GitHub Pages，可以访问：

```
https://your-username.github.io/stock-picker-v5.1/
```

## 🤖 自动化运行

### GitHub Actions配置

项目已配置GitHub Actions，可实现每个交易日自动运行：

1. **Fork本项目到您的GitHub账号**

2. **配置PushPlus Token**
   - 编辑 `strategy.py` 中的Token
   - 提交并推送到GitHub

3. **启用GitHub Pages**
   - 进入仓库 Settings → Pages
   - Source选择 "Deploy from a branch"
   - Branch选择 "main"，文件夹选择 "/docs"
   - 点击Save

4. **启用GitHub Actions**
   - 进入仓库 Actions 标签
   - 如果提示启用工作流，点击启用

5. **自动运行时间**
   - 每个交易日（周一至周五）15:30（北京时间）自动运行
   - 也可以手动触发：Actions → 选择工作流 → Run workflow

### 手动触发

在GitHub仓库页面：
1. 点击 `Actions` 标签
2. 选择 "评分制选股V5.1自动运行"
3. 点击 `Run workflow` → `Run workflow`

## 📱 PushPlus推送说明

### 推送内容

- 📊 选股数量统计
- 🏆 Top 10 高分股票
- 📈 股票代码、名称、得分、价格、涨幅
- ⏰ 更新时间

### 推送时机

- 测试脚本：立即推送
- 完整策略：运行完成后推送
- GitHub Actions：每个交易日收盘后自动推送

### 常见问题

**Q: 没有收到推送？**
- 检查Token是否正确配置
- 确认微信已关注PushPlus公众号
- 查看运行日志中的推送状态

**Q: 推送内容不完整？**
- PushPlus免费版有消息长度限制
- 策略会自动只推送Top 10股票

## 🔧 高级配置

### 修改评分标准

编辑 `strategy.py` 中的 `calculate_score` 函数，可以：

- 调整各指标的分值
- 修改入选门槛（默认50分）
- 添加新的评分指标

### 修改筛选条件

例如修改涨幅范围：

```python
# 原代码（第4条）
if 2 <= change_pct <= 8:
    score += 15

# 修改为
if 1 <= change_pct <= 10:
    score += 15
```

### 修改运行时间

编辑 `.github/workflows/auto-run.yml`：

```yaml
schedule:
  # 修改这一行的时间（UTC时间）
  - cron: '30 7 * * 1-5'  # 北京时间15:30
```

## 📝 注意事项

1. **数据来源**
   - 使用腾讯财经免费接口
   - 数据有延迟，仅供参考
   - 不保证数据准确性

2. **运行频率**
   - 建议每天运行一次
   - 过于频繁可能被限流
   - GitHub Actions已配置合理频率

3. **资源消耗**
   - 完整运行需要15-30分钟
   - 会产生大量网络请求
   - 建议在网络稳定时运行

4. **投资建议**
   - 本策略仅供学习研究
   - 不构成任何投资建议
   - 投资有风险，决策需谨慎

## 🆘 故障排查

### 运行失败

1. **检查Python版本**
   ```bash
   python --version  # 需要3.7+
   ```

2. **检查依赖安装**
   ```bash
   pip list | grep -E "numpy|pandas|requests|jinja2"
   ```

3. **查看错误日志**
   - 本地运行：查看终端输出
   - GitHub Actions：查看Actions日志

### 数据获取失败

1. **网络问题**
   - 检查网络连接
   - 尝试使用代理

2. **接口限流**
   - 减少运行频率
   - 增加请求间隔（修改 `time.sleep`）

### GitHub Pages不显示

1. **检查配置**
   - Settings → Pages 确认已启用
   - 确认Branch和文件夹设置正确

2. **等待部署**
   - 首次部署需要几分钟
   - 查看Actions中的部署状态

## 📧 获取帮助

- 提交Issue：[GitHub Issues](https://github.com/Jesse-J-whu/stock-picker-v5.1/issues)
- 查看文档：[README.md](README.md)
- 测试脚本：`python test_strategy.py`

---

**祝您使用愉快！** 📈
