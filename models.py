"""Data models for the electricity query plugin."""

from dataclasses import dataclass, field
from typing import Optional, Dict, List


@dataclass
class IMSResponse:
    """IMS API response structure."""
    code: int = 0
    msg: str = ""
    room_id: str = ""
    all_amp: float = 0.0  # Total electricity
    used_amp: float = 0.0  # Used electricity
    remain_amp: float = 0.0  # Remaining electricity

    @classmethod
    def from_dict(cls, data: Dict) -> "IMSResponse":
        """Parse from API response dict."""
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
    """Combined electricity result for a dorm."""
    dorm_name: str
    room_remain: float = 0.0  # 房间剩余电量
    ac_remain: float = 0.0    # 空调剩余电量
    error: str = ""

    def format_result(self) -> str:
        """Format the result for display."""
        if self.error:
            return f"❌ {self.dorm_name}: {self.error}"

        lines = [f"🏠 {self.dorm_name}"]
        lines.append(f"🔌 房间剩余: {self.room_remain:.2f} kWh")
        lines.append(f"❄️ 空调剩余: {self.ac_remain:.2f} kWh")

        # Low balance warning
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
    """User's dormitory configuration."""
    campus: str = ""  # Campus name (校区)
    building_id: str = ""  # Building ID (楼栋ID)
    building_name: str = ""  # Building name (楼栋名称)
    room_id: str = ""  # Room number (房间号)
    dorm_name: str = ""  # Full dorm name for display

    def to_dict(self) -> Dict:
        """Convert to dict for storage."""
        return {
            "campus": self.campus,
            "building_id": self.building_id,
            "building_name": self.building_name,
            "room_id": self.room_id,
            "dorm_name": self.dorm_name,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "DormConfig":
        """Parse from stored dict."""
        return cls(
            campus=data.get("campus", ""),
            building_id=data.get("building_id", ""),
            building_name=data.get("building_name", ""),
            room_id=data.get("room_id", ""),
            dorm_name=data.get("dorm_name", ""),
        )

    def get_display_name(self) -> str:
        """Get display name for the dorm."""
        if self.dorm_name:
            return self.dorm_name
        return f"{self.building_name} {self.room_id}"


@dataclass
class PayCredentials:
    """Pay system credentials (stored without password)."""
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
    """Registry of user dorm configurations."""
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
        """Set dorm config for a user."""
        self.dorms[sender_id] = dorm

    def get_dorm(self, sender_id: str) -> Optional[DormConfig]:
        """Get dorm config for a user."""
        return self.dorms.get(sender_id)

    def remove_dorm(self, sender_id: str) -> bool:
        """Remove dorm config for a user."""
        if sender_id in self.dorms:
            del self.dorms[sender_id]
            return True
        return False

    def get_all_dorms(self) -> List[tuple]:
        """Get all dorm configs as list of (sender_id, DormConfig)."""
        return list(self.dorms.items())