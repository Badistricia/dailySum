import os
import json
import re
import asyncio
from hoshino import Service
from .dailysum import handle_daily_report_cmd, start_scheduler, PLAYWRIGHT_AVAILABLE, init_dailysum_playwright
from .logger_helper import log_info, log_warning, log_error_msg

try:
    from .test_html_report_2 import handle_test_report_2
except ImportError as e:
    log_warning(f"导入HTML日报模块失败: {str(e)}")
    handle_test_report_2 = None

sv = Service('dailysum', enable_on_default=True, help_='群聊日报功能')

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

# 测试HTML日报命令
@sv.on_fullmatch(('测试日报2', '测试日报图片'))
async def handle_test_html_report(bot, ev):
    if handle_test_report_2:
        await handle_test_report_2(bot, ev)
    else:
        await bot.send(ev, "HTML日报功能未能正确加载，请检查是否安装了playwright库")

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