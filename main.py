"""
安徽工业大学电费查询插件

功能：
- 管理员可设置缴费系统登录凭证
- 用户可设置宿舍信息
- 查询所有已配置宿舍的电费
- 支持定时推送
"""
from pathlib import Path
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import AstrBotConfig, logger
from astrbot.core.utils.astrbot_path import get_astrbot_data_path

from .core.constants import COMMAND_PREFIX, PLUGIN_NAME, SESSION_TIMEOUT_MINUTES
from .core.exceptions import AhutEleException
from .models.entities import PayCredentials
from .repositories.credential_repository import CredentialRepository
from .repositories.dorm_repository import DormRepository
from .repositories.schedule_repository import ScheduleRepository
from .services.pay_service import PayService
from .services.scheduler_service import SchedulerService
from .handlers.admin_handler import AdminHandler
from .handlers.user_handler import UserHandler
from .handlers.query_handler import QueryHandler
from .handlers.schedule_handler import ScheduleHandler


@register("ahut_ele", "domye", "安徽工业大学电费查询插件", "2.0.0")
class AhutElePlugin(Star):
    """安工大电费查询插件 v2.0"""

    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config

        # 数据路径
        self.data_path = Path(get_astrbot_data_path()) / "plugin_data" / PLUGIN_NAME
        self.data_path.mkdir(parents=True, exist_ok=True)

        # 数据访问层
        self.credential_repo = CredentialRepository(self.data_path)
        self.dorm_repo = DormRepository(self.data_path)
        self.schedule_repo = ScheduleRepository(self.data_path)

        # 服务层
        self.pay_service = PayService()
        self.scheduler_service = SchedulerService(self.schedule_repo)

        # 处理器
        self.admin_handler = AdminHandler(self)
        self.user_handler = UserHandler(self)
        self.query_handler = QueryHandler(self)
        self.schedule_handler = ScheduleHandler(self)

    async def initialize(self):
        """初始化插件"""
        # 加载已存储的凭证
        creds = await self.credential_repo.get()
        if creds:
            self.pay_service.set_credentials(creds)
            logger.info(f"[{PLUGIN_NAME}] 已加载存储的凭证")

        # 启动定时任务调度器
        self.scheduler_service.start(self._send_scheduled_query)

        logger.info(f"[{PLUGIN_NAME}] 插件初始化完成 (v2.0.0)")

    async def terminate(self):
        """插件关闭时清理"""
        self.scheduler_service.stop()
        await self.pay_service.close()
        logger.info(f"[{PLUGIN_NAME}] 插件已终止")

    async def _send_scheduled_query(self, group_umo: str):
        """发送定时查询"""
        try:
            # 检查凭证
            if not await self.credential_repo.exists():
                logger.warning(f"[{PLUGIN_NAME}] 系统未配置，跳过定时查询")
                return

            # 获取所有宿舍
            all_dorms = await self.dorm_repo.get_all_as_list()
            if not all_dorms:
                return

            # 查询电费
            lines = ["📊 定时电费查询结果：", ""]
            for user_id, dorm in all_dorms:
                try:
                    result = await self.pay_service.query_full_electricity(
                        campus=dorm.campus,
                        building_name=dorm.building_name,
                        building_id=dorm.building_id,
                        room_id=dorm.room_id,
                    )

                    if result.error:
                        lines.append(f"❌ {dorm.get_display_name()}: {result.error}")
                    else:
                        lines.append(f"🏠 {dorm.get_display_name()}")
                        lines.append(f"🔌 房间: {result.room_remain:.2f} kWh")
                        lines.append(f"❄️ 空调: {result.ac_remain:.2f} kWh")
                    lines.append("")
                except Exception as e:
                    logger.error(f"[{PLUGIN_NAME}] 定时查询失败 {dorm.room_id}: {e}")

            # 发送消息
            from astrbot.api.message_components import Plain
            from astrbot.api.event import MessageChain
            message = "\n".join(lines)
            chain = MessageChain([Plain(message)])
            await self.context.send_message(group_umo, chain)

        except Exception as e:
            logger.error(f"[{PLUGIN_NAME}] 定时查询失败: {e}", exc_info=True)

    # ========== 命令入口 ==========

    @filter.regex(rf'^{COMMAND_PREFIX}')
    async def handle_command(self, event: AstrMessageEvent):
        """电费命令入口"""
        # 获取完整消息并解析参数
        full_msg = event.message_str.strip()

        # 移除命令前缀
        if full_msg.startswith(COMMAND_PREFIX):
            msg = full_msg[len(COMMAND_PREFIX):].strip()
        else:
            msg = ""

        # 解析参数
        parts = msg.split() if msg else []
        subcmd = parts[0] if parts else "帮助"
        args = parts[1:] if len(parts) > 1 else []

        if subcmd in ["登录", "login"]:
            async for result in self.admin_handler.handle_login(event):
                yield result
        elif subcmd in ["登出", "logout"]:
            async for result in self.admin_handler.handle_logout(event):
                yield result
        elif subcmd in ["设置", "setup", "set"]:
            async for result in self.user_handler.handle_setup(event):
                yield result
        elif subcmd in ["我的", "my"]:
            async for result in self.user_handler.handle_my(event):
                yield result
        elif subcmd in ["删除", "del", "delete"]:
            async for result in self.user_handler.handle_delete(event):
                yield result
        elif subcmd in ["查询", "query", "q"]:
            if args:
                room = args[0]
                async for result in self.query_handler.handle_query_one(event, room):
                    yield result
            else:
                async for result in self.query_handler.handle_query_all(event):
                    yield result
        elif subcmd == "定时":
            schedule_cmd = args[0] if args else "列表"
            schedule_args = args[1] if len(args) > 1 else ""

            if schedule_cmd in ["添加", "add"]:
                async for result in self.schedule_handler.handle_add(event, schedule_args):
                    yield result
            elif schedule_cmd in ["列表", "list", "ls"]:
                async for result in self.schedule_handler.handle_list(event):
                    yield result
            elif schedule_cmd in ["删除", "del", "delete"]:
                async for result in self.schedule_handler.handle_delete(event):
                    yield result
            elif schedule_cmd in ["设置", "update", "edit"]:
                async for result in self.schedule_handler.handle_update(event, schedule_args):
                    yield result
            else:
                yield event.plain_result("❌ 未知的定时任务命令")
        elif subcmd in ["状态", "status", "st"]:
            async for result in self._handle_status(event):
                yield result
        elif subcmd in ["帮助", "help", "h"]:
            async for result in self._handle_help(event):
                yield result
        else:
            yield event.plain_result(f"❌ 未知命令：{subcmd}\n请使用 {COMMAND_PREFIX} 帮助 查看可用命令")

    async def _handle_status(self, event: AstrMessageEvent):
        """查看状态"""
        from datetime import datetime

        ctx = self.user_handler.get_user_context(event)
        is_admin = ctx.is_admin

        has_session = self.pay_service.has_valid_session()
        has_credentials = await self.credential_repo.exists()
        dorm_count = await self.dorm_repo.count()

        session_info = "未登录"
        if has_session and self.pay_service._session_info:
            elapsed = datetime.now() - self.pay_service._session_info.login_time
            remaining = SESSION_TIMEOUT_MINUTES * 60 - elapsed.total_seconds()
            if remaining > 0:
                session_info = f"已登录 (剩余 {int(remaining // 60)} 分钟)"
            else:
                session_info = "已过期"

        lines = [
            "📋 电费查询插件状态",
            "",
            f"登录状态: {session_info}",
            f"凭证状态: {'已配置' if has_credentials else '未配置'}",
            f"宿舍数量: {dorm_count} 个",
        ]

        if is_admin:
            lines.extend([
                "",
                "管理员信息:",
                f"您的ID: {ctx.user_id}",
            ])

        yield event.plain_result("\n".join(lines))

    async def _handle_help(self, event: AstrMessageEvent):
        """查看帮助"""
        ctx = self.user_handler.get_user_context(event)
        is_admin = ctx.is_admin

        lines = [
            "📖 电费查询插件帮助",
            "",
        ]

        if is_admin:
            lines.extend([
                "【管理员命令】",
                f"{COMMAND_PREFIX} 登录 - 设置缴费系统登录",
                f"{COMMAND_PREFIX} 登出 - 清除登录信息",
                f"{COMMAND_PREFIX} 定时 添加 <时间> - 添加定时发送",
                f"{COMMAND_PREFIX} 定时 列表 - 查看定时任务",
                f"{COMMAND_PREFIX} 定时 删除 - 删除当前群定时任务",
                f"{COMMAND_PREFIX} 定时 设置 <时间> - 修改定时时间",
                "",
            ])

        lines.extend([
            "【用户命令】",
            f"{COMMAND_PREFIX} 设置 - 交互式设置宿舍",
            f"{COMMAND_PREFIX} 我的 - 查看我的宿舍",
            f"{COMMAND_PREFIX} 删除 - 删除我的宿舍",
            "",
            "【查询命令】",
            f"{COMMAND_PREFIX} 查询 - 查询所有宿舍电费",
            f"{COMMAND_PREFIX} 查询 <房间号> - 查询指定房间",
            "",
            "【其他】",
            f"{COMMAND_PREFIX} 状态 - 查看插件状态",
            f"{COMMAND_PREFIX} 帮助 - 查看此帮助",
        ])

        yield event.plain_result("\n".join(lines))
