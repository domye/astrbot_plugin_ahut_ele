"""
定时任务命令处理器
"""
from astrbot.api.event import AstrMessageEvent

from .base_handler import BaseHandler
from ..core.exceptions import ValidationException
from ..core.logger import log_operation


class ScheduleHandler(BaseHandler):
    """定时任务命令处理器"""

    async def handle_add(self, event: AstrMessageEvent, times: str = ""):
        """添加定时任务"""
        ctx = self.get_user_context(event)

        try:
            ctx.require_admin()
        except Exception as e:
            yield event.plain_result(f"❌ {e}")
            return

        if not times:
            yield event.plain_result("❌ 请提供发送时间，例如：/电费 定时 添加 8:00,20:00")
            return

        try:
            parsed_times = self.plugin.scheduler_service.parse_times(times)

            if not parsed_times:
                yield event.plain_result("❌ 时间格式错误，请使用格式如：8:00,20:00")
                return

            group_umo = event.unified_msg_origin
            group_name = group_umo.split(':')[-1] if ':' in group_umo else group_umo

            task = await self.plugin.scheduler_service.add_task(group_umo, group_name, parsed_times)

            log_operation("添加定时任务", ctx.user_id, True, f"{group_name}: {', '.join(task.times)}")
            yield event.plain_result(
                f"✅ 定时发送任务已添加\n"
                f"群聊: {group_name}\n"
                f"发送时间: {', '.join(task.times)}"
            )
        except Exception as e:
            yield event.plain_result(self.handle_error(e, "添加定时任务"))

    async def handle_list(self, event: AstrMessageEvent):
        """查看定时任务列表"""
        ctx = self.get_user_context(event)

        try:
            ctx.require_admin()
        except Exception as e:
            yield event.plain_result(f"❌ {e}")
            return

        try:
            tasks = await self.plugin.scheduler_service.get_all_tasks()

            if not tasks:
                yield event.plain_result("暂无定时发送任务")
                return

            lines = ["📋 定时发送任务列表：", ""]
            for i, task in enumerate(tasks, 1):
                lines.append(f"{i}. 群聊: {task.group_name}")
                lines.append(f"   时间: {', '.join(task.times)}")
                lines.append("")

            yield event.plain_result("\n".join(lines))
        except Exception as e:
            yield event.plain_result(self.handle_error(e, "查询定时任务"))

    async def handle_delete(self, event: AstrMessageEvent):
        """删除定时任务"""
        ctx = self.get_user_context(event)

        try:
            ctx.require_admin()
        except Exception as e:
            yield event.plain_result(f"❌ {e}")
            return

        try:
            group_umo = event.unified_msg_origin
            removed = await self.plugin.scheduler_service.remove_task(group_umo)

            if removed:
                log_operation("删除定时任务", ctx.user_id, True)
                yield event.plain_result("✅ 已删除当前群的定时发送任务")
            else:
                yield event.plain_result("当前群没有设置定时发送任务")
        except Exception as e:
            yield event.plain_result(self.handle_error(e, "删除定时任务"))

    async def handle_update(self, event: AstrMessageEvent, times: str = ""):
        """修改定时任务"""
        ctx = self.get_user_context(event)

        try:
            ctx.require_admin()
        except Exception as e:
            yield event.plain_result(f"❌ {e}")
            return

        if not times:
            yield event.plain_result("❌ 请提供发送时间，例如：/电费 定时 设置 8:00,20:00")
            return

        try:
            parsed_times = self.plugin.scheduler_service.parse_times(times)

            if not parsed_times:
                yield event.plain_result("❌ 时间格式错误，请使用格式如：8:00,20:00")
                return

            group_umo = event.unified_msg_origin
            existing = await self.plugin.scheduler_service.get_task(group_umo)

            if not existing:
                yield event.plain_result("❌ 当前群没有设置定时发送任务，请先使用 /电费 定时 添加")
                return

            group_name = group_umo.split(':')[-1] if ':' in group_umo else group_umo
            task = await self.plugin.scheduler_service.add_task(group_umo, group_name, parsed_times)

            log_operation("修改定时任务", ctx.user_id, True)
            yield event.plain_result(
                f"✅ 定时发送任务已修改\n"
                f"群聊: {group_name}\n"
                f"发送时间: {', '.join(task.times)}"
            )
        except Exception as e:
            yield event.plain_result(self.handle_error(e, "修改定时任务"))
