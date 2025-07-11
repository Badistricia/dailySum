import os

try:
    from hoshino.log import _info_log_file
    # 自动获取HoshinoBot的日志文件路径
    LOG_PATH = os.path.abspath(_info_log_file)
except ImportError:
    # 兜底方案，如果获取失败则需要手动指定
    LOG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'run.log')  # 指向项目根目录的run.log文件

# 基本配置
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')

# 定时任务配置
ENABLE_SCHEDULER = True  # 是否启用定时任务
SUMMARY_HOUR = 8  # 每天几点发送日报
SUMMARY_MINUTE = 30  # 每天几分发送日报
SUMMARY_START_HOUR = 4  # 统计时间段的起始小时（例如：4点到次日4点）

# AI配置
AI_API_KEY = "sk-476330950dd24ff6869b6a301930f275"  # DeepSeek API密钥
AI_MODEL = "deepseek-chat"  # AI模型名称
AI_TEMPERATURE = 1.0  # AI生成温度

# 群配置
DAILY_SUM_GROUPS = []  # 日报功能启用的群列表，为空时对所有群启用
# 示例：DAILY_SUM_GROUPS = ['123456789', '987654321'] # 只在这两个群启用日报功能

# 并发控制
MAX_CONCURRENT_TASKS = 3  # 最大并发任务数量
TASK_INTERVAL_SECONDS = 10  # 每个群任务之间的间隔秒数

# 提示词配置
PROMPT_TEMPLATE = """请根据【{group_name}】今天的聊天记录，整理一份QQ群日报，要求：  

1. **数据必须严格按照下列格式组织**，每个部分必须带明确标题，使用【】符号：

【聊天活跃度】
- 今日消息总量和参与人数
- 最活跃时段
- 活跃成员

【话题分析】
- 列出3-5个主要讨论话题，必须使用无序列表格式（每行以"-"开头）

【情感分析】
- 整体聊天氛围
- 群友互动情况

【互动亮点】
- 精彩对话或有趣互动
- 值得关注的消息

【总结】
- 对今日群聊的简短总结，一两句话即可

- 总内容控制在600字以内
- 严格遵循上述格式，确保每个部分都有【】标记的标题
- 聊天记录中[图片]表示图片内容，[链接]表示网址

聊天记录：
{chat_log}
"""

# HTML直接生成的提示词配置
PROMPT_HTML_TEMPLATE = """请根据【{group_name}】今天的聊天记录，生成一个精美的苹果风格Bento Grid布局的日报HTML页面，要求：

1. 页面需包含以下5个区块：
   - 聊天活跃度：展示今日消息总量、参与人数、最活跃时段等信息
   - 话题分析：列出3-5个主要讨论话题，使用无序列表格式
   - 情感分析：分析整体聊天氛围和群友互动情况
   - 互动亮点：展示精彩对话或有趣互动
   - 总结：对今日群聊的简短总结

2. 布局与设计要求：
   - 必须使用深色主题，类似苹果官网的Bento Grid布局
   - 页面顶部有标题："{title}"
   - 页面底部有落款："由AI生成 · {date}"
   - 使用圆角卡片设计，每个区块有独特图标
   - 布局宽度固定为800px
   - 确保文字清晰易读，深色背景上使用浅色文字
   - 必须使用不超过20行的内联CSS样式，不能使用外部样式表

3. 内容要求：
   - 内容控制在600字以内，简洁明了
   - 结构清晰，每个区块标题醒目
   - 总结部分使用高亮颜色显示

4. 技术要求：
   - 只需提供完整的HTML代码，不需要额外解释
   - 确保HTML代码有良好的缩进和格式
   - 确保代码中不包含任何会阻止直接执行的脚本
   - 代码必须能在现代浏览器中正确显示

请基于以上要求，将聊天记录分析后直接返回完整的HTML代码，无需额外说明。

聊天记录：
{chat_log}
"""
# 最后，用分块布局（类似苹果发布会的Bento Grid风格）生成HTML，方便阅读。

# 图片生成配置
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>群聊日报</title>
    <style>
        body {
            font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif;
            background-color: #f5f5f7;
            color: #1d1d1f;
            padding: 20px;
            margin: 0;
            line-height: 1.5;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
            background-color: white;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        .header {
            background-color: #000;
            color: white;
            padding: 20px;
            text-align: center;
        }
        .header h1 {
            margin: 0;
            font-weight: 600;
            font-size: 24px;
        }
        .date {
            color: #86868b;
            font-size: 14px;
            margin-top: 5px;
        }
        .bento-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 15px;
            padding: 20px;
        }
        .bento-item {
            background-color: #f5f5f7;
            border-radius: 8px;
            padding: 15px;
            overflow: hidden;
        }
        .bento-item.large {
            grid-column: span 2;
        }
        .bento-item h2 {
            margin-top: 0;
            font-size: 18px;
            color: #1d1d1f;
            border-bottom: 1px solid #d2d2d7;
            padding-bottom: 8px;
            margin-bottom: 12px;
        }
        .bento-item p {
            margin: 8px 0;
            font-size: 14px;
        }
        .bento-item ul {
            margin: 8px 0;
            padding-left: 20px;
        }
        .bento-item li {
            margin-bottom: 8px;
            font-size: 14px;
        }
        .footer {
            text-align: center;
            padding: 15px;
            color: #86868b;
            font-size: 12px;
            border-top: 1px solid #d2d2d7;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{group_name}日报</h1>
            <div class="date">{date}</div>
        </div>
        <div class="bento-grid">
            {content}
        </div>
        <div class="footer">
            由HoshinoBot生成 · {date}
        </div>
    </div>
</body>
</html>
""" 