"""
缴费系统服务
"""
import aiohttp
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Tuple

from ..core.constants import (
    REQUEST_TIMEOUT_SECONDS,
    MAX_RETRIES,
    PAY_SYSTEM_LOGIN_SERVICE_URL,
    PAY_SYSTEM_IMS_SERVICE_URL,
    PAY_SYSTEM_LOGIN_URL,
    PAY_SYSTEM_IMS_URL,
)
from ..core.exceptions import PaySystemException, AuthException
from ..core.logger import log_service_call
from ..models.entities import PayCredentials, SessionInfo, ElectricityData
from ..utils.rsa_utils import encrypt_password_with_rsa


class PayService:
    """缴费系统服务"""

    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
        self._session_info: Optional[SessionInfo] = None
        self._credentials: Optional[PayCredentials] = None
        self._timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS)

    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建HTTP会话"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=self._timeout,
                headers={"User-Agent": "AHUT-Ele-AstrBot/1.0"}
            )
        return self._session

    async def close(self):
        """关闭HTTP会话"""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    def has_valid_session(self) -> bool:
        """检查是否有有效会话"""
        if self._session_info is None:
            return False
        return not self._session_info.is_expired

    def clear_session(self):
        """清除会话"""
        self._session_info = None

    def set_credentials(self, credentials: PayCredentials):
        """设置凭证"""
        self._credentials = credentials

    def clear_credentials(self):
        """清除凭证"""
        self._credentials = None
        self._session_info = None

    async def login(self, username: str = None, password: str = None) -> Tuple[bool, str]:
        """登录缴费系统"""
        # 使用提供的凭证或已存储的凭证
        if username and password:
            creds = PayCredentials(username=username, password=password)
        elif self._credentials:
            creds = self._credentials
        else:
            return False, "未提供登录凭证"

        try:
            session = await self._get_session()

            # RSA加密密码
            encrypted_pwd = encrypt_password_with_rsa(creds.password)

            form_data = {
                "username": creds.username,
                "pwd": encrypted_pwd,
            }

            resp = await session.post(
                PAY_SYSTEM_LOGIN_SERVICE_URL,
                data=form_data,
                headers={"Referer": PAY_SYSTEM_LOGIN_URL},
                allow_redirects=False,
            )

            # 提取Cookie
            cookie_str = ""
            for name, morsel in resp.cookies.items():
                cookie_str += f"{name}={morsel.value}; "
            cookie_str = cookie_str.strip()

            if cookie_str:
                session.headers["Cookie"] = cookie_str

            status = resp.status
            body = await resp.text()

            if status == 302:
                self._session_info = SessionInfo(cookie=cookie_str, login_time=datetime.now())
                self.set_credentials(creds)
                log_service_call("PayService", "login", True)
                return True, "登录成功"

            if status == 200:
                if "用户名或密码错误" in body or "登录失败" in body:
                    return False, "用户名或密码错误"

                if cookie_str:
                    self._session_info = SessionInfo(cookie=cookie_str, login_time=datetime.now())
                    self.set_credentials(creds)
                    log_service_call("PayService", "login", True)
                    return True, "登录成功"

            return False, f"登录失败 (状态码: {status})"

        except aiohttp.ClientError as e:
            log_service_call("PayService", "login", False, str(e))
            return False, f"网络错误: {e}"
        except Exception as e:
            log_service_call("PayService", "login", False, str(e))
            raise PaySystemException(f"登录失败: {e}")

    async def ensure_login(self) -> Tuple[bool, str]:
        """确保已登录"""
        if self.has_valid_session():
            return True, "已登录"

        if not self._credentials:
            return False, "请先配置登录信息"

        return await self.login()

    async def query_electricity(
        self,
        campus: str,
        building_name: str,
        building_id: str,
        room_id: str,
        etype: str = "L",
    ) -> ElectricityData:
        """查询电费"""
        success, message = await self.ensure_login()
        if not success:
            raise AuthException(message)

        last_error = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                session = await self._get_session()

                form_data = {
                    "xiaoqu": campus,
                    "ld_Name": building_name,
                    "ld_Id": building_id,
                    "Room_No": room_id,
                    "etype": etype,
                }

                resp = await session.post(
                    PAY_SYSTEM_IMS_SERVICE_URL,
                    data=form_data,
                    headers={"Referer": PAY_SYSTEM_IMS_URL},
                )

                if resp.status != 200:
                    raise PaySystemException(f"请求失败: {resp.status}")

                data = await resp.json()
                code = data.get("Code", -1)

                if code == 0:
                    data_field = data.get("Data", {})
                    return ElectricityData(
                        room_remain=data_field.get("RemainAmp", 0) if etype == "L" else 0,
                        ac_remain=data_field.get("RemainAmp", 0) if etype == "K" else 0,
                        room_total=data_field.get("AllAmp", 0),
                        room_used=data_field.get("UsedAmp", 0),
                    )
                else:
                    return ElectricityData(error=data.get("Msg", "查询失败"))

            except asyncio.TimeoutError:
                last_error = "请求超时"
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(attempt)
                continue
            except aiohttp.ClientError as e:
                last_error = f"网络错误: {e}"
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(attempt)
                continue
            except Exception as e:
                raise PaySystemException(f"查询异常: {e}")

        return ElectricityData(error=last_error or f"查询失败，已重试{MAX_RETRIES}次")

    async def query_full_electricity(
        self,
        campus: str,
        building_name: str,
        building_id: str,
        room_id: str,
    ) -> ElectricityData:
        """查询完整电费（房间+空调）"""
        try:
            # 并行查询
            room_task = self.query_electricity(campus, building_name, building_id, room_id, "L")
            ac_task = self.query_electricity(campus, building_name, building_id, room_id, "K")

            room_data, ac_data = await asyncio.gather(room_task, ac_task)

            result = ElectricityData(
                room_remain=room_data.room_remain,
                ac_remain=ac_data.ac_remain,
                error=room_data.error or ac_data.error,
            )

            if not result.error and room_data.room_remain == 0 and ac_data.ac_remain == 0:
                result.error = "未查询到电费信息"

            return result

        except Exception as e:
            return ElectricityData(error=str(e))
