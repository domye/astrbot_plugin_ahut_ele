"""电费查询插件的数据模型"""

from dataclasses import dataclass, field
from typing import Optional, Dict, List


@dataclass
class IMSResponse:
    """IMS API 响应结构"""
    code: int = 0
    msg: str = ""
    room_id: str = ""
    all_amp: float = 0.0  # 总电量
    used_amp: float = 0.0  # 已用电量
    remain_amp: float = 0.0  # 剩余电量

    @classmethod
    def from_dict(cls, data: Dict) -> "IMSResponse":
        """从API响应字典解析"""
        return cls(
            code=data.get("Code", 0),
            msg=data.get("Msg", ""),
            room_id=data.get("Data", {}).get("room_id", ""),
            all_amp=data.get("Data", {}).get("AllAmp", 0.0),
            used_amp=data.get("Data", {}).get("UsedAmp", 0.0),
            remain_amp=data.get("Data", {}).get("RemainAmp", 0.0),
        )


@dataclass
class ElectricityResult:
    """宿舍的合并电费结果"""
    dorm_name: str
    room_remain: float = 0.0  # 房间剩余电量
    ac_remain: float = 0.0    # 空调剩余电量
    error: str = ""

    def format_result(self) -> str:
        """格式化结果显示"""
        if self.error:
            return f"❌ {self.dorm_name}: {self.error}"

        lines = [f"🏠 {self.dorm_name}"]
        lines.append(f"🔌 房间剩余: {self.room_remain:.2f} kWh")
        lines.append(f"❄️ 空调剩余: {self.ac_remain:.2f} kWh")

        # 低余额警告
        warnings = []
        if self.room_remain < 10:
            warnings.append("房间电量不足!")
        if self.ac_remain < 10:
            warnings.append("空调电量不足!")

        if warnings:
            lines.append("⚠️ " + " ".join(warnings))

        return "\n".join(lines)


@dataclass
class DormConfig:
    """用户宿舍配置"""
    campus: str = ""  # 校区名称
    building_id: str = ""  # 楼栋ID
    building_name: str = ""  # 楼栋名称
    room_id: str = ""  # 房间号
    dorm_name: str = ""  # 完整宿舍显示名称

    def to_dict(self) -> Dict:
        """转换为字典用于存储"""
        return {
            "campus": self.campus,
            "building_id": self.building_id,
            "building_name": self.building_name,
            "room_id": self.room_id,
            "dorm_name": self.dorm_name,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "DormConfig":
        """从存储的字典解析"""
        return cls(
            campus=data.get("campus", ""),
            building_id=data.get("building_id", ""),
            building_name=data.get("building_name", ""),
            room_id=data.get("room_id", ""),
            dorm_name=data.get("dorm_name", ""),
        )

    def get_display_name(self) -> str:
        """获取宿舍显示名称"""
        if self.dorm_name:
            return self.dorm_name
        return f"{self.building_name} {self.room_id}"


@dataclass
class PayCredentials:
    """缴费系统凭证（不存储密码）"""
    user: str = ""
    has_password: bool = False

    def to_dict(self) -> Dict:
        return {
            "user": self.user,
            "has_password": self.has_password,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "PayCredentials":
        return cls(
            user=data.get("user", ""),
            has_password=data.get("has_password", False),
        )


@dataclass
class UserDormRegistry:
    """用户宿舍配置注册表"""
    dorms: Dict[str, DormConfig] = field(default_factory=dict)  # sender_id -> DormConfig

    def to_dict(self) -> Dict:
        return {
            "dorms": {
                sender_id: dorm.to_dict()
                for sender_id, dorm in self.dorms.items()
            }
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "UserDormRegistry":
        dorms_data = data.get("dorms", {})
        return cls(
            dorms={
                sender_id: DormConfig.from_dict(dorm_data)
                for sender_id, dorm_data in dorms_data.items()
            }
        )

    def set_dorm(self, sender_id: str, dorm: DormConfig) -> None:
        """设置用户的宿舍配置"""
        self.dorms[sender_id] = dorm

    def get_dorm(self, sender_id: str) -> Optional[DormConfig]:
        """获取用户的宿舍配置"""
        return self.dorms.get(sender_id)

    def remove_dorm(self, sender_id: str) -> bool:
        """移除用户的宿舍配置"""
        if sender_id in self.dorms:
            del self.dorms[sender_id]
            return True
        return False

    def get_all_dorms(self) -> List[tuple]:
        """获取所有宿舍配置，返回 (sender_id, DormConfig) 列表"""
        return list(self.dorms.items())