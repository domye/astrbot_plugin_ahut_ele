"""
管理员命令处理器
"""
from astrbot.api.event import AstrMessageEvent
from astrbot.core.utils.session_waiter import session_waiter, SessionController

from .base_handler import BaseHandler
from ..models.entities import PayCredentials, UserContext
from ..models.dto import LoginResult
from ..core.exceptions import ValidationException
from ..core.logger import log_operation, log_auth_event


class AdminHandler(BaseHandler):
    """管理员命令处理器"""

    async def handle_login(self, event: AstrMessageEvent):
        """处理登录命令"""
        ctx = self.get_user_context(event)

        try:
            ctx.require_admin()
        except Exception as e:
            yield event.plain_result(f"❌ {e}")
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

                # 尝试登录
                success, message = await self.plugin.pay_service.login(username, password)

                if success:
                    # 保存凭证
                    creds = PayCredentials(username=username, password=password)
                    await self.plugin.credential_repo.save("default", creds)
                    self.plugin.pay_service.set_credentials(creds)

                    log_auth_event(ctx.user_id, "登录", True)
                    await e.send(e.plain_result(f"✅ 登录成功！{message}\n已保存登录信息。"))
                else:
                    log_auth_event(ctx.user_id, "登录", False)
                    await e.send(e.plain_result(f"❌ 登录失败：{message}\n请重新输入用户名："))
                    controller.keep(timeout=60)

                ctrl.stop()

            try:
                await password_session(ev)
            except TimeoutError:
                await ev.send(ev.plain_result("⏱️ 输入超时，请重新执行 /电费 登录"))

            controller.stop()

        try:
            await login_session(event)
        except TimeoutError:
            yield event.plain_result("⏱️ 输入超时，请重新执行 /电费 登录")
        finally:
            event.stop_event()

    async def handle_logout(self, event: AstrMessageEvent):
        """处理登出命令"""
        ctx = self.get_user_context(event)

        try:
            ctx.require_admin()
        except Exception as e:
            yield event.plain_result(f"❌ {e}")
            return

        try:
            # 清除凭证
            await self.plugin.credential_repo.delete("default")
            self.plugin.pay_service.clear_credentials()

            log_operation("登出", ctx.user_id, True)
            yield event.plain_result("✅ 已清除登录信息")
        except Exception as e:
            yield event.plain_result(self.handle_error(e, "登出"))
