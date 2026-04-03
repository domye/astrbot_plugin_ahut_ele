"""
查询命令处理器
"""
from astrbot.api.event import AstrMessageEvent, MessageChain

from .base_handler import BaseHandler
from ..models.dto import QueryResult
from ..models.entities import DormConfig, UserContext
from ..core.exceptions import NotConfiguredException
from ..core.logger import log_operation
import astrbot.api.message_components as Comp


class QueryHandler(BaseHandler):
    """查询命令处理器"""

    async def handle_query_all(self, event: AstrMessageEvent):
        """查询所有宿舍"""
        ctx = self.get_user_context(event)

        try:
            # 检查系统是否已配置
            if not await self.plugin.credential_repo.exists():
                raise NotConfiguredException()

            # 获取所有宿舍
            all_dorms = await self.plugin.dorm_repo.get_all_as_list()

            if not all_dorms:
                yield event.plain_result("❌ 还没有人设置宿舍信息，请先使用 电费 设置")
                return

            yield event.plain_result(f"正在查询 {len(all_dorms)} 个宿舍的电费...")

            # 查询所有宿舍
            results = []
            for user_id, dorm in all_dorms:
                try:
                    result = await self.plugin.pay_service.query_full_electricity(
                        campus=dorm.campus,
                        building_name=dorm.building_name,
                        building_id=dorm.building_id,
                        room_id=dorm.room_id,
                    )
                    results.append(QueryResult(
                        dorm_name=dorm.get_display_name(),
                        room_remain=result.room_remain,
                        ac_remain=result.ac_remain,
                        error=result.error,
                        is_low_balance=result.is_low_balance,
                    ))
                except Exception as e:
                    results.append(QueryResult(
                        dorm_name=dorm.get_display_name(),
                        room_remain=0,
                        ac_remain=0,
                        error=str(e),
                    ))

            # 格式化结果
            lines = ["📊 电费查询结果：", ""]
            for result in results:
                lines.append(result.format_message())
                lines.append("")

            yield event.plain_result("\n".join(lines))

        except NotConfiguredException:
            yield event.plain_result("❌ 系统未配置，请等待管理员设置登录信息")
        except Exception as e:
            yield event.plain_result(self.handle_error(e, "查询"))

    async def handle_query_one(self, event: AstrMessageEvent, room: str = ""):
        """查询单个房间"""
        ctx = self.get_user_context(event)

        if not room:
            yield event.plain_result("❌ 请提供房间号，例如：电费 查询 101")
            return

        try:
            # 检查系统是否已配置
            if not await self.plugin.credential_repo.exists():
                raise NotConfiguredException()

            # 获取用户宿舍配置
            dorm = await self.plugin.dorm_repo.get(ctx.user_id)
            if not dorm:
                yield event.plain_result("❌ 您还没有设置宿舍信息，请先使用 电费 设置")
                return

            # 使用已存储的校区和楼栋，但查询指定房间
            result = await self.plugin.pay_service.query_full_electricity(
                campus=dorm.campus,
                building_name=dorm.building_name,
                building_id=dorm.building_id,
                room_id=room,
            )

            if result.error:
                yield event.plain_result(f"❌ 查询失败：{result.error}")
            else:
                query_result = QueryResult(
                    dorm_name=f"{dorm.building_name} {room}",
                    room_remain=result.room_remain,
                    ac_remain=result.ac_remain,
                    is_low_balance=result.is_low_balance,
                )
                yield event.plain_result(query_result.format_message())

        except NotConfiguredException:
            yield event.plain_result("❌ 系统未配置，请等待管理员设置登录信息")
        except Exception as e:
            yield event.plain_result(self.handle_error(e, "查询"))
