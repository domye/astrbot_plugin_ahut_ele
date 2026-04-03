"""缴费系统服务 - 安工大电费查询

参考: ahut-tool/backend/pay/
"""

import aiohttp
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple
from astrbot.api import logger
from ..models import IMSResponse, ElectricityResult
from .rsa_utils import encrypt_password_with_rsa


class PayService:
    """与安工大缴费系统交互的服务"""

    # API 地址
    BASE_URL = "https://pay.ahut.edu.cn"
    LOGIN_URL = BASE_URL + "/Account/Login"
    LOGIN_SERVICE_URL = BASE_URL + "/Account/LoginService"
    IMS_URL = BASE_URL + "/Charge/IMS?state=WXSTATEFLAG"
    IMS_SERVICE_URL = BASE_URL + "/Charge/GetIMS_AHUTService"

    # 会话超时：30分钟
    SESSION_TIMEOUT = timedelta(minutes=30)

    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
        self._cookie: str = ""
        self._credentials: Optional[Tuple[str, str]] = None  # (用户名, 密码)
        self._login_time: Optional[datetime] = None  # 上次成功登录时间

    # 请求超时：每次尝试10秒
    REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=10)
    # 电费查询最大重试次数
    MAX_RETRIES = 3

    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建HTTP会话"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=self.REQUEST_TIMEOUT,
                headers={"User-Agent": "AHUT-Ele-AstrBot/1.0"}
            )
        return self._session

    async def close(self):
        """关闭HTTP会话"""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    def has_session(self) -> bool:
        """检查是否有有效会话（未过期）"""
        if not self._cookie:
            return False
        # 检查会话是否已过期（30分钟）
        if self._login_time is None:
            return False
        elapsed = datetime.now() - self._login_time
        return elapsed < self.SESSION_TIMEOUT

    def clear_session(self):
        """清除会话cookie"""
        self._cookie = ""
        self._login_time = None

    def set_credentials(self, username: str, password: str):
        """存储凭证用于自动登录"""
        self._credentials = (username, password)

    def clear_credentials(self):
        """清除已存储的凭证"""
        self._credentials = None
        self._cookie = ""
        self._login_time = None

    async def login(self, username: str, password: str) -> Tuple[bool, str]:
        """
        登录缴费系统。

        返回: (是否成功, 消息)
        """
        try:
            session = await self._get_session()

            # 使用RSA加密密码
            encrypted_pwd = encrypt_password_with_rsa(password)

            form_data = {
                "username": username,
                "pwd": encrypted_pwd,
            }

            # 发送登录请求（不跟随重定向）
            resp = await session.post(
                self.LOGIN_SERVICE_URL,
                data=form_data,
                headers={"Referer": self.LOGIN_URL},
                allow_redirects=False,
            )

            # 从响应中提取cookie
            # aiohttp的cookies是SimpleCookie，使用items()迭代
            cookie_str = ""
            for name, morsel in resp.cookies.items():
                cookie_str += f"{name}={morsel.value}; "

            self._cookie = cookie_str.strip()
            if self._cookie:
                session.headers["Cookie"] = self._cookie

            # 调试：记录获取的内容
            logger.info(f"登录响应: 状态={resp.status}, cookie={self._cookie[:80] if self._cookie else 'EMPTY'}")

            status = resp.status
            body = await resp.text()

            # 检查登录结果
            if status == 302:
                # 重定向表示登录成功
                self._login_time = datetime.now()
                return True, "登录成功"

            if status == 200:
                # 首先检查错误消息
                if "用户名或密码错误" in body or "登录失败" in body or "error" in body.lower():
                    self._cookie = ""
                    self._login_time = None
                    return False, "用户名或密码错误"

                # 200 + cookie = 成功
                if self._cookie:
                    self._login_time = datetime.now()
                    return True, "登录成功"

            return False, f"登录失败 (状态码: {status})"

        except aiohttp.ClientError as e:
            logger.error(f"登录网络错误: {e}")
            return False, f"网络错误: {e}"
        except Exception as e:
            logger.error(f"登录未知错误: {e}", exc_info=True)
            return False, f"未知错误: {e}"

    async def ensure_login(self) -> Tuple[bool, str]:
        """
        确保有有效会话，如需要则自动登录。

        返回: (是否成功, 消息)
        """
        # 检查会话是否仍然有效（30分钟内）
        if self.has_session():
            elapsed = datetime.now() - self._login_time
            remaining = self.SESSION_TIMEOUT - elapsed
            logger.debug(f"会话有效，剩余时间: {int(remaining.total_seconds())}秒")
            return True, "已登录"

        # 会话已过期或未登录，需要重新登录
        if not self._credentials:
            return False, "请先配置登录信息"

        logger.info("会话已过期（超过30分钟），需要重新登录")
        username, password = self._credentials
        success, message = await self.login(username, password)

        if success:
            logger.info(f"重新登录成功于 {self._login_time}")
        else:
            logger.warning(f"重新登录失败: {message}")

        return success, message

    async def get_electricity(
        self,
        campus: str,
        building_name: str,
        building_id: str,
        room_id: str,
        etype: str = "L",
    ) -> Optional[IMSResponse]:
        """
        获取指定房间的电费数据。

        参数:
            campus: 校区名称
            building_name: 楼栋名称
            building_id: 楼栋ID
            room_id: 房间号
            etype: 电费类型 - 'L'表示房间电费，'K'表示空调电费

        返回: IMSResponse 或 None（如果失败）
        """
        # 确保已登录
        success, message = await self.ensure_login()
        if not success:
            logger.warning(f"需要登录: {message}")
            return None

        last_error = None
        for attempt in range(1, self.MAX_RETRIES + 1):
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
                    self.IMS_SERVICE_URL,
                    data=form_data,
                    headers={"Referer": self.IMS_URL},
                )

                if resp.status != 200:
                    logger.error(f"IMS请求失败: 状态 {resp.status}")
                    return None

                data = await resp.json()
                return IMSResponse.from_dict(data)

            except asyncio.TimeoutError:
                last_error = "超时"
                logger.warning(f"IMS请求超时（尝试 {attempt}/{self.MAX_RETRIES}）")
                if attempt < self.MAX_RETRIES:
                    # 重试前等待（1秒、2秒间隔）
                    await asyncio.sleep(attempt)
                continue
            except aiohttp.ClientError as e:
                last_error = f"网络: {e}"
                logger.warning(f"IMS网络错误（尝试 {attempt}/{self.MAX_RETRIES}）: {e}")
                if attempt < self.MAX_RETRIES:
                    await asyncio.sleep(attempt)
                continue
            except Exception as e:
                logger.error(f"IMS未知错误: {e}", exc_info=True)
                return None

        # 所有重试已用尽
        logger.error(f"IMS请求在 {self.MAX_RETRIES} 次尝试后失败，最后错误: {last_error}")
        return None

    async def get_full_electricity(
        self,
        campus: str,
        building_name: str,
        building_id: str,
        room_id: str,
        dorm_name: str = "",
    ) -> ElectricityResult:
        """
        获取房间电费和空调电费数据。

        参数:
            campus: 校区名称
            building_name: 楼栋名称
            building_id: 楼栋ID
            room_id: 房间号
            dorm_name: 宿舍显示名称

        返回: 包含房间和空调电费数据的 ElectricityResult
        """
        result = ElectricityResult(dorm_name=dorm_name or f"{building_name} {room_id}")

        try:
            # 并行查询房间（L）和空调（K）电费
            room_task = self.get_electricity(campus, building_name, building_id, room_id, "L")
            ac_task = self.get_electricity(campus, building_name, building_id, room_id, "K")

            room_resp, ac_resp = await asyncio.gather(room_task, ac_task)

            if room_resp and room_resp.code == 0:
                result.room_remain = room_resp.remain_amp

            if ac_resp and ac_resp.code == 0:
                result.ac_remain = ac_resp.remain_amp

            if not room_resp and not ac_resp:
                result.error = "查询失败"

        except Exception as e:
            logger.error(f"完整电费查询错误: {e}")
            result.error = str(e)

        return result

    async def query_multiple(self, dorm_configs: list) -> list:
        """
        查询多个宿舍的电费。

        参数:
            dorm_configs: (发送者ID, DormConfig) 元组列表

        返回: (发送者ID, DormConfig, ElectricityResult) 列表
        """
        results = []
        for sender_id, dorm in dorm_configs:
            try:
                result = await self.get_full_electricity(
                    campus=dorm.campus,
                    building_name=dorm.building_name,
                    building_id=dorm.building_id,
                    room_id=dorm.room_id,
                    dorm_name=dorm.get_display_name(),
                )
                results.append((sender_id, dorm, result))
            except Exception as e:
                logger.error(f"查询错误 {dorm.room_id}: {e}")
                result = ElectricityResult(dorm_name=dorm.get_display_name(), error=str(e))
                results.append((sender_id, dorm, result))

        return results