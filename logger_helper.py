import os
import logging
import traceback
from datetime import datetime
from hoshino import logger as hoshino_logger

# 创建插件专属日志目录
LOG_DIR = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

# 配置文件日志处理器
file_handler = logging.FileHandler(
    os.path.join(LOG_DIR, f'dailysum_{datetime.now().strftime("%Y-%m-%d")}.log'),
    encoding='utf-8'
)
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    '[%(asctime)s][%(levelname)s][%(funcName)s:%(lineno)d]: %(message)s'
)
file_handler.setFormatter(formatter)

# 获取与HoshinoBot相同的日志器，但添加我们的文件处理器
plugin_logger = hoshino_logger
plugin_logger.addHandler(file_handler)

def log_start(func_name, **kwargs):
    """记录函数开始执行"""
    args_str = ', '.join([f'{k}={v}' for k, v in kwargs.items()])
    plugin_logger.info(f"开始执行 {func_name}({args_str})")

def log_end(func_name, result=None):
    """记录函数执行结束"""
    if result is not None:
        if isinstance(result, (dict, list)) and len(str(result)) > 200:
            plugin_logger.info(f"函数 {func_name} 执行完成，返回大型对象，长度: {len(str(result))}")
        else:
            plugin_logger.info(f"函数 {func_name} 执行完成，返回: {result}")
    else:
        plugin_logger.info(f"函数 {func_name} 执行完成")

def log_error(func_name, error):
    """记录函数执行错误"""
    plugin_logger.error(f"函数 {func_name} 执行出错: {str(error)}")
    plugin_logger.error(traceback.format_exc())

def log_debug(message):
    """记录调试信息"""
    plugin_logger.debug(message)

def log_info(message):
    """记录信息"""
    plugin_logger.info(message)

def log_warning(message):
    """记录警告"""
    plugin_logger.warning(message)

def log_error_msg(message):
    """记录错误消息"""
    plugin_logger.error(message)

def log_critical(message):
    """记录严重错误"""
    plugin_logger.critical(message)

class LoggedFunction:
    """日志装饰器类，用于记录函数执行过程"""
    def __init__(self, func):
        self.func = func
        self.__name__ = func.__name__
        self.__doc__ = func.__doc__

    def __call__(self, *args, **kwargs):
        try:
            log_start(self.func.__name__, **{**{f'arg{i}': arg for i, arg in enumerate(args)}, **kwargs})
            result = self.func(*args, **kwargs)
            log_end(self.func.__name__, result)
            return result
        except Exception as e:
            log_error(self.func.__name__, e)
            raise

    async def __async_call__(self, *args, **kwargs):
        try:
            log_start(self.func.__name__, **{**{f'arg{i}': arg for i, arg in enumerate(args)}, **kwargs})
            result = await self.func(*args, **kwargs)
            log_end(self.func.__name__, result)
            return result
        except Exception as e:
            log_error(self.func.__name__, e)
            raise

def logged(func):
    """日志装饰器，自动记录函数执行情况"""
    if asyncio.iscoroutinefunction(func):
        async def wrapper(*args, **kwargs):
            return await LoggedFunction(func).__async_call__(*args, **kwargs)
        return wrapper
    else:
        return LoggedFunction(func)

# 添加导入
import asyncio 