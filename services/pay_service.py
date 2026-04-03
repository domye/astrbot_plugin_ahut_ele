"""Pay system service for AHUT electricity query.

Reference: ahut-tool/backend/pay/
"""

import aiohttp
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple
from astrbot.api import logger
from ..models import IMSResponse, ElectricityResult
from .rsa_utils import encrypt_password_with_rsa


class PayService:
    """Service for interacting with AHUT pay system."""

    # API URLs
    BASE_URL = "https://pay.ahut.edu.cn"
    LOGIN_URL = BASE_URL + "/Account/Login"
    LOGIN_SERVICE_URL = BASE_URL + "/Account/LoginService"
    IMS_URL = BASE_URL + "/Charge/IMS?state=WXSTATEFLAG"
    IMS_SERVICE_URL = BASE_URL + "/Charge/GetIMS_AHUTService"

    # Session timeout: 30 minutes
    SESSION_TIMEOUT = timedelta(minutes=30)

    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
        self._cookie: str = ""
        self._credentials: Optional[Tuple[str, str]] = None  # (username, password)
        self._login_time: Optional[datetime] = None  # Last successful login time

    # Request timeout: 10 seconds per attempt
    REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=10)
    # Max retry attempts for electricity query
    MAX_RETRIES = 3

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=self.REQUEST_TIMEOUT,
                headers={"User-Agent": "AHUT-Ele-AstrBot/1.0"}
            )
        return self._session

    async def close(self):
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    def has_session(self) -> bool:
        """Check if we have a valid session (not expired)."""
        if not self._cookie:
            return False
        # Check if session has expired (30 minutes)
        if self._login_time is None:
            return False
        elapsed = datetime.now() - self._login_time
        return elapsed < self.SESSION_TIMEOUT

    def clear_session(self):
        """Clear the session cookie."""
        self._cookie = ""
        self._login_time = None

    def set_credentials(self, username: str, password: str):
        """Store credentials for auto-login."""
        self._credentials = (username, password)

    def clear_credentials(self):
        """Clear stored credentials."""
        self._credentials = None
        self._cookie = ""
        self._login_time = None

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

            # Debug: log what we got
            logger.info(f"Login response: status={resp.status}, cookie={self._cookie[:80] if self._cookie else 'EMPTY'}")

            status = resp.status
            body = await resp.text()

            # Check login result
            if status == 302:
                # Redirect means login success
                self._login_time = datetime.now()
                return True, "登录成功"

            if status == 200:
                # Check for error messages first
                if "用户名或密码错误" in body or "登录失败" in body or "error" in body.lower():
                    self._cookie = ""
                    self._login_time = None
                    return False, "用户名或密码错误"

                # 200 + cookie = success
                if self._cookie:
                    self._login_time = datetime.now()
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
        # Check if session is still valid (within 30 minutes)
        if self.has_session():
            elapsed = datetime.now() - self._login_time
            remaining = self.SESSION_TIMEOUT - elapsed
            logger.debug(f"Session valid, remaining time: {int(remaining.total_seconds())}s")
            return True, "已登录"

        # Session expired or not logged in, need to re-login
        if not self._credentials:
            return False, "请先配置登录信息"

        logger.info("Session expired (over 30 minutes), re-login required")
        username, password = self._credentials
        success, message = await self.login(username, password)

        if success:
            logger.info(f"Re-login successful at {self._login_time}")
        else:
            logger.warning(f"Re-login failed: {message}")

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
        Get electricity data for a specific room.

        Args:
            campus: Campus name (校区)
            building_name: Building name (楼栋名称)
            building_id: Building ID (楼栋ID)
            room_id: Room number (房间号)
            etype: Electricity type - 'L' for room, 'K' for AC

        Returns: IMSResponse or None if failed
        """
        # Ensure logged in
        success, message = await self.ensure_login()
        if not success:
            logger.warning(f"Login required: {message}")
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
                    logger.error(f"IMS request failed: status {resp.status}")
                    return None

                data = await resp.json()
                return IMSResponse.from_dict(data)

            except asyncio.TimeoutError:
                last_error = "timeout"
                logger.warning(f"IMS request timeout (attempt {attempt}/{self.MAX_RETRIES})")
                if attempt < self.MAX_RETRIES:
                    # Wait before retry (1s, 2s between attempts)
                    await asyncio.sleep(attempt)
                continue
            except aiohttp.ClientError as e:
                last_error = f"network: {e}"
                logger.warning(f"IMS network error (attempt {attempt}/{self.MAX_RETRIES}): {e}")
                if attempt < self.MAX_RETRIES:
                    await asyncio.sleep(attempt)
                continue
            except Exception as e:
                logger.error(f"IMS unexpected error: {e}", exc_info=True)
                return None

        # All retries exhausted
        logger.error(f"IMS request failed after {self.MAX_RETRIES} attempts, last error: {last_error}")
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
        Get both room and AC electricity data.

        Args:
            campus: Campus name (校区)
            building_name: Building name (楼栋名称)
            building_id: Building ID (楼栋ID)
            room_id: Room number (房间号)
            dorm_name: Display name for the dorm

        Returns: ElectricityResult with both room and AC data
        """
        result = ElectricityResult(dorm_name=dorm_name or f"{building_name} {room_id}")

        try:
            # Query both room (L) and AC (K) electricity in parallel
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
            logger.error(f"Full electricity query error: {e}")
            result.error = str(e)

        return result

    async def query_multiple(self, dorm_configs: list) -> list:
        """
        Query electricity for multiple dorms.

        Args:
            dorm_configs: List of (sender_id, DormConfig) tuples

        Returns: List of (sender_id, DormConfig, ElectricityResult)
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
                logger.error(f"Query error for {dorm.room_id}: {e}")
                result = ElectricityResult(dorm_name=dorm.get_display_name(), error=str(e))
                results.append((sender_id, dorm, result))

        return results