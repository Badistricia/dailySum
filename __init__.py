import os
from hoshino import Service, priv
from .logger_helper import log_info, log_warning, log_error_msg
from .dailysum import start_scheduler, manual_summary

sv = Service(
    name='dailySum',
    bundle='日常',
    help_='''
    [日报] 手动触发当天群聊总结
    [日报 昨天] 手动触发昨天的群聊总结
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

# 注册命令
@sv.on_fullmatch(('日报', '群聊日报'))
async def daily_summary(bot, ev):
    log_info(f"收到日报命令，群号:{ev['group_id']}, 用户:{ev['user_id']}")
    await manual_summary(bot, ev, day_offset=0)

@sv.on_fullmatch(('昨日日报', '昨天日报', '日报 昨天'))
async def yesterday_summary(bot, ev):
    log_info(f"收到昨日日报命令，群号:{ev['group_id']}, 用户:{ev['user_id']}")
    await manual_summary(bot, ev, day_offset=1)

# 启动定时任务
log_info("开始启动定时任务...")
start_scheduler(sv)
log_info("群聊日报插件初始化完成") 