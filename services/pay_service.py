"""Pay system service for AHUT electricity query.

Reference: ahut-tool/backend/pay/
"""

import aiohttp
import asyncio
from typing import Optional, Dict, Tuple
from astrbot.api import logger
from ..models import IMSResponse
from .rsa_utils import encrypt_password_with_rsa


class PayService:
    """Service for interacting with AHUT pay system."""

    # API URLs
    BASE_URL = "https://pay.ahut.edu.cn"
    LOGIN_URL = BASE_URL + "/Account/Login"
    LOGIN_SERVICE_URL = BASE_URL + "/Account/LoginService"
    IMS_URL = BASE_URL + "/Charge/IMS?state=WXSTATEFLAG"
    IMS_SERVICE_URL = BASE_URL + "/Charge/GetIMS_AHUTService"

    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
        self._cookie: str = ""
        self._credentials: Optional[Tuple[str, str]] = None  # (username, password)

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=10)
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                headers={"User-Agent": "AHUT-Ele-AstrBot/1.0"}
            )
        return self._session

    async def close(self):
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    def has_session(self) -> bool:
        """Check if we have a valid session."""
        return self._cookie != ""

    def clear_session(self):
        """Clear the session cookie."""
        self._cookie = ""

    def set_credentials(self, username: str, password: str):
        """Store credentials for auto-login."""
        self._credentials = (username, password)

    def clear_credentials(self):
        """Clear stored credentials."""
        self._credentials = None
        self._cookie = ""

    async def login(self, username: str, password: str) -> Tuple[bool, str]:
        """
        Login to the pay system.

        Returns: (success, message)
        """
        try:
            session = await self._get_session()

            # Encrypt password with RSA
            encrypted_pwd = encrypt_password_with_rsa(password)

            form_data = {
                "username": username,
                "pwd": encrypted_pwd,
            }

            # Send login request (don't follow redirects)
            resp = await session.post(
                self.LOGIN_SERVICE_URL,
                data=form_data,
                headers={"Referer": self.LOGIN_URL},
                allow_redirects=False,
            )

            # Extract cookies from response
            # aiohttp cookies is SimpleCookie, iterate with items()
            cookie_str = ""
            for name, morsel in resp.cookies.items():
                cookie_str += f"{name}={morsel.value}; "

            self._cookie = cookie_str.strip()
            if self._cookie:
                session.headers["Cookie"] = self._cookie

            status = resp.status
            body = await resp.text()

            # Check login result
            if status == 302:
                # Redirect means login success
                return True, "登录成功"

            if status == 200:
                # Check for error messages
                if "用户名或密码错误" in body or "登录失败" in body:
                    self._cookie = ""
                    return False, "用户名或密码错误"

                if "success" in body.lower() or "true" in body.lower():
                    return True, "登录成功"

            return False, f"登录失败 (状态码: {status})"

        except aiohttp.ClientError as e:
            logger.error(f"Login network error: {e}")
            return False, f"网络错误: {e}"
        except Exception as e:
            logger.error(f"Login unexpected error: {e}", exc_info=True)
            return False, f"未知错误: {e}"

    async def ensure_login(self) -> Tuple[bool, str]:
        """
        Ensure we have a valid session, auto-login if needed.

        Returns: (success, message)
        """
        if self.has_session():
            return True, "已登录"

        if not self._credentials:
            return False, "请先配置登录信息"

        username, password = self._credentials
        return await self.login(username, password)

    async def get_electricity(
        self,
        campus: str,
        building_name: str,
        building_id: str,
        room_id: str,
        etype: str = "宿舍电费",
    ) -> Optional[IMSResponse]:
        """
        Get electricity data for a specific room.

        Args:
            campus: Campus name (校区)
            building_name: Building name (楼栋名称)
            building_id: Building ID (楼栋ID)
            room_id: Room number (房间号)
            etype: Electricity type (default: 宿舍电费)

        Returns: IMSResponse or None if failed
        """
        # Ensure logged in
        success, message = await self.ensure_login()
        if not success:
            logger.warning(f"Login required: {message}")
            return None

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
                logger.error(f"IMS request failed: status {resp.status}")
                return None

            data = await resp.json()
            return IMSResponse.from_dict(data)

        except aiohttp.ClientError as e:
            logger.error(f"IMS network error: {e}")
            return None
        except Exception as e:
            logger.error(f"IMS unexpected error: {e}", exc_info=True)
            return None

    async def query_multiple(self, dorm_configs: list) -> list:
        """
        Query electricity for multiple dorms.

        Args:
            dorm_configs: List of (sender_id, DormConfig) tuples

        Returns: List of (sender_id, DormConfig, IMSResponse or error_str)
        """
        results = []
        for sender_id, dorm in dorm_configs:
            try:
                ims = await self.get_electricity(
                    campus=dorm.campus,
                    building_name=dorm.building_name,
                    building_id=dorm.building_id,
                    room_id=dorm.room_id,
                )
                if ims:
                    results.append((sender_id, dorm, ims))
                else:
                    results.append((sender_id, dorm, "查询失败"))
            except Exception as e:
                logger.error(f"Query error for {dorm.room_id}: {e}")
                results.append((sender_id, dorm, f"错误: {e}"))

        return results