import os
import re
import asyncio
from datetime import datetime
from hoshino import Service, priv
from nonebot import scheduler  # 导入scheduler
from .logger_helper import log_info, log_warning, log_error_msg
from .dailysum import start_scheduler, manual_summary, backup_logs, load_group_config, handle_daily_report_cmd
from .test_html_report import handle_test_report  # 重新导入handle_test_report函数

sv = Service(
    name='dailySum',  # 使用原来的名称
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
    [日报 测试] 生成一个HTML格式的测试日报
    '''.strip(),
    enable_on_default=False
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

# 初始化和备份操作
async def init_and_backup():
    log_info("执行初始化和备份操作...")
    try:
        # 初始化配置
        await init_config()
        # 执行日志备份
        await backup_logs()
        log_info("初始化备份完成")
    except Exception as e:
        log_error_msg(f"初始化或备份失败: {str(e)}")

# 使用scheduler在机器人启动后执行初始化任务
scheduler.add_job(init_and_backup, 'date', run_date=datetime.now())

# 测试日报命令处理 - 专门处理"日报 测试"命令
@sv.on_fullmatch('日报 测试')
async def test_daily_report_cmd(bot, ev):
    log_info(f"收到测试日报命令，群号:{ev['group_id']}, 用户:{ev['user_id']}")
    await handle_test_report(bot, ev)

# 统一处理其他日报命令
@sv.on_prefix(['日报'])
async def daily_report_cmd(bot, ev):
    msg = ev.message.extract_plain_text().strip()
    log_info(f"收到日报命令，群号:{ev['group_id']}, 用户:{ev['user_id']}, 参数:{msg}")
    
    # 测试命令已由上面的专用处理函数处理，这里跳过
    if msg == '测试':
        log_info("跳过测试命令，已由专用处理函数处理")
        return
    
    # 处理其他日报命令
    await handle_daily_report_cmd(bot, ev, msg)

# 原有的处理函数，保留以兼容已发送的命令
# 如果不需要兼容性，可以删除下面这些函数
@sv.on_fullmatch(('日报', '群聊日报'))
async def daily_summary(bot, ev):
    log_info(f"收到日报命令，群号:{ev['group_id']}, 用户:{ev['user_id']}")
    await manual_summary(bot, ev, day_offset=1, target_group=None)  # 默认改为1天偏移，查看昨天的日报

@sv.on_rex(r'^日报\s+(昨天|前天|今天)$')
async def day_summary(bot, ev):
    match = ev['match']
    day_str = match.group(1)
    day_offset = {'今天': 0, '昨天': 1, '前天': 2}.get(day_str, 1)
    log_info(f"收到{day_str}日报命令，群号:{ev['group_id']}, 用户:{ev['user_id']}, 日期偏移:{day_offset}")
    await manual_summary(bot, ev, day_offset=day_offset, target_group=None)

@sv.on_rex(r'^日报\s+(\d{5,})$')
async def group_daily_summary(bot, ev):
    match = ev['match']
    target_group_id = match.group(1)
    log_info(f"收到指定群日报命令，当前群号:{ev['group_id']}, 目标群号:{target_group_id}, 用户:{ev['user_id']}")
    await manual_summary(bot, ev, day_offset=1, target_group=target_group_id)  # 默认改为1天偏移，查看昨天的日报

@sv.on_rex(r'^日报\s+(昨天|前天|今天)\s+(\d{5,})$')
async def yesterday_group_summary(bot, ev):
    match = ev['match']
    day_str = match.group(1)
    target_group_id = match.group(2)
    day_offset = {'今天': 0, '昨天': 1, '前天': 2}.get(day_str, 1)
    log_info(f"收到指定群{day_str}日报命令，当前群号:{ev['group_id']}, 目标群号:{target_group_id}, 用户:{ev['user_id']}, 日期偏移:{day_offset}")
    await manual_summary(bot, ev, day_offset=day_offset, target_group=target_group_id)

# 启动定时任务
log_info("开始启动定时任务...")
start_scheduler(sv)

log_info("群聊日报插件初始化完成")