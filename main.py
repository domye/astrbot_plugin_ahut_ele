"""AHUT Electricity Query Plugin for AstrBot.

Features:
- Admin can set pay system login credentials
- Users can set their dormitory configuration
- Query electricity for all configured dorms
"""

from astrbot.api.event import filter, AstrMessageEvent, MessageChain
from astrbot.api.star import Context, Star, register
from astrbot.api import AstrBotConfig, logger
from astrbot.core.utils.session_waiter import session_waiter, SessionController
from pathlib import Path
import json
import asyncio

import astrbot.api.message_components as Comp

from .services import PayService, DormManager, ScheduleManager
from .services.building_data import (
    CAMPUS_OPTIONS, get_buildings, get_building_by_id,
    format_campus_menu, format_building_menu, parse_campus_input
)
from .models import DormConfig, ElectricityResult


@register("ahut_ele", "domye", "安徽工业大学电费查询插件", "1.0.0")
class AhutElePlugin(Star):
    """AHUT electricity query plugin."""

    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config

        # Services
        self.pay_service = PayService()
        self.dorm_manager = DormManager(self.name)
        self.schedule_manager = ScheduleManager(self.name)

        # Admin users from config
        self.admin_users = config.get("admin_users", [])

        # Credentials storage path
        self._data_path = Path("data/plugin_data") / self.name

    async def initialize(self):
        """Initialize the plugin."""
        self._data_path.mkdir(parents=True, exist_ok=True)

        # Initialize dorm manager
        await self.dorm_manager.initialize()

        # Initialize schedule manager
        await self.schedule_manager.initialize()

        # Load stored credentials
        await self._load_credentials()

        # Start scheduler
        self.schedule_manager.start_scheduler(self._send_scheduled_query)

        logger.info(f"{self.name} initialized")

    async def terminate(self):
        """Cleanup on shutdown."""
        # Stop scheduler
        self.schedule_manager.stop_scheduler()

        await self.pay_service.close()
        logger.info(f"{self.name} terminated")

    async def _load_credentials(self):
        """Load stored credentials."""
        creds_file = self._data_path / "credentials.json"
        if creds_file.exists():
            try:
                with open(creds_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                username = data.get("username", "")
                password = data.get("password", "")
                if username and password:
                    self.pay_service.set_credentials(username, password)
                    logger.info("Loaded stored credentials")
            except Exception as e:
                logger.error(f"Failed to load credentials: {e}")

    async def _save_credentials(self, username: str, password: str):
        """Save credentials to file."""
        creds_file = self._data_path / "credentials.json"
        try:
            # Note: Password is stored locally, not in keyring for simplicity
            # In production, consider using keyring or encryption
            data = {"username": username, "password": password}
            with open(creds_file, 'w', encoding='utf-8') as f:
                json.dump(data, f)
            logger.info("Credentials saved")
        except Exception as e:
            logger.error(f"Failed to save credentials: {e}")

    async def _clear_credentials(self):
        """Clear stored credentials."""
        creds_file = self._data_path / "credentials.json"
        if creds_file.exists():
            try:
                creds_file.unlink()
            except Exception as e:
                logger.error(f"Failed to delete credentials file: {e}")

    def _is_admin(self, sender_id: str) -> bool:
        """Check if user is admin."""
        # If no admin configured, first user can become admin
        if not self.admin_users:
            return True
        return sender_id in self.admin_users or str(sender_id) in self.admin_users

    # === Admin Commands ===

    @filter.command("ele_login")
    async def ele_login(self, event: AstrMessageEvent):
        """设置缴费系统登录信息（管理员）。用法: /ele_login"""
        sender_id = str(event.get_sender_id())

        if not self._is_admin(sender_id):
            yield event.plain_result("权限不足，此命令仅限管理员使用。")
            event.stop_event()
            return

        yield event.plain_result("请输入缴费系统用户名（学号）：")

        @session_waiter(timeout=60)
        async def login_session(controller: SessionController, ev: AstrMessageEvent):
            username = ev.message_str.strip()

            if not username:
                await ev.send(ev.plain_result("用户名不能为空，请重新输入："))
                controller.keep(timeout=60)
                return

            await ev.send(ev.plain_result("请输入缴费系统密码："))

            @session_waiter(timeout=60)
            async def password_session(ctrl: SessionController, e: AstrMessageEvent):
                password = e.message_str.strip()

                if not password:
                    await e.send(e.plain_result("密码不能为空，请重新输入："))
                    ctrl.keep(timeout=60)
                    return

                # Try login
                success, message = await self.pay_service.login(username, password)

                if success:
                    # Save credentials
                    self.pay_service.set_credentials(username, password)
                    await self._save_credentials(username, password)
                    await e.send(e.plain_result(f"登录成功！{message}\n已保存登录信息。"))
                else:
                    await e.send(e.plain_result(f"登录失败：{message}\n请重新输入用户名："))
                    controller.keep(timeout=60)

                ctrl.stop()

            try:
                await password_session(ev)
            except TimeoutError:
                await ev.send(ev.plain_result("输入超时，请重新执行 /ele_login"))

            controller.stop()

        try:
            await login_session(event)
        except TimeoutError:
            yield event.plain_result("输入超时，请重新执行 /ele_login")
        finally:
            event.stop_event()

    @filter.command("ele_logout")
    async def ele_logout(self, event: AstrMessageEvent):
        """清除缴费系统登录信息（管理员）。用法: /ele_logout"""
        sender_id = str(event.get_sender_id())

        if not self._is_admin(sender_id):
            yield event.plain_result("权限不足，此命令仅限管理员使用。")
            event.stop_event()
            return

        self.pay_service.clear_credentials()
        await self._clear_credentials()

        yield event.plain_result("已清除登录信息。")

    # === User Commands ===

    @filter.command("ele_set")
    async def ele_set(self, event: AstrMessageEvent):
        """设置宿舍信息。用法: /ele_set"""
        sender_id = str(event.get_sender_id())

        # Check if system is configured
        if not self.pay_service._credentials:
            yield event.plain_result("系统未配置，请等待管理员设置登录信息。")
            event.stop_event()
            return

        # Step 1: Select campus
        yield event.plain_result(format_campus_menu())

        # Store state for pagination and retry
        state = {"page": 1, "retry_count": 0}
        MAX_RETRY = 3

        @session_waiter(timeout=120)
        async def campus_session(controller: SessionController, ev: AstrMessageEvent):
            # Check if this is the original sender
            if str(ev.get_sender_id()) != sender_id:
                return  # Ignore messages from other users

            text = ev.message_str.strip()

            # Cancel command
            if text in ['取消', 'cancel', 'quit', '退出', 'q']:
                await ev.send(ev.plain_result("已取消设置。"))
                controller.stop()
                return

            campus = parse_campus_input(text)

            if not campus:
                await ev.send(ev.plain_result("输入无效，请输入 1 或 2 选择校区，或输入'取消'退出："))
                controller.keep(timeout=120)
                return

            campus_name = CAMPUS_OPTIONS[campus]

            # Step 2: Select building
            await ev.send(ev.plain_result(format_building_menu(campus, page=state["page"])))

            @session_waiter(timeout=120)
            async def building_session(ctrl: SessionController, e: AstrMessageEvent):
                # Check sender
                if str(e.get_sender_id()) != sender_id:
                    return

                text = e.message_str.strip()
                buildings = get_buildings(campus)
                total = len(buildings)

                # Cancel command
                if text in ['取消', 'cancel', 'quit', '退出', 'q']:
                    await e.send(e.plain_result("已取消设置。"))
                    ctrl.stop()
                    return

                # Check for pagination
                if text.lower() == 'n':
                    state["page"] = min(state["page"] + 1, (total + 19) // 20)
                    await e.send(e.plain_result(format_building_menu(campus, page=state["page"])))
                    ctrl.keep(timeout=120)
                    return

                if text.lower() == 'p':
                    state["page"] = max(state["page"] - 1, 1)
                    await e.send(e.plain_result(format_building_menu(campus, page=state["page"])))
                    ctrl.keep(timeout=120)
                    return

                # Parse building selection
                try:
                    num = int(text)
                    if 1 <= num <= total:
                        building = buildings[num - 1]
                    else:
                        await e.send(e.plain_result(f"序号超出范围，请输入 1-{total} 之间的数字："))
                        ctrl.keep(timeout=120)
                        return
                except ValueError:
                    await e.send(e.plain_result("请输入数字序号选择楼栋，或输入'取消'退出："))
                    ctrl.keep(timeout=120)
                    return

                # Step 3: Input room number
                await e.send(e.plain_result(
                    f"已选择：{building.name}\n"
                    f"请输入房间号（如：101），或输入'取消'退出："
                ))

                @session_waiter(timeout=120)
                async def room_session(c: SessionController, evt: AstrMessageEvent):
                    # Check sender
                    if str(evt.get_sender_id()) != sender_id:
                        return

                    room_id = evt.message_str.strip()

                    # Cancel command
                    if room_id in ['取消', 'cancel', 'quit', '退出', 'q']:
                        await evt.send(evt.plain_result("已取消设置。"))
                        c.stop()
                        return

                    # Validate room number format (must be alphanumeric)
                    if not room_id or not room_id.replace('-', '').replace('_', '').isalnum():
                        await evt.send(evt.plain_result("房间号格式错误，请输入数字或字母数字组合（如：101、A101）："))
                        c.keep(timeout=120)
                        return

                    # Create dorm config
                    dorm = DormConfig(
                        campus=campus,
                        building_id=building.id,
                        building_name=building.name,
                        room_id=room_id,
                        dorm_name=f"{campus_name} {building.name} {room_id}",
                    )

                    # Verify by querying
                    await evt.send(evt.plain_result("正在验证宿舍信息..."))

                    result = await self.pay_service.get_full_electricity(
                        campus=campus,
                        building_name=building.name,
                        building_id=building.id,
                        room_id=room_id,
                        dorm_name=dorm.get_display_name(),
                    )

                    if result.room_remain > 0 or result.ac_remain > 0:
                        # Save dorm config
                        await self.dorm_manager.set_dorm(sender_id, dorm)
                        await evt.send(evt.plain_result(
                            f"✅ 宿舍设置成功！\n\n{result.format_result()}"
                        ))
                        c.stop()
                    else:
                        state["retry_count"] += 1
                        if state["retry_count"] >= MAX_RETRY:
                            await evt.send(evt.plain_result(
                                f"验证失败次数过多，请重新执行 /ele_set\n"
                                f"错误：{result.error or '未查询到电费信息'}"
                            ))
                            c.stop()
                        else:
                            await evt.send(evt.plain_result(
                                f"❌ 验证失败：{result.error or '未查询到电费信息'}\n"
                                f"请重新输入房间号（{MAX_RETRY - state['retry_count']}次机会）："
                            ))
                            c.keep(timeout=120)

                try:
                    await room_session(e)
                except TimeoutError:
                    await e.send(e.plain_result("输入超时，请重新执行 /ele_set"))

                ctrl.stop()

            try:
                await building_session(ev)
            except TimeoutError:
                await ev.send(ev.plain_result("输入超时，请重新执行 /ele_set"))

            controller.stop()

        try:
            await campus_session(event)
        except TimeoutError:
            yield event.plain_result("输入超时，请重新执行 /ele_set")
        finally:
            event.stop_event()

    @filter.command("ele_my")
    async def ele_my(self, event: AstrMessageEvent):
        """查看我设置的宿舍。用法: /ele_my"""
        sender_id = str(event.get_sender_id())

        dorm = await self.dorm_manager.get_dorm(sender_id)

        if not dorm:
            yield event.plain_result("您还没有设置宿舍信息，请使用 /ele_set 设置。")
            return

        yield event.plain_result(f"您设置的宿舍：{dorm.get_display_name()}")

    @filter.command("ele_del")
    async def ele_del(self, event: AstrMessageEvent):
        """删除我的宿舍设置。用法: /ele_del"""
        sender_id = str(event.get_sender_id())

        removed = await self.dorm_manager.remove_dorm(sender_id)

        if removed:
            yield event.plain_result("已删除您的宿舍设置。")
        else:
            yield event.plain_result("您还没有设置宿舍信息。")

    # === Query Commands ===

    @filter.command("ele")
    async def ele_query(self, event: AstrMessageEvent):
        """查询电费。用法: /ele [宿舍号]\n无参数时查询所有已设置的宿舍"""
        sender_id = str(event.get_sender_id())

        # Check if system is configured
        if not self.pay_service._credentials:
            yield event.plain_result("系统未配置，请等待管理员设置登录信息。")
            return

        # Get all dorms
        all_dorms = await self.dorm_manager.get_all_dorms()

        if not all_dorms:
            yield event.plain_result("还没有人设置宿舍信息。请先使用 /ele_set 设置。")
            return

        # Query all dorms
        yield event.plain_result(f"正在查询 {len(all_dorms)} 个宿舍的电费...")

        try:
            results = await self.pay_service.query_multiple(all_dorms)

            # Format results
            lines = ["📊 电费查询结果：", ""]
            for sid, dorm, result in results:
                lines.append(result.format_result())
                lines.append("")

            yield event.plain_result("\n".join(lines))

        except Exception as e:
            logger.error(f"Query failed: {e}", exc_info=True)
            yield event.plain_result(f"查询失败：{e}")

    @filter.command("ele_one")
    async def ele_one(self, event: AstrMessageEvent, room: str = ""):
        """查询单个宿舍电费。用法: /ele_one <宿舍号>"""
        sender_id = str(event.get_sender_id())

        if not room:
            yield event.plain_result("请提供宿舍号，例如：/ele_one 101")
            return

        # Check if system is configured
        if not self.pay_service._credentials:
            yield event.plain_result("系统未配置，请等待管理员设置登录信息。")
            return

        # Check if user has dorm set
        dorm = await self.dorm_manager.get_dorm(sender_id)

        if not dorm:
            yield event.plain_result("您还没有设置宿舍信息，请先使用 /ele_set 设置。")
            return

        # Use stored dorm config but with provided room number
        query_dorm = DormConfig(
            campus=dorm.campus,
            building_id=dorm.building_id,
            building_name=dorm.building_name,
            room_id=room,
            dorm_name=f"{dorm.building_name} {room}",
        )

        try:
            result = await self.pay_service.get_full_electricity(
                campus=query_dorm.campus,
                building_name=query_dorm.building_name,
                building_id=query_dorm.building_id,
                room_id=query_dorm.room_id,
                dorm_name=query_dorm.get_display_name(),
            )

            if result.error:
                yield event.plain_result(f"查询失败：{result.error}")
            else:
                yield event.plain_result(result.format_result())

        except Exception as e:
            logger.error(f"Query one failed: {e}")
            yield event.plain_result(f"查询失败：{e}")

    # === Status Commands ===

    @filter.command("ele_status")
    async def ele_status(self, event: AstrMessageEvent):
        """查看插件状态。用法: /ele_status"""
        sender_id = str(event.get_sender_id())
        is_admin = self._is_admin(sender_id)

        # Get status
        has_session = self.pay_service.has_session()
        has_credentials = self.pay_service._credentials is not None
        dorm_count = await self.dorm_manager.get_dorm_count()

        lines = [
            "📋 电费查询插件状态",
            "",
            f"登录状态: {'已登录' if has_session else '未登录'}",
            f"凭证状态: {'已配置' if has_credentials else '未配置'}",
            f"宿舍数量: {dorm_count} 个",
        ]

        if is_admin:
            lines.extend([
                "",
                "管理员信息:",
                f"您的ID: {sender_id}",
                f"管理员列表: {self.admin_users or '(未设置，所有人可管理)'}",
            ])

        yield event.plain_result("\n".join(lines))

    @filter.command("ele_help")
    async def ele_help(self, event: AstrMessageEvent):
        """查看帮助信息。用法: /ele_help"""
        lines = [
            "📖 电费查询插件帮助",
            "",
            "【管理员命令】",
            "/ele_login - 设置缴费系统登录",
            "/ele_logout - 清除登录信息",
            "/ele_schedule_add <时间> - 添加定时发送（如：8:00,20:00）",
            "/ele_schedule_list - 查看所有定时任务",
            "/ele_schedule_del - 删除当前群的定时任务",
            "/ele_schedule_edit <时间> - 修改当前群的定时时间",
            "",
            "【用户命令】",
            "/ele_set - 交互式设置宿舍（推荐）",
            "/ele_my - 查看我的宿舍",
            "/ele_del - 删除我的宿舍",
            "",
            "【查询命令】",
            "/ele - 查询所有宿舍电费",
            "/ele_one <房间号> - 查询指定房间",
            "",
            "【其他】",
            "/ele_status - 查看插件状态",
            "/ele_help - 查看此帮助",
            "",
            "💡 提示：使用 /ele_set 时会引导你选择校区、楼栋和房间号",
            "💡 提示：定时发送会在指定时间自动推送所有宿舍的电费信息",
        ]

        yield event.plain_result("\n".join(lines))

    # === Scheduled Task Methods ===

    async def _send_scheduled_query(self, group_umo: str):
        """Send scheduled electricity query to a group."""
        # Check if system is configured
        if not self.pay_service._credentials:
            logger.warning("System not configured, skipping scheduled query")
            return

        # Get all dorms
        all_dorms = await self.dorm_manager.get_all_dorms()

        if not all_dorms:
            logger.info("No dorms configured, skipping scheduled query")
            return

        try:
            results = await self.pay_service.query_multiple(all_dorms)

            # Format results
            lines = ["📊 定时电费查询结果：", ""]
            for sid, dorm, result in results:
                lines.append(result.format_result())
                lines.append("")

            message = "\n".join(lines)

            # Send message
            message_chain = MessageChain().message(message)
            await self.context.send_message(group_umo, message_chain)
            logger.info(f"Sent scheduled query to {group_umo}")

        except Exception as e:
            logger.error(f"Scheduled query failed: {e}", exc_info=True)

    # === Schedule Commands ===

    @filter.command("ele_schedule_add")
    async def ele_schedule_add(self, event: AstrMessageEvent, times: str = ""):
        """添加定时发送任务（管理员）。用法: /ele_schedule_add <时间1,时间2,...>"""
        sender_id = str(event.get_sender_id())

        if not self._is_admin(sender_id):
            yield event.plain_result("权限不足，此命令仅限管理员使用。")
            event.stop_event()
            return

        if not times:
            yield event.plain_result("请提供发送时间，例如：/ele_schedule_add 8:00,20:00")
            return

        # Parse times
        parsed_times = self.schedule_manager.parse_times(times)

        if not parsed_times:
            yield event.plain_result("时间格式错误，请使用格式如：8:00,20:00")
            return

        # Get group UMO
        group_umo = event.unified_msg_origin
        group_name = group_umo.split(':')[-1] if ':' in group_umo else group_umo

        # Add task
        task = await self.schedule_manager.add_task(group_umo, group_name, parsed_times)

        yield event.plain_result(
            f"✅ 定时发送任务已添加\n"
            f"群聊: {group_name}\n"
            f"发送时间: {', '.join(task.times)}\n"
            f"发送内容: 所有宿舍的电费查询结果"
        )

    @filter.command("ele_schedule_list")
    async def ele_schedule_list(self, event: AstrMessageEvent):
        """查看所有定时任务（管理员）。用法: /ele_schedule_list"""
        sender_id = str(event.get_sender_id())

        if not self._is_admin(sender_id):
            yield event.plain_result("权限不足，此命令仅限管理员使用。")
            event.stop_event()
            return

        tasks = await self.schedule_manager.get_all_tasks()

        if not tasks:
            yield event.plain_result("暂无定时发送任务。")
            return

        lines = ["📋 定时发送任务列表：", ""]
        for i, task in enumerate(tasks, 1):
            lines.append(f"{i}. 群聊: {task.group_name}")
            lines.append(f"   时间: {', '.join(task.times)}")
            lines.append("")

        yield event.plain_result("\n".join(lines))

    @filter.command("ele_schedule_del")
    async def ele_schedule_del(self, event: AstrMessageEvent):
        """删除当前群的定时任务（管理员）。用法: /ele_schedule_del"""
        sender_id = str(event.get_sender_id())

        if not self._is_admin(sender_id):
            yield event.plain_result("权限不足，此命令仅限管理员使用。")
            event.stop_event()
            return

        group_umo = event.unified_msg_origin

        removed = await self.schedule_manager.remove_task(group_umo)

        if removed:
            yield event.plain_result("✅ 已删除当前群的定时发送任务。")
        else:
            yield event.plain_result("当前群没有设置定时发送任务。")

    @filter.command("ele_schedule_edit")
    async def ele_schedule_edit(self, event: AstrMessageEvent, times: str = ""):
        """修改当前群的定时任务（管理员）。用法: /ele_schedule_edit <时间1,时间2,...>"""
        sender_id = str(event.get_sender_id())

        if not self._is_admin(sender_id):
            yield event.plain_result("权限不足，此命令仅限管理员使用。")
            event.stop_event()
            return

        if not times:
            yield event.plain_result("请提供发送时间，例如：/ele_schedule_edit 8:00,20:00")
            return

        # Parse times
        parsed_times = self.schedule_manager.parse_times(times)

        if not parsed_times:
            yield event.plain_result("时间格式错误，请使用格式如：8:00,20:00")
            return

        # Get group UMO
        group_umo = event.unified_msg_origin
        group_name = group_umo.split(':')[-1] if ':' in group_umo else group_umo

        # Check if task exists
        existing = await self.schedule_manager.get_task(group_umo)
        if not existing:
            yield event.plain_result("当前群没有设置定时发送任务，请先使用 /ele_schedule_add 添加。")
            return

        # Update task
        task = await self.schedule_manager.add_task(group_umo, group_name, parsed_times)

        yield event.plain_result(
            f"✅ 定时发送任务已修改\n"
            f"群聊: {group_name}\n"
            f"发送时间: {', '.join(task.times)}"
        )