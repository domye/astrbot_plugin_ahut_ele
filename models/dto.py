"""
数据传输对象 (DTO)
"""
from dataclasses import dataclass
from typing import Optional, List


@dataclass
class LoginResult:
    """登录结果"""
    success: bool
    message: str
    session_valid: bool = False


@dataclass
class QueryResult:
    """查询结果"""
    dorm_name: str
    room_remain: float
    ac_remain: float
    error: Optional[str] = None
    is_low_balance: bool = False

    def format_message(self) -> str:
        """格式化消息"""
        if self.error:
            return f"❌ {self.dorm_name}: {self.error}"

        lines = [f"🏠 {self.dorm_name}"]
        lines.append(f"🔌 房间剩余: {self.room_remain:.2f} kWh")
        lines.append(f"❄️ 空调剩余: {self.ac_remain:.2f} kWh")

        if self.is_low_balance:
            lines.append("⚠️ 电量不足，请及时充值！")

        return "\n".join(lines)


@dataclass
class SetupStep:
    """设置步骤"""
    step_number: int
    prompt: str
    validator: Optional[callable] = None
    error_message: str = "输入无效，请重试"


@dataclass
class BuildingInfo:
    """楼栋信息"""
    id: str
    name: str
    campus: str


@dataclass
class CampusInfo:
    """校区信息"""
    code: str
    name: str
    buildings: List[BuildingInfo]
