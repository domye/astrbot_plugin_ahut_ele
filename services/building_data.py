"""安工大宿舍楼栋数据

参考: ahut-tool/frontend/src/components/DormSetting.vue
"""

from dataclasses import dataclass
from typing import List, Dict


@dataclass
class Building:
    """楼栋数据"""
    id: str
    name: str


# 校区选项
CAMPUS_OPTIONS = {
    "NewS": "新校区",
    "OldS": "老校区",
}

# 新校区楼栋（东校区）
NEW_CAMPUS_BUILDINGS = [
    Building("01", "东校区1号学生宿舍楼"),
    Building("02", "东校区2号学生宿舍楼"),
    Building("03", "东校区3号学生宿舍楼"),
    Building("04", "东校区4号学生宿舍楼"),
    Building("05", "东校区5号学生宿舍楼"),
    Building("06", "东校区6号学生宿舍楼"),
    Building("07", "东校区7号学生宿舍楼"),
    Building("08", "东校区8号学生宿舍楼"),
    Building("09", "东校区9号学生宿舍楼"),
    Building("10", "东校区A号学生宿舍楼"),
    Building("11", "东校区B号学生宿舍楼"),
    Building("13", "东校区C号学生宿舍楼"),
    Building("14", "东校区D号学生宿舍楼"),
    Building("15", "东校区E号学生宿舍楼"),
    Building("16", "东校区F号学生宿舍楼"),
    Building("17", "东校区H1号学生宿舍楼"),
    Building("18", "东校区H2号学生宿舍楼"),
    Building("19", "东校区H3号学生宿舍楼"),
    Building("20", "东校区G1号学生宿舍楼"),
    Building("21", "东校区G2号学生宿舍楼"),
    Building("22", "东校区G3号学生宿舍楼"),
    Building("23", "东校区J1号学生宿舍楼"),
    Building("24", "东校区J2号学生宿舍楼"),
    Building("25", "东校区J3号学生宿舍楼"),
    Building("26", "东校区K1号学生宿舍楼"),
    Building("27", "东校区K2号学生宿舍楼"),
    Building("28", "东校区K3号学生宿舍楼"),
    Building("29", "东校区L1号学生宿舍楼"),
    Building("30", "东校区L2号学生宿舍楼"),
    Building("31", "东校区G4号学生宿舍楼"),
    Building("32", "东校区研5号学生宿舍楼"),
    Building("33", "东校区研6号学生宿舍楼"),
    Building("34", "东校区研7号学生宿舍楼"),
    Building("35", "东校区研8号学生宿舍楼"),
    Building("36", "东校区研1号学生宿舍楼"),
    Building("37", "东校区研2号学生宿舍楼"),
    Building("38", "东校区研3号学生宿舍楼"),
    Building("39", "东校区研4号学生宿舍楼"),
    Building("40", "东校区M栋南楼宿舍"),
    Building("41", "东校区M栋北楼宿舍"),
    Building("42", "东校区N栋南楼宿舍"),
    Building("43", "东校区N栋北楼宿舍"),
]

# 老校区楼栋（本部校区）
OLD_CAMPUS_BUILDINGS = [
    Building("01", "本部校区01栋学生宿舍"),
    Building("02", "本部校区02栋学生宿舍"),
    Building("03", "本部校区03栋学生宿舍"),
    Building("04", "本部校区04栋学生宿舍"),
    Building("05", "本部校区05A栋学生宿舍"),
    Building("06", "本部校区05B栋学生宿舍"),
    Building("07", "本部校区矿东栋学生宿舍"),
    Building("08", "本部校区矿西栋学生宿舍"),
    Building("09", "本部校区研A栋学生宿舍"),
    Building("10", "本部校区研B栋学生宿舍"),
    Building("11", "本部校区8号公寓"),
    Building("12", "本部校区7号公寓"),
]


def get_buildings(campus: str) -> List[Building]:
    """获取校区的楼栋列表"""
    if campus == "OldS":
        return OLD_CAMPUS_BUILDINGS
    return NEW_CAMPUS_BUILDINGS


def get_building_by_id(campus: str, building_id: str) -> Building:
    """根据ID获取楼栋"""
    buildings = get_buildings(campus)
    for b in buildings:
        if b.id == building_id:
            return b
    return None


def format_campus_menu() -> str:
    """格式化校区选择菜单"""
    lines = ["🏠 请选择校区：", ""]
    for i, (code, name) in enumerate(CAMPUS_OPTIONS.items(), 1):
        lines.append(f"  {i}. {name}")
    lines.append("")
    lines.append("请输入序号或校区名称，或输入'取消'退出：")
    return "\n".join(lines)


def format_building_menu(campus: str, page: int = 1, page_size: int = 20) -> str:
    """格式化楼栋选择菜单（带分页）"""
    buildings = get_buildings(campus)
    campus_name = CAMPUS_OPTIONS.get(campus, campus)

    total = len(buildings)
    total_pages = (total + page_size - 1) // page_size
    page = max(1, min(page, total_pages))

    start = (page - 1) * page_size
    end = min(start + page_size, total)
    page_buildings = buildings[start:end]

    lines = [f"🏢 {campus_name}楼栋列表（第{page}/{total_pages}页）：", ""]
    for i, b in enumerate(page_buildings, start + 1):
        lines.append(f"  {i}. {b.name}")

    lines.append("")
    nav_hints = []
    if page < total_pages:
        nav_hints.append("'n'下一页")
    if page > 1:
        nav_hints.append("'p'上一页")
    nav_hints.append("'取消'退出")

    lines.append("输入序号选择楼栋" + (f"，或 {', '.join(nav_hints)}" if nav_hints else ""))

    return "\n".join(lines)


def parse_campus_input(text: str) -> str:
    """解析校区输入，返回校区代码或空字符串"""
    text = text.strip()

    # 直接代码
    if text in CAMPUS_OPTIONS:
        return text

    # 数字输入
    try:
        num = int(text)
        if num == 1:
            return "NewS"
        elif num == 2:
            return "OldS"
    except ValueError:
        pass

    # 名称匹配
    text_lower = text.lower()
    if "新" in text or "东" in text:
        return "NewS"
    if "老" in text or "本" in text or "部" in text:
        return "OldS"

    return ""