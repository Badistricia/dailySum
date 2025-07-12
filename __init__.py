import os
import json
import re
import asyncio
from hoshino import Service
from .dailysum import handle_daily_report_cmd, start_scheduler, PLAYWRIGHT_AVAILABLE, init_dailysum_playwright
from .logger_helper import log_info, log_warning, log_error_msg

sv = Service('dailysum', enable_on_default=False, help_='群聊日报功能')

# 创建必要的目录
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
os.makedirs(DATA_DIR, exist_ok=True)

LOG_DIR = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

# 日报相关命令处理
@sv.on_prefix(('日报', 'ribaogn', 'rb'))
async def handle_dailysum(bot, ev):
    msg = ev.message.extract_plain_text().strip()
    await handle_daily_report_cmd(bot, ev, msg)

# 初始化定时任务
scheduler_started = False
def init():
    global scheduler_started
    if not scheduler_started:
        # 启动定时器
        start_scheduler()
        scheduler_started = True
        
        # 异步初始化Playwright
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(init_dailysum_playwright())
        else:
            loop.run_until_complete(init_dailysum_playwright())

# 自动初始化
init()