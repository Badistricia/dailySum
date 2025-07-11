# 群聊日报生成器

这是一个基于HoshinoBot的群聊日报生成插件，可以自动分析群聊记录并生成每日报告。

## 功能特点

- 自动分析群聊活跃度
- 生成话题分析
- 进行情感分析
- 提供互动亮点
- 支持手动和自动触发
- 支持多群管理
- 支持两种输出格式：简单图片和精美HTML报告

## 安装依赖

### 基础依赖

基础功能只需安装以下依赖：

```bash
# Ubuntu/Debian系统安装中文字体
sudo apt update
sudo apt install -y fonts-wqy-microhei fonts-wqy-zenhei fonts-noto-cjk
```

### 高级HTML报告依赖

要使用高级HTML报告功能（`日报 测试2`命令），需要安装以下依赖：

```bash
# 安装Python依赖
pip install playwright pillow

# 安装Playwright浏览器
playwright install chromium
```

## 使用方法

### 常用命令

- `日报` - 手动触发当天群聊总结
- `日报 昨天` - 手动触发昨天的群聊总结
- `日报 群号` - 手动触发指定群的当天聊天总结
- `日报 昨天 群号` - 手动触发指定群的昨天聊天总结
- `日报 状态` - 查看当前日报配置
- `日报 添加群 群号` - 添加群到日报白名单
- `日报 删除群 群号` - 从日报白名单移除群
- `日报 启用/禁用` - 开启或关闭日报定时功能

### 测试命令

- `日报 测试` - 生成一个简单格式的测试日报图片
- `日报 测试2` - 生成一个精美的HTML格式测试日报图片 (需安装playwright)

## 故障排除

### 图片生成失败

1. 确保已安装中文字体
2. 检查模块目录中是否有字体文件
3. 查看日志输出，了解具体错误

### HTML报告生成失败

1. 确保已安装playwright和pillow
2. 确保已安装chromium浏览器（playwright install chromium）
3. 检查是否有足够的系统权限

## 自定义样式

如需自定义HTML报告样式，可编辑`test_html_report_2.py`文件中的HTML_TEMPLATE变量。

## 许可证

MIT License 