"""
用户命令处理器
"""
from astrbot.api.event import AstrMessageEvent
from astrbot.core.utils.session_waiter import session_waiter, SessionController

from .base_handler import BaseHandler
from ..models.entities import DormConfig, UserContext
from ..services.building_service import BuildingService
from ..core.exceptions import NotConfiguredException, ValidationException
from ..core.constants import MAX_SETUP_RETRIES
from ..core.logger import log_operation


class UserHandler(BaseHandler):
    """用户命令处理器"""

    def __init__(self, plugin):
        super().__init__(plugin)
        self.building_service = BuildingService()

    async def handle_setup(self, event: AstrMessageEvent):
        """处理设置宿舍命令"""
        ctx = self.get_user_context(event)

        # 检查系统是否已配置
        if not await self.plugin.credential_repo.exists():
            yield event.plain_result("❌ 系统未配置，请等待管理员设置登录信息")
            return

        yield event.plain_result(self.building_service.format_campus_menu())

        state = {"page": 1, "retry_count": 0}

        @session_waiter(timeout=120)
        async def campus_session(controller: SessionController, ev: AstrMessageEvent):
            if str(ev.get_sender_id()) != ctx.user_id:
                return

            text = ev.message_str.strip()

            if text in ['取消', 'cancel', 'quit', '退出', 'q']:
                await ev.send(ev.plain_result("已取消设置"))
                controller.stop()
                return

            campus = self.building_service.parse_campus_input(text)
            if not campus:
                await ev.send(ev.plain_result("输入无效，请输入 1 或 2 选择校区，或输入'取消'退出："))
                controller.keep(timeout=120)
                return

            campus_name = self.building_service.get_campus_name(campus)
            await ev.send(ev.plain_result(self.building_service.format_building_menu(campus, page=state["page"])))

            @session_waiter(timeout=120)
            async def building_session(ctrl: SessionController, e: AstrMessageEvent):
                if str(e.get_sender_id()) != ctx.user_id:
                    return

                text = e.message_str.strip()
                buildings = self.building_service.get_buildings(campus)
                total = len(buildings)

                if text in ['取消', 'cancel', 'quit', '退出', 'q']:
                    await e.send(e.plain_result("已取消设置"))
                    ctrl.stop()
                    return

                # 处理翻页
                if text.lower() == 'n':
                    state["page"] = min(state["page"] + 1, (total + 19) // 20)
                    await e.send(e.plain_result(self.building_service.format_building_menu(campus, page=state["page"])))
                    ctrl.keep(timeout=120)
                    return

                if text.lower() == 'p':
                    state["page"] = max(state["page"] - 1, 1)
                    await e.send(e.plain_result(self.building_service.format_building_menu(campus, page=state["page"])))
                    ctrl.keep(timeout=120)
                    return

                # 解析楼栋选择
                try:
                    num = int(text)
                    building = self.building_service.get_building_by_index(campus, num)
                    if not building:
                        await e.send(e.plain_result(f"序号超出范围，请输入 1-{total} 之间的数字："))
                        ctrl.keep(timeout=120)
                        return
                except ValueError:
                    await e.send(e.plain_result("请输入数字序号选择楼栋，或输入'取消'退出："))
                    ctrl.keep(timeout=120)
                    return

                await e.send(e.plain_result(
                    f"已选择：{building.name}\n请输入房间号（如：101），或输入'取消'退出："
                ))

                @session_waiter(timeout=120)
                async def room_session(c: SessionController, evt: AstrMessageEvent):
                    if str(evt.get_sender_id()) != ctx.user_id:
                        return

                    room_id = evt.message_str.strip()

                    if room_id in ['取消', 'cancel', 'quit', '退出', 'q']:
                        await evt.send(evt.plain_result("已取消设置"))
                        c.stop()
                        return

                    # 验证房间号
                    if not room_id or not room_id.replace('-', '').replace('_', '').isalnum():
                        await evt.send(evt.plain_result("房间号格式错误，请输入数字或字母数字组合（如：101、A101）："))
                        c.keep(timeout=120)
                        return

                    # 创建宿舍配置
                    dorm = DormConfig(
                        campus=campus,
                        building_id=building.id,
                        building_name=building.name,
                        room_id=room_id,
                    )

                    # 验证宿舍信息
                    await evt.send(evt.plain_result("正在验证宿舍信息..."))

                    try:
                        result = await self.plugin.pay_service.query_full_electricity(
                            campus=campus,
                            building_name=building.name,
                            building_id=building.id,
                            room_id=room_id,
                        )

                        if result.room_remain > 0 or result.ac_remain > 0:
                            await self.plugin.dorm_repo.save(ctx.user_id, dorm)
                            log_operation("设置宿舍", ctx.user_id, True, dorm.get_display_name())
                            await evt.send(evt.plain_result(
                                f"✅ 宿舍设置成功！\n\n{result.format_message()}"
                            ))
                            c.stop()
                        else:
                            state["retry_count"] += 1
                            if state["retry_count"] >= MAX_SETUP_RETRIES:
                                await evt.send(evt.plain_result(
                                    f"❌ 验证失败次数过多\n错误：{result.error or '未查询到电费信息'}"
                                ))
                                c.stop()
                            else:
                                await evt.send(evt.plain_result(
                                    f"❌ 验证失败：{result.error or '未查询到电费信息'}\n"
                                    f"请重新输入房间号（{MAX_SETUP_RETRIES - state['retry_count']}次机会）："
                                ))
                                c.keep(timeout=120)
                    except Exception as ex:
                        await evt.send(evt.plain_result(self.handle_error(ex, "验证")))
                        c.stop()

                try:
                    await room_session(e)
                except TimeoutError:
                    await e.send(e.plain_result("⏱️ 输入超时，请重新执行 /电费 设置"))

                ctrl.stop()

            try:
                await building_session(ev)
            except TimeoutError:
                await ev.send(ev.plain_result("⏱️ 输入超时，请重新执行 /电费 设置"))

            controller.stop()

        try:
            await campus_session(event)
        except TimeoutError:
            yield event.plain_result("⏱️ 输入超时，请重新执行 /电费 设置")
        finally:
            event.stop_event()

    async def handle_my(self, event: AstrMessageEvent):
        """查看我的宿舍"""
        ctx = self.get_user_context(event)

        try:
            dorm = await self.plugin.dorm_repo.get(ctx.user_id)
            if dorm:
                yield event.plain_result(f"🏠 您设置的宿舍：{dorm.get_display_name()}")
            else:
                yield event.plain_result("❌ 您还没有设置宿舍信息，请使用 /电费 设置")
        except Exception as e:
            yield event.plain_result(self.handle_error(e, "查询"))

    async def handle_delete(self, event: AstrMessageEvent):
        """删除宿舍设置"""
        ctx = self.get_user_context(event)

        try:
            removed = await self.plugin.dorm_repo.delete(ctx.user_id)
            if removed:
                log_operation("删除宿舍", ctx.user_id, True)
                yield event.plain_result("✅ 已删除您的宿舍设置")
            else:
                yield event.plain_result("❌ 您还没有设置宿舍信息")
        except Exception as e:
            yield event.plain_result(self.handle_error(e, "删除"))
