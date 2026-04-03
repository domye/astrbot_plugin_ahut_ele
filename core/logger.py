"""
日志配置
"""
from astrbot.api import logger


def log_operation(operation: str, user_id: str, success: bool, details: str = None):
    """记录操作日志"""
    status = "成功" if success else "失败"
    msg = f"[操作] {operation} | 用户: {user_id} | 结果: {status}"
    if details:
        msg += f" | 详情: {details}"

    if success:
        logger.info(msg)
    else:
        logger.warning(msg)


def log_service_call(service: str, method: str, success: bool, error: str = None):
    """记录服务调用日志"""
    status = "成功" if success else "失败"
    msg = f"[服务] {service}.{method} | 结果: {status}"
    if error:
        msg += f" | 错误: {error}"

    if success:
        logger.debug(msg)
    else:
        logger.error(msg)


def log_auth_event(user_id: str, event: str, success: bool):
    """记录认证事件"""
    status = "成功" if success else "失败"
    logger.info(f"[认证] 用户: {user_id} | 事件: {event} | 结果: {status}")
