/**
 * TITrack i18n module - English / Simplified Chinese
 *
 * Public API:
 *   t(key, vars?)         -> translate a key with optional {var} substitution
 *   pickItemName(item)    -> CN name if zh-CN and available, else EN, else "Unknown {id}"
 *   pickItemUrl(item)     -> CN url if zh-CN and available, else EN
 *   tZone(englishName)    -> zone translation if available, else englishName
 *   pickSeasonName(player)-> CN season if zh-CN and available, else EN
 *   pickHeroName(player)  -> CN hero if zh-CN and available, else EN
 *   setLang(lang)         -> change language and dispatch 'langchange' event
 *   getLang()             -> 'en' | 'zh-CN'
 *   applyTranslations(root?) -> walk DOM and update [data-i18n] / [data-i18n-title] / [data-i18n-placeholder]
 *
 * Translation tables are flat key → string maps. Missing keys fall back to
 * English; missing English fall back to the key string itself.
 */
(function (global) {
    'use strict';

    const TRANSLATIONS = {
        'en': {
            // Header
            'header.app_title': 'TITrack',
            'header.awaiting_player': 'Waiting for character detection... (log in or sort your inventory)',
            'header.see_details': 'See details',
            'header.net_worth': 'Net Worth',
            'header.cumulative_value': 'Cumulative Value',
            'header.fe_per_hour': 'FE/Hour',
            'header.fe_per_map': 'FE/Map',
            'header.runs': 'Runs',
            'header.avg_run_time': 'Avg Run Time',
            'header.total_time': 'Total Time',
            'header.fe_per_hour_tooltip': 'Calculated from active run time only. Time spent in town, hideout, or between runs is not counted. This measures your farming efficiency, not total session time.',
            'header.pause_tracking': 'Pause tracking',
            'header.resume_tracking': 'Resume tracking',
            // Controls
            'controls.overlay': 'Overlay',
            'controls.overlay_tooltip': 'Open mini overlay',
            'controls.economy': 'Economy',
            'controls.economy_tooltip': 'Open titrack.ninja economy data',
            'controls.cloud_sync': 'Cloud Sync',
            'controls.cloud_sync_tooltip': 'Cloud sync status',
            'controls.settings': 'Settings',
            'controls.instructions': 'Instructions',
            'controls.reset_stats': 'Reset Stats',
            'controls.resetting': 'Resetting...',
            'controls.auto_refresh': 'Auto-refresh',
            // Charts
            'charts.cumulative_value': 'Cumulative Value',
            'charts.fe_per_hour': 'FE / Hour',
            // Active run
            'active_run.title_prefix': 'Current Run:',
            'active_run.value': 'Value:',
            'active_run.no_drops': 'No drops yet...',
            'active_run.previous_run': 'Previous Run',
            // Recent runs
            'runs.title': 'Recent Runs',
            'runs.report': 'Report',
            'runs.col_zone': 'Zone',
            'runs.col_duration': 'Duration',
            'runs.col_value': 'Value',
            'runs.loading': 'Loading...',
            'runs.none': 'No runs recorded yet',
            'runs.details': 'Details',
            'runs.gross': 'gross:',
            'runs.cost': 'cost:',
            // Inventory
            'inventory.title': 'Current Inventory',
            'inventory.hide_items': 'Hide Items',
            'inventory.hide_items_count': 'Hide Items ({count})',
            'inventory.col_item': 'Item',
            'inventory.col_qty': 'Qty',
            'inventory.col_value': 'Value',
            'inventory.col_trend': 'Trend',
            'inventory.trend_tooltip': 'Price trend (72h)',
            'inventory.filter_tooltip': 'Filter by tab',
            'inventory.tab_all': 'All',
            'inventory.tab_gear': 'Gear',
            'inventory.tab_skill': 'Skill',
            'inventory.tab_commodity': 'Commodity',
            'inventory.tab_others': 'Others',
            'inventory.empty': 'No items in inventory',
            // Footer
            'footer.last_updated': 'Last updated: {time}',
            'footer.collector': 'Collector: {state}',
            'footer.collector_running': 'Running',
            'footer.collector_stopped': 'Stopped',
            'footer.discord_tooltip': 'Join the TITrack Discord',
            'footer.kofi_tooltip': 'Help cover server costs',
            'footer.kofi': 'Help cover server costs',
            'footer.check_updates': 'Check for Updates',
            'footer.update_tooltip': 'Update available',
            'footer.exit': 'Exit App',
            'footer.checking': 'Checking...',
            'footer.update_available': 'Update Available!',
            'footer.downloading': 'Downloading...',
            'footer.install_update': 'Install Update',
            // Run details modal
            'modal.run_details': 'Run Details',
            'modal.ignore_run': '✕ Ignore Run',
            'modal.run_ignored': '✓ Run Ignored',
            // Settings modal
            'settings.title': 'Settings',
            'settings.section_value': 'Value Calculations',
            'settings.trade_tax': 'Trade Tax',
            'settings.trade_tax_desc': 'Apply 12.5% trade house tax to item values',
            'settings.map_costs': 'Map Costs',
            'settings.map_costs_desc': 'Track and subtract compass/beacon costs from run values',
            'settings.realtime': 'Real-Time Tracking',
            'settings.realtime_desc': 'Use wall-clock time for FE/Hour and Total Time instead of in-map time only',
            'settings.section_overlay': 'Overlay',
            'settings.overlay_hide_loot': 'Hide Loot Pickups',
            'settings.overlay_hide_loot_desc': 'Hide the loot section in the overlay for a more compact view (stats only)',
            'settings.overlay_micro': 'Micro Overlay',
            'settings.overlay_micro_desc': 'Show a compact overlay with only key stats instead of the full overlay',
            'settings.layout': 'Layout:',
            'settings.layout_horizontal': 'Horizontal',
            'settings.layout_vertical': 'Vertical',
            'settings.font_size': 'Font size:',
            'settings.visible_stats': 'Visible stats:',
            'settings.drag_to_reorder': '(drag to reorder)',
            'settings.section_supply': 'Low Supply Alerts',
            'settings.supply_desc': 'Get notified when map supplies drop to a threshold. Set to 0 to disable.',
            'settings.supply_beacons': 'Beacons',
            'settings.supply_compasses': 'Compasses',
            'settings.supply_resonance': 'Resonance',
            'settings.section_game_dir': 'Game Directory',
            'settings.current_path': 'Current:',
            'settings.path_placeholder': 'C:\\Torchlight Infinite or C:\\...\\Logs\\UE_game.log',
            'settings.browse': 'Browse',
            'settings.validate': 'Validate',
            'settings.path_help': 'You can enter the game folder, the Logs folder, or the full path to UE_game.log',
            'settings.save_restart': 'Save & Restart',
            'settings.saved_restart_required': 'Saved - Restart Required',
            'settings.saving': 'Saving...',
            'settings.section_language': 'Language',
            'settings.language_label': 'Language',
            'settings.language_desc': 'Display language for the dashboard and overlay',
            'settings.path_validating': 'Validating...',
            'settings.path_enter': 'Please enter a path',
            'settings.path_found': 'Found: {path}',
            'settings.path_not_found': 'Log file not found at this location',
            'settings.path_error': 'Error validating path. Please try again.',
            'settings.path_loading': 'Loading...',
            'settings.path_not_found_short': 'Not found - please configure below',
            'settings.path_unable': 'Unable to fetch current path',
            'settings.saved_msg': 'Saved! Please restart TITrack for changes to take effect.',
            'settings.error_saving': 'Error saving. Please try again.',
            // Loot report
            'report.title': 'Loot Report',
            'report.gross': 'Gross Value',
            'report.map_costs': 'Map Costs',
            'report.profit': 'Profit',
            'report.runs': 'Runs',
            'report.total_time': 'Total Time',
            'report.profit_per_hour': 'Profit/Hour',
            'report.profit_per_map': 'Profit/Map',
            'report.unique_items': 'Unique Items',
            'report.col_item': 'Item',
            'report.col_qty': 'Qty',
            'report.col_unit_price': 'Unit Price',
            'report.col_total_value': 'Total Value',
            'report.col_pct': '%',
            'report.export_csv': 'Export CSV',
            'report.close': 'Close',
            'report.loading': 'Loading report...',
            'report.failed': 'Failed to load report',
            'report.empty': 'No loot recorded yet. Complete some runs to see your report.',
            // Hide items modal
            'hide.title': 'Hide Items from Inventory',
            'hide.hint': 'Check items to hide from inventory display. Hidden items still count toward net worth.',
            'hide.hint_excluded': 'Check items to hide from inventory display. Hidden items will be excluded from net worth.',
            'hide.exclude_worth': 'Exclude from Net Worth',
            'hide.exclude_worth_desc': 'Hidden items will not count toward net worth',
            'hide.search': 'Search items...',
            'hide.col_item': 'Item',
            'hide.col_qty': 'Qty',
            'hide.col_value': 'Value',
            'hide.save': 'Save',
            'hide.cancel': 'Cancel',
            'hide.count': '{count} item{plural} hidden',
            'hide.empty': 'No items in inventory',
            // Update modal
            'update.title': 'Update Available',
            'update.release_notes': 'Release Notes',
            'update.loading': 'Loading...',
            'update.no_notes': 'No release notes available.',
            'update.download_install': 'Download & Install',
            'update.later': 'Later',
            'update.downloading_progress': 'Downloading... {mb} / {total} MB',
            'update.installing': 'Download complete. Installing...',
            'update.ready_install': 'Ready to install',
            'update.failed': 'Download failed: {error}',
            'update.retry': 'Retry',
            'update.unknown_error': 'Unknown error',
            'update.shutdown': 'TITrack has been shut down. You can close this tab.',
            // Help modal
            'help.title': 'How to Use TITrack',
            'help.s1.title': '1. Enable Game Logging',
            'help.s1.intro': "TITrack reads the game's log file to track your loot. To enable logging:",
            'help.s1.step1': 'Open Torchlight Infinite',
            'help.s1.step2': 'Go to <strong>Settings</strong>',
            'help.s1.step3': 'Find and click the <strong>"Enable Log"</strong> button',
            'help.s1.note': 'Without this enabled, TITrack cannot capture any data.',
            'help.s2.title': '2. Character Detection',
            'help.s2.intro': 'TITrack automatically detects your character from the game log:',
            'help.s2.b1': "If you've played before with logging enabled, your character is detected <strong>automatically</strong> on startup",
            'help.s2.b2': 'If this is your first time, log in with your character and TITrack will detect it',
            'help.s2.b3': 'To switch characters, just log out and back in (do NOT close the game)',
            'help.s2.note': 'TITrack tracks data separately for each character and league.',
            'help.s3.title': '3. Sync Your Inventory',
            'help.s3.intro': 'To populate the inventory display with your current items:',
            'help.s3.step1': 'Open your inventory in-game',
            'help.s3.step2': 'Click the <strong>Sort</strong> button (auto-arranges items)',
            'help.s3.step3': 'Repeat for each tab you want to track (Skill, Commodity, Others)',
            'help.s3.note': 'The Gear tab is not tracked because gear prices depend heavily on specific affixes.',
            'help.s4.title': '4. Automatic Price Learning',
            'help.s4.intro': 'TITrack learns item prices automatically when you use the in-game Exchange:',
            'help.s4.step1': 'Open the Exchange in-game',
            'help.s4.step2': 'Search for any item you want to price',
            'help.s4.step3': 'TITrack captures the listed prices and calculates a reference price (10th percentile)',
            'help.s4.note': 'Prices are saved locally and used to calculate your loot value and net worth.',
            'help.s5.title': '5. Tracking Runs',
            'help.s5.intro': 'Once logging is enabled, TITrack automatically:',
            'help.s5.b1': 'Detects when you enter and leave maps',
            'help.s5.b2': 'Tracks all items picked up during each run',
            'help.s5.b3': 'Calculates value based on learned prices',
            'help.s5.b4': 'Shows your FE/Hour based on active run time only',
            'help.s6.title': '6. Cloud Sync (Optional)',
            'help.s6.intro': 'Share and receive community pricing data by enabling Cloud Sync:',
            'help.s6.step1': 'Click the <strong>Cloud Sync</strong> toggle in the header',
            'help.s6.step2': 'When enabled, your Exchange searches are anonymously shared',
            'help.s6.step3': "You'll receive aggregated prices from other users",
            'help.s6.benefits': 'Benefits:',
            'help.s6.b1': "Get prices for items you haven't searched yet",
            'help.s6.b2': 'See price trends with sparkline charts',
            'help.s6.b3': 'Help the community by contributing your data',
            'help.s6.note': 'Cloud Sync is completely optional and anonymous. No account required. Only Exchange prices are shared, never manual edits. Data requires 3+ contributors before being shown.',
            // No-character modal
            'nochar.title': 'Character Not Detected',
            'nochar.dismiss': 'Dismiss',
            'nochar.diagnostics': 'Diagnostics',
            'nochar.checking': 'Checking log activity...',
            'nochar.detect_title': 'How character detection works',
            'nochar.detect_intro': "TITrack reads your character name and season from the game log, but Torchlight only writes those details when its <strong>Enable Log</strong> setting is on <em>at the exact moment</em> the game's login-time data packet arrives. Enabling the log after you're already logged in is not enough — you need to trigger a new login while the log is on.",
            'nochar.try_title': 'Try this first',
            'nochar.try_step1': 'Open Torchlight Infinite and log in to your character as usual.',
            'nochar.try_step2': 'Open the in-game <strong>Settings</strong> menu and turn on <strong>Enable Log</strong>.',
            'nochar.try_step3': "Exit all the way back to the <strong>Select Character</strong> screen (you don't need to quit the client).",
            'nochar.try_step4': 'Click your character to log back in.',
            'nochar.try_note': 'This works because the server re-sends your full character data on every login, and Torchlight only writes it to the log when Enable Log is already on when that packet arrives.',
            'nochar.fail_title': "If that didn't work",
            'nochar.fail_intro': 'On some sessions the game records only a truncated placeholder (<code>+player+...</code>) for your character even with logging on. Resetting the client usually clears this:',
            'nochar.fail_step1': 'Fully close Torchlight Infinite (quit to desktop — not just log out).',
            'nochar.fail_step2': 'Reopen the client and log in to your character.',
            'nochar.fail_step3': 'Open <strong>Settings</strong> and turn on <strong>Enable Log</strong>.',
            'nochar.fail_step4': 'Exit to <strong>Select Character</strong> and log back in.',
            'nochar.fail_note': "A sort of your inventory (click the Sort button in your bag) also forces a fresh inventory dump, which is a useful extra nudge if detection still doesn't fire.",
            'nochar.other_title': 'Other things to check',
            'nochar.other_b1': "<strong>Wrong log file.</strong> If you have both the Steam and standalone Torchlight client installed, TITrack may be watching the log for the client you aren't currently playing on. The diagnostic above will suggest a switch when it detects a newer log elsewhere.",
            'nochar.other_b2': "<strong>Game closed.</strong> Torchlight only writes to its log while it's running. If you quit the game, the log stops updating and TITrack will flag it as stale.",
            'nochar.other_b3': "<strong>Enable Log doesn't persist.</strong> Torchlight resets this toggle to off every time the client restarts. You need to turn it back on each session.",
            // Toasts / misc
            'toast.low_supply': 'Low Supply: {name} — {qty} remaining (threshold: {threshold})',
            'toast.exported_to': 'Exported to {file}',
            'unit.fe': 'FE',
            'unit.fe_per_hour': 'FE/Hour',
            'unit.fe_per_map': 'FE/Map',
            'misc.unknown_item': 'Unknown {id}',
            // Cost tooltip line: "Item x123 = 456"
            'misc.cost_line': '{name} x{qty} = {value}',
        },
        'zh-CN': {
            // Header
            'header.app_title': 'TITrack',
            'header.awaiting_player': '正在等待识别角色…（请登录游戏或整理一下背包）',
            'header.see_details': '查看详情',
            'header.net_worth': '净资产',
            'header.cumulative_value': '累计价值',
            'header.fe_per_hour': '源质/小时',
            'header.fe_per_map': '源质/图',
            'header.runs': '地图数',
            'header.avg_run_time': '平均时间',
            'header.total_time': '总时长',
            'header.fe_per_hour_tooltip': '仅以游戏内地图运行时间为基准计算，城镇、驻地及地图间的等待时间不计入。此值反映打图效率，而非整体游戏时长。',
            'header.pause_tracking': '暂停统计',
            'header.resume_tracking': '继续统计',
            // Controls
            'controls.overlay': '悬浮窗',
            'controls.overlay_tooltip': '打开迷你悬浮窗',
            'controls.economy': '经济数据',
            'controls.economy_tooltip': '打开 titrack.ninja 经济数据',
            'controls.cloud_sync': '云端同步',
            'controls.cloud_sync_tooltip': '云端同步状态',
            'controls.settings': '设置',
            'controls.instructions': '使用说明',
            'controls.reset_stats': '重置统计',
            'controls.resetting': '正在重置…',
            'controls.auto_refresh': '自动刷新',
            // Charts
            'charts.cumulative_value': '累计价值',
            'charts.fe_per_hour': '源质 / 小时',
            // Active run
            'active_run.title_prefix': '当前地图：',
            'active_run.value': '价值：',
            'active_run.no_drops': '暂无掉落…',
            'active_run.previous_run': '上一张地图',
            // Recent runs
            'runs.title': '最近地图',
            'runs.report': '报表',
            'runs.col_zone': '地区',
            'runs.col_duration': '耗时',
            'runs.col_value': '价值',
            'runs.loading': '加载中…',
            'runs.none': '暂无地图记录',
            'runs.details': '详情',
            'runs.gross': '总收益：',
            'runs.cost': '消耗：',
            // Inventory
            'inventory.title': '当前背包',
            'inventory.hide_items': '隐藏物品',
            'inventory.hide_items_count': '隐藏物品（{count}）',
            'inventory.col_item': '物品',
            'inventory.col_qty': '数量',
            'inventory.col_value': '价值',
            'inventory.col_trend': '趋势',
            'inventory.trend_tooltip': '价格趋势（72小时）',
            'inventory.filter_tooltip': '按背包页筛选',
            'inventory.tab_all': '全部',
            'inventory.tab_gear': '装备',
            'inventory.tab_skill': '技能',
            'inventory.tab_commodity': '通货',
            'inventory.tab_others': '杂项',
            'inventory.empty': '背包为空',
            // Footer
            'footer.last_updated': '最后更新：{time}',
            'footer.collector': '采集器：{state}',
            'footer.collector_running': '运行中',
            'footer.collector_stopped': '已停止',
            'footer.discord_tooltip': '加入 TITrack 的 Discord',
            'footer.kofi_tooltip': '帮助分担服务器费用',
            'footer.kofi': '帮助分担服务器费用',
            'footer.check_updates': '检查更新',
            'footer.update_tooltip': '有可用更新',
            'footer.exit': '退出程序',
            'footer.checking': '检查中…',
            'footer.update_available': '有可用更新！',
            'footer.downloading': '下载中…',
            'footer.install_update': '安装更新',
            // Run details modal
            'modal.run_details': '地图详情',
            'modal.ignore_run': '✕ 忽略此地图',
            'modal.run_ignored': '✓ 已忽略此地图',
            // Settings modal
            'settings.title': '设置',
            'settings.section_value': '价值计算',
            'settings.trade_tax': '交易税',
            'settings.trade_tax_desc': '对物品价值应用 12.5% 的交易行税率',
            'settings.map_costs': '地图开销',
            'settings.map_costs_desc': '统计并扣除指南针/信标等开图消耗',
            'settings.realtime': '实时计时',
            'settings.realtime_desc': '使用真实时间计算 源质/小时 与 总时长（而非仅游戏内地图时间）',
            'settings.section_overlay': '悬浮窗',
            'settings.overlay_hide_loot': '隐藏掉落列表',
            'settings.overlay_hide_loot_desc': '在悬浮窗中隐藏掉落区域，使界面更紧凑（仅显示数据）',
            'settings.overlay_micro': '迷你悬浮窗',
            'settings.overlay_micro_desc': '改用紧凑模式仅显示关键数据',
            'settings.layout': '布局：',
            'settings.layout_horizontal': '横向',
            'settings.layout_vertical': '纵向',
            'settings.font_size': '字号：',
            'settings.visible_stats': '显示项：',
            'settings.drag_to_reorder': '（可拖拽排序）',
            'settings.section_supply': '低库存提醒',
            'settings.supply_desc': '当开图消耗品的数量低于阈值时提醒，设为 0 表示不提醒。',
            'settings.supply_beacons': '信标',
            'settings.supply_compasses': '指南针',
            'settings.supply_resonance': '共振石',
            'settings.section_game_dir': '游戏目录',
            'settings.current_path': '当前路径：',
            'settings.path_placeholder': 'C:\\Torchlight Infinite 或 C:\\…\\Logs\\UE_game.log',
            'settings.browse': '浏览',
            'settings.validate': '校验',
            'settings.path_help': '可填写游戏目录、Logs 文件夹或 UE_game.log 的完整路径',
            'settings.save_restart': '保存并重启',
            'settings.saved_restart_required': '已保存 - 需要重启',
            'settings.saving': '保存中…',
            'settings.section_language': '语言',
            'settings.language_label': '语言',
            'settings.language_desc': '面板与悬浮窗的显示语言',
            'settings.path_validating': '校验中…',
            'settings.path_enter': '请填写一个路径',
            'settings.path_found': '已找到：{path}',
            'settings.path_not_found': '在该位置未找到日志文件',
            'settings.path_error': '校验失败，请重试。',
            'settings.path_loading': '加载中…',
            'settings.path_not_found_short': '未找到 - 请在下方配置',
            'settings.path_unable': '无法获取当前路径',
            'settings.saved_msg': '已保存！请重启 TITrack 使更改生效。',
            'settings.error_saving': '保存失败，请重试。',
            // Loot report
            'report.title': '掉落报表',
            'report.gross': '总价值',
            'report.map_costs': '地图开销',
            'report.profit': '利润',
            'report.runs': '地图数',
            'report.total_time': '总时长',
            'report.profit_per_hour': '利润/小时',
            'report.profit_per_map': '利润/图',
            'report.unique_items': '物品种类',
            'report.col_item': '物品',
            'report.col_qty': '数量',
            'report.col_unit_price': '单价',
            'report.col_total_value': '总价值',
            'report.col_pct': '%',
            'report.export_csv': '导出 CSV',
            'report.close': '关闭',
            'report.loading': '正在加载报表…',
            'report.failed': '加载报表失败',
            'report.empty': '暂无掉落数据，完成几张地图后再查看报表。',
            // Hide items modal
            'hide.title': '从背包中隐藏物品',
            'hide.hint': '勾选要从背包中隐藏的物品。隐藏的物品仍计入净资产。',
            'hide.hint_excluded': '勾选要从背包中隐藏的物品。隐藏的物品不会计入净资产。',
            'hide.exclude_worth': '从净资产中排除',
            'hide.exclude_worth_desc': '隐藏的物品不会计入净资产',
            'hide.search': '搜索物品…',
            'hide.col_item': '物品',
            'hide.col_qty': '数量',
            'hide.col_value': '价值',
            'hide.save': '保存',
            'hide.cancel': '取消',
            'hide.count': '已隐藏 {count} 个物品',
            'hide.empty': '背包为空',
            // Update modal
            'update.title': '有可用更新',
            'update.release_notes': '更新说明',
            'update.loading': '加载中…',
            'update.no_notes': '暂无更新说明。',
            'update.download_install': '下载并安装',
            'update.later': '稍后',
            'update.downloading_progress': '下载中… {mb} / {total} MB',
            'update.installing': '下载完成，正在安装…',
            'update.ready_install': '准备安装',
            'update.failed': '下载失败：{error}',
            'update.retry': '重试',
            'update.unknown_error': '未知错误',
            'update.shutdown': 'TITrack 已关闭，可以关闭此标签页了。',
            // Help modal
            'help.title': '如何使用 TITrack',
            'help.s1.title': '1. 开启游戏日志',
            'help.s1.intro': 'TITrack 通过读取游戏日志文件来追踪你的掉落。开启方式：',
            'help.s1.step1': '打开《无限火炬》',
            'help.s1.step2': '进入 <strong>设置</strong>',
            'help.s1.step3': '找到并点击 <strong>"启用日志"</strong> 按钮',
            'help.s1.note': '不开启此选项的话，TITrack 无法采集任何数据。',
            'help.s2.title': '2. 角色识别',
            'help.s2.intro': 'TITrack 会自动从游戏日志中识别你的角色：',
            'help.s2.b1': '如果你之前在开启日志的情况下游玩过，启动时会 <strong>自动</strong> 识别你的角色',
            'help.s2.b2': '如果是首次使用，登录角色后 TITrack 会自动识别',
            'help.s2.b3': '切换角色只需登出再登入即可（不要关闭游戏）',
            'help.s2.note': 'TITrack 会按角色和赛季分别保存数据。',
            'help.s3.title': '3. 同步背包',
            'help.s3.intro': '让背包面板显示当前物品的方法：',
            'help.s3.step1': '在游戏内打开背包',
            'help.s3.step2': '点击 <strong>整理</strong> 按钮（自动排列物品）',
            'help.s3.step3': '在每个需要追踪的页签重复操作（技能、商品、其他）',
            'help.s3.note': '装备页不会被追踪，因为装备价格高度依赖于具体词缀。',
            'help.s4.title': '4. 自动学习价格',
            'help.s4.intro': '当你在游戏内使用交易行时，TITrack 会自动学习物品价格：',
            'help.s4.step1': '在游戏内打开交易行',
            'help.s4.step2': '搜索你想要定价的任意物品',
            'help.s4.step3': 'TITrack 会捕获挂单价格，并以第 10 百分位作为参考价',
            'help.s4.note': '价格保存在本地，用于计算你的掉落价值与净资产。',
            'help.s5.title': '5. 追踪打图',
            'help.s5.intro': '开启日志后，TITrack 会自动：',
            'help.s5.b1': '识别进入和离开地图',
            'help.s5.b2': '追踪每张图中拾取的所有物品',
            'help.s5.b3': '基于已学价格计算价值',
            'help.s5.b4': '仅以地图运行时间为基准计算源质/小时',
            'help.s6.title': '6. 云端同步（可选）',
            'help.s6.intro': '通过开启云端同步来共享和接收社区价格数据：',
            'help.s6.step1': '点击页头的 <strong>云端同步</strong> 开关',
            'help.s6.step2': '开启后，你的交易行搜索会被匿名共享',
            'help.s6.step3': '你将收到来自其他用户的聚合价格',
            'help.s6.benefits': '好处：',
            'help.s6.b1': '获得你尚未搜索过物品的价格',
            'help.s6.b2': '通过迷你折线图查看价格趋势',
            'help.s6.b3': '通过贡献数据帮助整个社区',
            'help.s6.note': '云端同步完全可选且匿名，无需账户。仅共享交易行价格，绝不共享手工修改。数据需要至少 3 名贡献者后才会显示。',
            // No-character modal
            'nochar.title': '未识别到角色',
            'nochar.dismiss': '关闭',
            'nochar.diagnostics': '诊断信息',
            'nochar.checking': '正在检查日志…',
            'nochar.detect_title': '角色识别原理',
            'nochar.detect_intro': 'TITrack 从游戏日志中读取你的角色名和赛季信息，但《无限火炬》仅在登录时数据包到达 <em>那一刻</em> 其 <strong>启用日志</strong> 选项已开启时，才会写入这些细节。已经登录后再开启日志是不够的——你需要在日志开启的状态下重新触发一次登录。',
            'nochar.try_title': '请先尝试',
            'nochar.try_step1': '正常打开《无限火炬》并登录角色。',
            'nochar.try_step2': '打开游戏内 <strong>设置</strong> 菜单，开启 <strong>启用日志</strong>。',
            'nochar.try_step3': '一路返回到 <strong>选择角色</strong> 界面（不需要退出客户端）。',
            'nochar.try_step4': '点击角色重新登录。',
            'nochar.try_note': '之所以有效，是因为服务器在每次登录时都会重新发送完整的角色数据，而《无限火炬》只在那个数据包到达时启用日志已开启的情况下才会写入。',
            'nochar.fail_title': '如果上面的方法没用',
            'nochar.fail_intro': '在某些会话中，即使开启了日志，游戏也只会记录一个被截断的占位符（<code>+player+...</code>）。重启客户端通常能清除这种状态：',
            'nochar.fail_step1': '完全关闭《无限火炬》（退出到桌面，而不仅是登出）。',
            'nochar.fail_step2': '重新打开客户端并登录角色。',
            'nochar.fail_step3': '打开 <strong>设置</strong> 并开启 <strong>启用日志</strong>。',
            'nochar.fail_step4': '退出到 <strong>选择角色</strong> 界面，再重新登录。',
            'nochar.fail_note': '在背包中点击整理按钮也会强制游戏重新输出一次完整背包，如果识别仍然失败，这是一个有用的额外触发方式。',
            'nochar.other_title': '其它需要排查的问题',
            'nochar.other_b1': '<strong>日志文件不对。</strong> 如果你同时安装了 Steam 版和单机版的《无限火炬》，TITrack 可能正在监视你当前没在游玩的那个客户端的日志。当上方诊断信息检测到其它位置有更新的日志时，会建议切换。',
            'nochar.other_b2': '<strong>游戏已关闭。</strong>《无限火炬》只在运行时才会写入日志。如果你退出了游戏，日志就会停止更新，TITrack 会将其标记为已过期。',
            'nochar.other_b3': '<strong>"启用日志" 不会保留。</strong>《无限火炬》每次客户端重启时都会把这个开关重置为关闭状态。每次开机都需要重新打开。',
            // Toasts / misc
            'toast.low_supply': '低库存：{name} — 剩余 {qty}（阈值：{threshold}）',
            'toast.exported_to': '已导出至 {file}',
            'unit.fe': '源质',
            'unit.fe_per_hour': '源质/小时',
            'unit.fe_per_map': '源质/图',
            'misc.unknown_item': '未知物品 {id}',
            'misc.cost_line': '{name} x{qty} = {value}',
        },
    };

    const SUPPORTED_LANGS = ['en', 'zh-CN'];
    const STORAGE_KEY = 'titrack.lang';
    let currentLang = 'en';
    let zoneTranslations = {}; // {lang: {englishLabel: cnLabel}} — fetched from /api/i18n/zones

    // Load cached preference synchronously so the very first render is correct.
    try {
        const cached = localStorage.getItem(STORAGE_KEY);
        if (cached && SUPPORTED_LANGS.indexOf(cached) !== -1) {
            currentLang = cached;
        }
    } catch (_) { /* localStorage may be unavailable */ }

    function getLang() {
        return currentLang;
    }

    function interpolate(str, vars) {
        if (!vars || typeof str !== 'string') return str;
        return str.replace(/\{(\w+)\}/g, function (_, k) {
            return Object.prototype.hasOwnProperty.call(vars, k) ? String(vars[k]) : '{' + k + '}';
        });
    }

    function t(key, vars) {
        const dict = TRANSLATIONS[currentLang] || {};
        const fallback = TRANSLATIONS.en || {};
        const raw = (dict[key] !== undefined) ? dict[key] : (fallback[key] !== undefined ? fallback[key] : key);
        return interpolate(raw, vars);
    }

    function pickItemName(item) {
        if (!item) return '';
        if (currentLang === 'zh-CN' && item.name_cn) return item.name_cn;
        if (item.name_en) return item.name_en;
        if (item.name) return item.name; // backwards-compat
        if (item.config_base_id != null) return t('misc.unknown_item', { id: item.config_base_id });
        return '';
    }

    function pickItemUrl(item) {
        if (!item) return null;
        if (currentLang === 'zh-CN' && item.url_cn) return item.url_cn;
        return item.url_en || null;
    }

    function pickSeasonName(player) {
        if (!player) return '';
        if (currentLang === 'zh-CN' && player.season_name_cn) return player.season_name_cn;
        return player.season_name_en || player.season_name || '';
    }

    function pickHeroName(player) {
        if (!player) return '';
        if (currentLang === 'zh-CN' && player.hero_name_cn) return player.hero_name_cn;
        return player.hero_name_en || player.hero_name || '';
    }

    function tZone(englishName) {
        if (!englishName) return englishName;
        if (currentLang === 'en') return englishName;
        const table = zoneTranslations[currentLang];
        if (!table) return englishName;
        // Direct hit
        if (table[englishName]) return table[englishName];
        // Handle " (Nightmare)" runtime suffix
        const NM = ' (Nightmare)';
        if (englishName.endsWith(NM)) {
            const base = englishName.slice(0, -NM.length);
            const tr = table[base];
            const nmSuffix = table['(Nightmare)'] || NM;
            return (tr ? tr : base) + nmSuffix;
        }
        return englishName;
    }

    async function loadZoneTranslations() {
        if (zoneTranslations['zh-CN']) return; // already loaded
        try {
            const resp = await fetch('/api/i18n/zones');
            if (resp.ok) {
                zoneTranslations = await resp.json();
            }
        } catch (_) { /* offline-friendly: silently ignore */ }
    }

    function applyTranslations(root) {
        const r = root || document;
        // textContent
        r.querySelectorAll('[data-i18n]').forEach(function (el) {
            const key = el.getAttribute('data-i18n');
            if (key) el.textContent = t(key);
        });
        // innerHTML (for strings containing <strong>, <em>, etc.)
        r.querySelectorAll('[data-i18n-html]').forEach(function (el) {
            const key = el.getAttribute('data-i18n-html');
            if (key) el.innerHTML = t(key);
        });
        // title attr
        r.querySelectorAll('[data-i18n-title]').forEach(function (el) {
            const key = el.getAttribute('data-i18n-title');
            if (key) el.setAttribute('title', t(key));
        });
        // placeholder attr
        r.querySelectorAll('[data-i18n-placeholder]').forEach(function (el) {
            const key = el.getAttribute('data-i18n-placeholder');
            if (key) el.setAttribute('placeholder', t(key));
        });
        // <html lang="...">
        if (document.documentElement) {
            document.documentElement.setAttribute('lang', currentLang);
        }
    }

    function setLang(lang) {
        if (SUPPORTED_LANGS.indexOf(lang) === -1) lang = 'en';
        if (lang === currentLang) return;
        currentLang = lang;
        try { localStorage.setItem(STORAGE_KEY, lang); } catch (_) { }
        applyTranslations();
        document.dispatchEvent(new CustomEvent('langchange', { detail: { lang: lang } }));
    }

    // Initialize as soon as DOM is parsed so static labels are correct on first paint.
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () {
            applyTranslations();
            loadZoneTranslations();
        });
    } else {
        applyTranslations();
        loadZoneTranslations();
    }

    global.i18n = {
        t: t,
        pickItemName: pickItemName,
        pickItemUrl: pickItemUrl,
        pickSeasonName: pickSeasonName,
        pickHeroName: pickHeroName,
        tZone: tZone,
        setLang: setLang,
        getLang: getLang,
        applyTranslations: applyTranslations,
        loadZoneTranslations: loadZoneTranslations,
        SUPPORTED_LANGS: SUPPORTED_LANGS,
    };
    // Convenience globals (kept short for inline usage)
    global.t = t;
    global.tZone = tZone;
    global.pickItemName = pickItemName;
    global.pickItemUrl = pickItemUrl;
    global.pickSeasonName = pickSeasonName;
    global.pickHeroName = pickHeroName;
})(window);
