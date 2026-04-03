"""
核心实体定义
"""
from dataclasses import dataclass, field
from typing import Optional, Dict, List
from datetime import datetime


@dataclass
class PayCredentials:
    """缴费系统凭证"""
    username: str
    password: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()

    def to_dict(self) -> Dict:
        return {
            "username": self.username,
            "password": self.password,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "PayCredentials":
        created = None
        updated = None
        if data.get("created_at"):
            try:
                created = datetime.fromisoformat(data["created_at"])
            except:
                pass
        if data.get("updated_at"):
            try:
                updated = datetime.fromisoformat(data["updated_at"])
            except:
                pass
        return cls(
            username=data.get("username", ""),
            password=data.get("password", ""),
            created_at=created,
            updated_at=updated,
        )


@dataclass
class DormConfig:
    """宿舍配置"""
    campus: str
    building_id: str
    building_name: str
    room_id: str
    dorm_name: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self):
        if self.dorm_name is None:
            campus_name = {"NewS": "新校区", "OldS": "老校区"}.get(self.campus, self.campus)
            self.dorm_name = f"{campus_name} {self.building_name} {self.room_id}"
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()

    def to_dict(self) -> Dict:
        return {
            "campus": self.campus,
            "building_id": self.building_id,
            "building_name": self.building_name,
            "room_id": self.room_id,
            "dorm_name": self.dorm_name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "DormConfig":
        created = None
        updated = None
        if data.get("created_at"):
            try:
                created = datetime.fromisoformat(data["created_at"])
            except:
                pass
        if data.get("updated_at"):
            try:
                updated = datetime.fromisoformat(data["updated_at"])
            except:
                pass
        return cls(
            campus=data.get("campus", ""),
            building_id=data.get("building_id", ""),
            building_name=data.get("building_name", ""),
            room_id=data.get("room_id", ""),
            dorm_name=data.get("dorm_name"),
            created_at=created,
            updated_at=updated,
        )

    def get_display_name(self) -> str:
        """获取显示名称"""
        return self.dorm_name or f"{self.building_name} {self.room_id}"


@dataclass
class ElectricityData:
    """电费数据"""
    room_remain: float = 0.0
    ac_remain: float = 0.0
    room_total: float = 0.0
    room_used: float = 0.0
    ac_total: float = 0.0
    ac_used: float = 0.0
    error: Optional[str] = None

    @property
    def has_error(self) -> bool:
        return self.error is not None

    @property
    def is_low_balance(self) -> bool:
        return self.room_remain < 10 or self.ac_remain < 10


@dataclass
class ScheduleTask:
    """定时任务"""
    group_umo: str
    group_name: str
    times: List[str] = field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()

    def to_dict(self) -> Dict:
        return {
            "group_umo": self.group_umo,
            "group_name": self.group_name,
            "times": self.times,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "ScheduleTask":
        created = None
        updated = None
        if data.get("created_at"):
            try:
                created = datetime.fromisoformat(data["created_at"])
            except:
                pass
        if data.get("updated_at"):
            try:
                updated = datetime.fromisoformat(data["updated_at"])
            except:
                pass
        return cls(
            group_umo=data.get("group_umo", ""),
            group_name=data.get("group_name", ""),
            times=data.get("times", []),
            created_at=created,
            updated_at=updated,
        )


@dataclass
class SessionInfo:
    """会话信息"""
    cookie: str
    login_time: datetime

    @property
    def is_expired(self, timeout_minutes: int = 30) -> bool:
        from datetime import datetime
        elapsed = datetime.now() - self.login_time
        return elapsed.total_seconds() > timeout_minutes * 60


@dataclass
class UserContext:
    """用户上下文"""
    user_id: str
    is_admin: bool = False
    group_umo: Optional[str] = None

    def require_admin(self):
        """要求管理员权限"""
        if not self.is_admin:
            from ..core.exceptions import AuthException
            raise AuthException("此操作需要管理员权限")
