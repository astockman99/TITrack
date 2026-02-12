"""Zone name mappings from internal paths to English names."""

# Map internal zone path patterns to English display names
# Add new mappings as you encounter zones
ZONE_NAMES = {
    # Hideouts / Hubs
    "XZ_YuJinZhiXiBiNanSuo": "Hideout - Ember's Rest",
    "DD_ShengTingZhuangYuan": "Hideout - Sacred Court Manor",

    # Sandlord zone (trackable - players earn FE here)
    "YunDuanLvZhou": "Cloud Oasis",

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

    # Arcana (league mechanic sub-zone)
    "SuMingTaLuo": "Fateful Contest",

    # Mistville (legacy league mechanic)
    "WuDuYiZhi": "Mistville",

    # Void Sea
    "XuHaiZhongGang": "Void Sea Terminal",

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
}


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
