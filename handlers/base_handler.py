"""
处理器基类
"""
from abc import ABC
from typing import Optional

from astrbot.api.event import AstrMessageEvent
from astrbot.api import logger

from ..models.entities import UserContext
from ..core.exceptions import AhutEleException, AuthException


class BaseHandler(ABC):
    """处理器基类"""

    def __init__(self, plugin):
        self.plugin = plugin

    def get_user_context(self, event: AstrMessageEvent) -> UserContext:
        """获取用户上下文"""
        sender_id = str(event.get_sender_id())
        is_admin = self._is_admin(sender_id)
        group_umo = getattr(event, 'unified_msg_origin', None)
        return UserContext(user_id=sender_id, is_admin=is_admin, group_umo=group_umo)

    def _is_admin(self, user_id: str) -> bool:
        """检查是否为管理员"""
        admin_users = self.plugin.config.get("admin_users", [])
        if not admin_users:
            return True
        return user_id in admin_users or str(user_id) in admin_users

    def handle_error(self, error: Exception, operation: str = "操作") -> str:
        """统一错误处理"""
        if isinstance(error, AhutEleException):
            return f"❌ {error.message}"

        logger.error(f"{operation}失败: {error}", exc_info=True)
        return f"❌ {operation}失败，请稍后重试"
