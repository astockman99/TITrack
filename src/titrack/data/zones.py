"""Zone name mappings from internal paths to English names."""

# Map internal zone path patterns to English display names
# Add new mappings as you encounter zones
ZONE_NAMES = {
    # Hideouts / Hubs
    "XZ_YuJinZhiXiBiNanSuo": "Hideout - Ember's Rest",
    "DD_ShengTingZhuangYuan": "Hideout - Sacred Court Manor",

    # Sandlord zones (trackable - players earn FE from airship/glider rewards)
    "YunDuanLvZhou": "Cloud Oasis (Sandlord)",

    # Voidlands (entries with number suffixes must come before generic ones)
    # KD_YuanSuKuangDong000 differentiated by LevelId suffix
    "DD_ShengTingZhuangYuan000": "Voidlands - Mundane Palace",

    # Blistering Lava Sea
    "KD_YuanSuKuangDong": "Blistering Lava Sea - Elemental Mine",
    "DD_ChaoBaiZhiLu": "Blistering Lava Sea - Path of Sacrifice",
    "SD_ShouGuSiDi": "Blistering Lava Sea - Dragonrest Cavern",
    "JH_ZuiRenMiDian": "Blistering Lava Sea - Where Lies Confession",
    "YJ_LuoRiQiongDi": "Blistering Lava Sea - Sunset Dome Bottom",
    "SQ_BianChuiZhiDi": "Blistering Lava Sea - Savage Grasslands",
    "JH_MengZhongShengDi": "Blistering Lava Sea - Shimmering Hall",
    "KD_AiRenDiSanCeng": "Blistering Lava Sea - Heart of the Mountains",
    "JH_ShengDeLanXiuDaoYuan": "Blistering Lava Sea - Confession Chapel",
    "SD_ShouGuLinDi": "Blistering Lava Sea - Twisted Valley",
    "DD_DiDuTingYuan200": "Blistering Lava Sea - Court of Darkness",
    "KD_RongHuoHeXin": "Blistering Lava Sea - Smelting Plant",
    "YanYuZhiGu": "Blistering Lava Sea - Hellfire Chasm",
    # Glacial Abyss
    "DD_TingYuanMiGong": "Glacial Abyss - High Court Maze",
    "YJ_XieDuYuZuo": "Glacial Abyss - Defiled Side Chamber",
    "DD_ZaWuJieQu": "Glacial Abyss - Deserted District",
    "SQ_MingShaJuLuo": "Glacial Abyss - Singing Sand",
    "SD_GeBuLinShanZhai": "Glacial Abyss - Shadow Outpost",
    # GeBuLinCunLuo - differentiated by LevelId suffix in AMBIGUOUS_ZONES
    # Fallback shows generic name when suffix is unknown
    "GeBuLinCunLuo": "Demiman Village",
    "KD_AiRenKuangDong": "Glacial Abyss - Abandoned Mines",
    "YL_YinYiZhiDi": "Glacial Abyss - Rainforest of Divine Legacy",
    "KD_WeiJiKuangDong": "Glacial Abyss - Swirling Mines",
    # YL_BeiFengLinDi (Grimwind Woods) - differentiated by LevelId suffix
    # Fallback for when LevelId is not available
    "YL_BeiFengLinDi": "Grimwind Woods",
    "SD_ZhongXiGaoQiang": "Glacial Abyss - Wall of the Last Breath",
    "SD_GeBuLinYingDi": "Glacial Abyss - Blustery Canyon",
    "YongShuangBingPo": "Glacial Abyss - Throne of Winter",

    # Boss zones
    "YJ_XiuShiShenYuan": "Rusted Abyss",

    # Ruins of Aeterna (Season 10 content)
    "CC1_SiWangMiCheng": "Ruins of Aeterna: Boundless",
    "XueYuRongLu": "The Frozen Canvas",

    # Vorax
    "DiXiaZhenSuo": "Vorax - Shelly's Operating Theater",

    # Steel Forge
    "JH_JueXingMiDian": "Steel Forge - Shrine of Despair",
    "JH_TongKuMiDian": "Steel Forge - Shrine of Punishment",
    "SD_YuanGuTongDao": "Steel Forge - Beast Plains",
    "SQ_JingJiHuiTu": "Steel Forge - Thorny Filth",
    "KD_AiRenDiErCeng": "Steel Forge - Weeping Mines",
    "SD_DuiLongJuQiang": "Steel Forge - Cloud Walls",
    "DD_YinYanJieXiang": "Steel Forge - Alleys of the Lost",
    "YJ_TaiYangWangTing": "Steel Forge - City of Eternal Fire",
    "DD_JueWangZhiQiang": "Steel Forge - Wall of the Pure",
    "YJ_RiXiShenMiao": "Steel Forge - Sun Temple",
    "YJ_YingLingShenDian": "Steel Forge - Corona Shrine",
    "SQ_ZheFengBiZhang": "Steel Forge - Windbreath Cliff",
    "ChiGuiWuShi": "Steel Forge - Imaginary Monument",

    # Thunder Wastes
    "DD_TanXiZhiQiang": "Thunder Wastes - Wall of Sorrows",
    "DD_XinTuJieXiang": "Thunder Wastes - Alleys of Pilgrims",
    "SQ_EWuHuangCun": "Thunder Wastes - Desolate Village",
    "YJ_ShuXiDaTing": "Thunder Wastes - Hall in the Mirror",
    "SQ_NvShenQunBai": "Thunder Wastes - Defiled Oasis",
    "SQ_XiongShiZhiXin": "Thunder Wastes - King's Hub",
    "KD_CangBaoDongKu": "Thunder Wastes - Thirsty Mines",
    "SD_ShengHuoLing": "Thunder Wastes - Rainmist Jungle",
    "JH_JiaoTangDaTing": "Thunder Wastes - Prayer Sanctuary",
    "DD_DiDuTingYuan000": "Thunder Wastes - Sacred Courtyard",
    "YJ_LiuJinJieQu": "Thunder Wastes - Gallery of Moon",
    "LeiYingJiDian": "Thunder Wastes - Summit of Thunder",

    # Rift of Dimensions
    "LieXiKongJing": "Rift of Dimensions",

    # Secret Realms
    "HD_YingGuangDianTang": "Secret Realm - Invaluable Time",
    "HD_EMengZhiXia": "Secret Realm - Sea of Rites",
    "BZ_NaGouZhiXi": "Secret Realm - Unholy Pedestal",
    "BZ_JiangShengChao": "Secret Realm - Abyssal Vault",

    # Supreme Showdown (floor prefix varies by map reuse, e.g. JH_, YJ_)
    "MuBiaoTiaoZhan": "Supreme Showdown",

    # Arcana (league mechanic sub-zone)
    "SuMingTaLuo": "Fateful Contest",

    # Mistville (legacy league mechanic)
    "WuDuYiZhi": "Mistville",

    # Void Sea
    "XuHaiZhongGang": "Void Sea Terminal",

    # Deep Space (exclusive zones not in the regular 5 regions)
    "SD_GuangMaoLieChang": "Deep Space - Boundless Hunting Ground",
    "KD_DiXinKuangChang": "Deep Space - Core Mine",
    "SQ_ShaZhongMuYuan": "Deep Space - Desert Pasture",
    "SD_DaHuangZhiYe": "Deep Space - Barren Wilderness",
    "YL_WanQingHuangLin": "Deep Space - Vast Wasteland",

    # Voidlands (remaining zones without conflicts)
    "DD_QunLangJieXiang": "Voidlands - Grim Alleys",
    "YL_MaNeiLaYuLin": "Voidlands - Filthy Forest",
    "YL_MiWuYuLin": "Voidlands - Dreamless Thicket",
    "JH_ShenHeJuSuo": "Voidlands - Luminescent Throne",
    "JH_YiWangMiDian": "Voidlands - Shrine of Agony",
    "YL_KuangReYuLin": "Voidlands - Shimmering Swamp",
    "YL_XiDiChongGu": "Voidlands - Jungle of the Brood",
    "YJ_YongZhouHuiLang": "Voidlands - Gallery of Stars",
    "JH_YinNiShengTang": "Voidlands - Yesterday Chamber",
    "DiaoLingWangYu": "Voidlands - Dreamless Abyss",
}

# Ambiguous zones that appear in multiple regions with same path
# These are resolved using the LevelId suffix (last 2 digits)
# LevelId format: XXYY where XX = Timemark tier, YY = zone identifier
AMBIGUOUS_ZONES = {
    # Zone path pattern -> {suffix: "Region - Zone Name"}
    "YL_BeiFengLinDi": {  # Grimwind Woods
        6: "Glacial Abyss - Grimwind Woods",
        54: "Voidlands - Grimwind Woods",
    },
    "KD_YuanSuKuangDong000": {  # Elemental Mine (with 000 suffix in path)
        12: "Blistering Lava Sea - Elemental Mine",
        55: "Voidlands - Elemental Mine",
    },
    "GeBuLinCunLuo": {  # Demiman Village / Grove of Calamity
        2: "Glacial Abyss - Demiman Village",
        # TODO: Find suffix for Thunder Wastes - Grove of Calamity (if different path)
    },
}

# Exact LevelId mappings for special zones (bosses, secret realms, etc.)
# These don't follow the XXYY pattern
LEVEL_ID_ZONES = {
    # Boss zones (Timemark bosses)
    3016: "Blistering Lava Sea - Hellfire Chasm",
    3006: "Glacial Abyss - Throne of Winter",
    3036: "Thunder Wastes - Summit of Thunder",
    3026: "Steel Forge - Imaginary Monument",
    3046: "Voidlands - Dreamless Abyss",
    # Secret Realm
    234020: "Secret Realm - Sea of Rites",
    # Trial of Divinity
    212023: "Trial of Divinity",
    # Path of the Brave (rooms use 999901-999905, one per difficulty level)
    999901: "Path of the Brave",
    999902: "Path of the Brave",
    999903: "Path of the Brave",
    999904: "Path of the Brave",
    999905: "Path of the Brave",
    # Sandlord zones
    9999999: "Cloud Oasis (Sandlord)",
    9999997: "Quicksand Treasure Stash (Sandlord)",
}

# LevelIds for sandlord zones (Cloud Oasis + sub-zones like Pillage Raid).
# Transitions between these zones do NOT create new runs.
# Push2 events in these zones create deltas (oasis rewards/costs).
SANDLORD_LEVEL_IDS = frozenset({9999999, 9999997})


def is_sandlord_zone(level_id: int | None) -> bool:
    """Check if a level_id corresponds to a sandlord zone."""
    return level_id is not None and level_id in SANDLORD_LEVEL_IDS


def get_zone_display_name(zone_path: str, level_id: int | None = None) -> str:
    """
    Get the English display name for a zone path.

    Args:
        zone_path: Internal zone path like /Game/Art/Maps/01SD/XZ_YuJinZhiXiBiNanSuo200/...
        level_id: Optional LevelId for differentiating zones with same path

    Returns:
        English display name if known, otherwise a cleaned-up version of the path
    """
    # First, check exact level_id mapping (for boss zones, secret realms, etc.)
    if level_id is not None and level_id in LEVEL_ID_ZONES:
        return LEVEL_ID_ZONES[level_id]

    # Check if this is an ambiguous zone that needs suffix-based resolution
    if level_id is not None:
        for zone_pattern, suffix_map in AMBIGUOUS_ZONES.items():
            if zone_pattern in zone_path:
                suffix = level_id % 100
                if suffix in suffix_map:
                    return suffix_map[suffix]
                # Suffix not found - fall through to ZONE_NAMES fallback

    # Check each known mapping
    for internal_name, english_name in ZONE_NAMES.items():
        if internal_name in zone_path:
            return english_name

    # Fallback: extract the zone code from the path
    # /Game/Art/Maps/01SD/XZ_YuJinZhiXiBiNanSuo200/... -> XZ_YuJinZhiXiBiNanSuo200
    parts = zone_path.split("/")
    for part in reversed(parts):
        if part and not part.startswith("Game") and not part.startswith("Art"):
            # Remove trailing numbers
            import re
            cleaned = re.sub(r'\d+$', '', part)
            return cleaned if cleaned else part

    return zone_path


# Chinese translations of zone display names (the English values from
# ZONE_NAMES / AMBIGUOUS_ZONES / LEVEL_ID_ZONES). Keyed by the *English*
# display string so the web client can translate without re-implementing
# zone-path resolution. Missing keys fall back to the English string.
ZONE_NAMES_CN: dict[str, str] = {
    # Hideouts
    "Hideout - Ember's Rest": "驻地 - 余烬避难所",
    "Hideout - Sacred Court Manor": "驻地 - 圣庭庄园",

    # Sandlord
    "Cloud Oasis (Sandlord)": "云端绿洲（沙王）",
    "Quicksand Treasure Stash (Sandlord)": "流沙中的琳琅宝库（沙王）",

    # Blistering Lava Sea
    "Blistering Lava Sea - Elemental Mine": "沸涌炎海 - 元素矿洞",
    "Blistering Lava Sea - Path of Sacrifice": "沸涌炎海 - 献身之路",
    "Blistering Lava Sea - Dragonrest Cavern": "沸涌炎海 - 龙眠峡谷",
    "Blistering Lava Sea - Where Lies Confession": "沸涌炎海 - 告罪之间",
    "Blistering Lava Sea - Sunset Dome Bottom": "沸涌炎海 - 落日穹底",
    "Blistering Lava Sea - Savage Grasslands": "沸涌炎海 - 蛮荒原野",
    "Blistering Lava Sea - Shimmering Hall": "沸涌炎海 - 微光礼堂",
    "Blistering Lava Sea - Heart of the Mountains": "沸涌炎海 - 群山之心",
    "Blistering Lava Sea - Confession Chapel": "沸涌炎海 - 忽罪学院",
    "Blistering Lava Sea - Twisted Valley": "沸涌炎海 - 曲折谷地",
    "Blistering Lava Sea - Court of Darkness": "沸涌炎海 - 暗夜王庭",
    "Blistering Lava Sea - Smelting Plant": "沸涌炎海 - 熔铁工厂",
    "Blistering Lava Sea - Hellfire Chasm": "沸涌炎海 - 焰狱之谷",

    # Glacial Abyss
    "Glacial Abyss - High Court Maze": "冰封寒渊 - 圣庭迷宫",
    "Glacial Abyss - Defiled Side Chamber": "冰封寒渊 - 渎神偏殿",
    "Glacial Abyss - Deserted District": "冰封寒渊 - 杂芜街区",
    "Glacial Abyss - Singing Sand": "冰封寒渊 - 鸣沙村落",
    "Glacial Abyss - Shadow Outpost": "冰封寒渊 - 暗影前哨",
    "Demiman Village": "亚人村落",
    "Glacial Abyss - Demiman Village": "冰封寒渊 - 亚人村落",
    "Glacial Abyss - Abandoned Mines": "冰封寒渊 - 荒弃矿场",
    "Glacial Abyss - Rainforest of Divine Legacy": "冰封寒渊 - 神遗雨林",
    "Glacial Abyss - Swirling Mines": "冰封寒渊 - 回旋矿场",
    "Grimwind Woods": "悲风林地",
    "Glacial Abyss - Grimwind Woods": "冰封寒渊 - 悲风林地",
    "Glacial Abyss - Wall of the Last Breath": "冰封寒渊 - 终息高墙",
    "Glacial Abyss - Blustery Canyon": "冰封寒渊 - 风鸣峡谷",
    "Glacial Abyss - Throne of Winter": "冰封寒渊 - 永霜冰魄",

    # Boss zones
    "Rusted Abyss": "锈蚀深渊",

    # Ruins of Aeterna
    "Ruins of Aeterna: Boundless": "永恒废墟：无尽",
    "The Frozen Canvas": "雪域熔炉",

    # Vorax
    "Vorax - Shelly's Operating Theater": "灭世之喙 - 谢莉的手术室",

    # Steel Forge
    "Steel Forge - Shrine of Despair": "钢铁炼境 - 绝望秘殿",
    "Steel Forge - Shrine of Punishment": "钢铁炼境 - 苦罚秘殿",
    "Steel Forge - Beast Plains": "钢铁炼境 - 聚兽平原",
    "Steel Forge - Thorny Filth": "钢铁炼境 - 荆棘秽土",
    "Steel Forge - Weeping Mines": "钢铁炼境 - 悲鸣矿区",
    "Steel Forge - Cloud Walls": "钢铁炼境 - 云间高墙",
    "Steel Forge - Alleys of the Lost": "钢铁炼境 - 遗落街巷",
    "Steel Forge - City of Eternal Fire": "钢铁炼境 - 长明宫城",
    "Steel Forge - Wall of the Pure": "钢铁炼境 - 无垢之墙",
    "Steel Forge - Sun Temple": "钢铁炼境 - 日栖神庙",
    "Steel Forge - Corona Shrine": "钢铁炼境 - 日冕神殿",
    "Steel Forge - Windbreath Cliff": "钢铁炼境 - 风息峦壁",
    "Steel Forge - Imaginary Monument": "钢铁炼境 - 赤魂武士",

    # Thunder Wastes
    "Thunder Wastes - Wall of Sorrows": "雷鸣废土 - 悲歌之墙",
    "Thunder Wastes - Alleys of Pilgrims": "雷鸣废土 - 朝圣街巷",
    "Thunder Wastes - Desolate Village": "雷鸣废土 - 恶武荒村",
    "Thunder Wastes - Hall in the Mirror": "雷鸣废土 - 镜中礼堂",
    "Thunder Wastes - Defiled Oasis": "雷鸣废土 - 不洁绿洲",
    "Thunder Wastes - King's Hub": "雷鸣废土 - 王者枢纽",
    "Thunder Wastes - Thirsty Mines": "雷鸣废土 - 干涃矿场",
    "Thunder Wastes - Rainmist Jungle": "雷鸣废土 - 雾雨密林",
    "Thunder Wastes - Prayer Sanctuary": "雷鸣废土 - 祷告圣堂",
    "Thunder Wastes - Sacred Courtyard": "雷鸣废土 - 圣教庭院",
    "Thunder Wastes - Gallery of Moon": "雷鸣废土 - 新月长廊",
    "Thunder Wastes - Summit of Thunder": "雷鸣废土 - 灾厄之林",

    # Rift of Dimensions
    "Rift of Dimensions": "裂隙空境",

    # Secret Realms
    "Secret Realm - Invaluable Time": "秘境 - 莹光殿堂",
    "Secret Realm - Sea of Rites": "秘境 - 噩梦之匣",
    "Secret Realm - Unholy Pedestal": "秘境 - 污秽王座",
    "Secret Realm - Abyssal Vault": "秘境 - 降神巢",

    # Misc
    "Supreme Showdown": "巅峰对决",
    "Fateful Contest": "宿命对局",
    "Mistville": "雾都遗址",
    "Void Sea Terminal": "虚空终港",

    # Deep Space
    "Deep Space - Boundless Hunting Ground": "深空 - 广袤猎场",
    "Deep Space - Core Mine": "深空 - 地心矿场",
    "Deep Space - Desert Pasture": "深空 - 沙中牧原",
    "Deep Space - Barren Wilderness": "深空 - 大荒之野",
    "Deep Space - Vast Wasteland": "深空 - 万顷荒林",

    # Voidlands
    "Voidlands - Mundane Palace": "幽夜暗域 - 常世宫闱",
    "Voidlands - Grimwind Woods": "幽夜暗域 - 悲风林地",
    "Voidlands - Elemental Mine": "幽夜暗域 - 元素矿洞",
    "Voidlands - Grim Alleys": "幽夜暗域 - 幽暗街巷",
    "Voidlands - Filthy Forest": "幽夜暗域 - 污浊丛林",
    "Voidlands - Dreamless Thicket": "幽夜暗域 - 迷雾雨林",
    "Voidlands - Luminescent Throne": "幽夜暗域 - 流光神座",
    "Voidlands - Shrine of Agony": "幽夜暗域 - 苦痛秘殿",
    "Voidlands - Shimmering Swamp": "幽夜暗域 - 微光沼泽",
    "Voidlands - Jungle of the Brood": "幽夜暗域 - 母巢密林",
    "Voidlands - Gallery of Stars": "幽夜暗域 - 群星长廊",
    "Voidlands - Yesterday Chamber": "幽夜暗域 - 昔日之所",
    "Voidlands - Dreamless Abyss": "幽夜暗域 - 凋零妄域",

    # Trial of Divinity / Path of the Brave
    "Trial of Divinity": "神威试炼",
    "Path of the Brave": "勇者之路",

    # Suffixes used at runtime
    "(Nightmare)": "（梦魇）",
}


def get_zone_display_name_cn(english_name: str) -> str:
    """
    Return the Chinese translation of an English zone display name.

    Falls back to the English string if no translation exists. Also handles
    the runtime-appended " (Nightmare)" suffix.
    """
    if english_name.endswith(" (Nightmare)"):
        base = english_name[: -len(" (Nightmare)")]
        return f"{ZONE_NAMES_CN.get(base, base)}（梦魇）"
    return ZONE_NAMES_CN.get(english_name, english_name)
