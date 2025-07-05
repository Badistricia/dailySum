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
SUMMARY_HOUR_AFTERNOON = 18  # 下午6点进行总结
SUMMARY_HOUR_NIGHT = 0  # 晚上12点进行总结

# AI配置
AI_API_KEY = "sk-476330950dd24ff6869b6a301930f275"  # DeepSeek API密钥
AI_MODEL = "deepseek-chat"  # AI模型名称
AI_TEMPERATURE = 1.0  # AI生成温度

# 提示词配置
PROMPT_TEMPLATE = """请根据【{group_name}】今天的聊天记录，整理一份QQ群日报，要求：  

1. **今日热点话题**（总结3-5个最活跃的讨论点）  
2. **重要消息**（活动通知、截止时间等）  
3. **金句/趣图**（摘录精彩内容）  

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