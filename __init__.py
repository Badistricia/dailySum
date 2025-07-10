import os
import re
import asyncio
from datetime import datetime
from hoshino import Service, priv
from .logger_helper import log_info, log_warning, log_error_msg
from .dailysum import start_scheduler, manual_summary, backup_logs, load_group_config

sv = Service(
    name='dailySum',
    bundle='日常',
    help_='''
    [日报] 手动触发当天群聊总结
    [日报 昨天] 手动触发昨天的群聊总结
    [日报 群号] 手动触发指定群的当天聊天总结
    [日报 昨天 群号] 手动触发指定群的昨天聊天总结
    [日报 状态] 查看当前日报配置
    [日报 添加群 群号] 添加群到日报白名单
    [日报 删除群 群号] 从日报白名单移除群
    [日报 启用/禁用] 开启或关闭日报定时功能
    '''.strip()
)

# 创建目录
log_info("初始化群聊日报插件...")
# 创建data目录
os.makedirs(os.path.join(os.path.dirname(__file__), 'data'), exist_ok=True)
log_info("创建data目录成功")
# 创建logs目录
os.makedirs(os.path.join(os.path.dirname(__file__), 'logs'), exist_ok=True)
log_info("创建logs目录成功")

# 加载群配置
async def init_config():
    """初始化配置"""
    await load_group_config()

# 正则表达式用于匹配群号和日期描述词
GROUP_ID_PATTERN = r'^日报\s+(\d{5,})$'  # 至少5位数字的群号
YESTERDAY_GROUP_ID_PATTERN = r'^日报\s+(昨天|前天|今天)\s+(\d{5,})$'  # 日期描述词 + 群号
DAY_PATTERN = r'^日报\s+(昨天|前天|今天)$'  # 仅日期描述词

# 注册命令
@sv.on_fullmatch(('日报', '群聊日报'))
async def daily_summary(bot, ev):
    log_info(f"收到日报命令，群号:{ev['group_id']}, 用户:{ev['user_id']}")
    await manual_summary(bot, ev, day_offset=0, target_group=None)

@sv.on_rex(DAY_PATTERN)
async def day_summary(bot, ev):
    match = ev['match']
    day_str = match.group(1)
    day_offset = {'今天': 0, '昨天': 1, '前天': 2}.get(day_str, 1)
    log_info(f"收到{day_str}日报命令，群号:{ev['group_id']}, 用户:{ev['user_id']}, 日期偏移:{day_offset}")
    await manual_summary(bot, ev, day_offset=day_offset, target_group=None)

@sv.on_rex(GROUP_ID_PATTERN)
async def group_daily_summary(bot, ev):
    match = ev['match']
    target_group_id = match.group(1)
    log_info(f"收到指定群日报命令，当前群号:{ev['group_id']}, 目标群号:{target_group_id}, 用户:{ev['user_id']}")
    await manual_summary(bot, ev, day_offset=0, target_group=target_group_id)

@sv.on_rex(YESTERDAY_GROUP_ID_PATTERN)
async def yesterday_group_summary(bot, ev):
    match = ev['match']
    day_str = match.group(1)
    target_group_id = match.group(2)
    day_offset = {'今天': 0, '昨天': 1, '前天': 2}.get(day_str, 1)
    log_info(f"收到指定群{day_str}日报命令，当前群号:{ev['group_id']}, 目标群号:{target_group_id}, 用户:{ev['user_id']}, 日期偏移:{day_offset}")
    await manual_summary(bot, ev, day_offset=day_offset, target_group=target_group_id)

# 执行一次日志备份，确保历史记录保存
async def run_initial_backup():
    log_info("执行初始化日志备份...")
    try:
        await backup_logs()
        log_info("初始化日志备份完成")
    except Exception as e:
        log_error_msg(f"初始化日志备份失败: {str(e)}")

# 初始化配置
asyncio.create_task(init_config())

# 启动定时任务
log_info("开始启动定时任务...")
start_scheduler(sv)

# 异步执行初始化备份
asyncio.create_task(run_initial_backup())

log_info("群聊日报插件初始化完成")