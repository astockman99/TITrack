using System.Net.Http;
using System.Text.Json;

namespace TITrackOverlay;

/// <summary>
/// Lightweight localization helper for the overlay window.
///
/// Mirrors the web frontend's i18n.js behaviour:
/// - Two languages: "en" (default) and "zh-CN".
/// - Item-name selection prefers name_cn when language == zh-CN and name_cn is non-empty,
///   otherwise falls back to name_en (or the legacy name field).
/// - Zone names are translated via a table downloaded once from /api/i18n/zones.
/// - Static UI strings (labels, "No active run", supply alerts, tooltips) are looked
///   up in <see cref="Strings"/>; missing keys fall back to English.
///
/// The overlay polls the language setting every refresh tick. When the value
/// changes, <see cref="LanguageChanged"/> fires so the UI can reapply labels.
/// </summary>
internal static class Localization
{
    public const string LangEn = "en";
    public const string LangZh = "zh-CN";

    public static string CurrentLang { get; private set; } = LangEn;

    /// <summary>Fired when SetLang() actually changes the current language.</summary>
    public static event Action<string>? LanguageChanged;

    private static Dictionary<string, string>? _zoneNamesCn;
    private static bool _zonesLoadAttempted;

    // Static UI strings. Keep keys identical to the Python/JS side where possible.
    private static readonly Dictionary<string, Dictionary<string, string>> Strings = new()
    {
        [LangEn] = new()
        {
            // Main overlay labels
            ["overlay.title"] = "TITrack Overlay",
            ["overlay.net_worth"] = "Net Worth",
            ["overlay.this_run"] = "This Run",
            ["overlay.previous_run"] = "Previous Run",
            ["overlay.fe_per_hour"] = "FE/Hour",
            ["overlay.fe_per_map"] = "FE/Map",
            ["overlay.runs"] = "Runs",
            ["overlay.avg_time"] = "Avg Time",
            ["overlay.total_time"] = "Total Time",
            ["overlay.no_active_run"] = "No active run",
            ["overlay.unknown_zone"] = "Unknown Zone",
            // Tooltips
            ["overlay.tip_decrease_text"] = "Decrease text size",
            ["overlay.tip_increase_text"] = "Increase text size",
            ["overlay.tip_transparency"] = "Toggle transparency",
            ["overlay.tip_pause"] = "Pause/resume tracking",
            ["overlay.tip_lock"] = "Lock overlay (click-through)",
            ["overlay.tip_close"] = "Close overlay",
            // Supply alert (mirrors low-supply toast text on the web)
            ["overlay.supply_alert"] = "\u26a0 Low: {0} \u2014 {1} left",
            // Micro overlay short labels
            ["micro.time"] = "Time",
            ["micro.fe_per_hr"] = "FE/hr",
            ["micro.total"] = "Total",
            ["micro.nw"] = "NW",
            ["micro.run"] = "Run",
            ["micro.fe_per_map"] = "FE/Map",
            ["micro.runs"] = "Runs",
            ["micro.avg"] = "Avg",
            // Misc
            ["overlay.unknown_item"] = "Unknown ({0})",
        },
        [LangZh] = new()
        {
            ["overlay.title"] = "TITrack \u60ac\u6d6e\u7a97",
            ["overlay.net_worth"] = "\u51c0\u8d44\u4ea7",
            ["overlay.this_run"] = "\u5f53\u524d\u5730\u56fe",
            ["overlay.previous_run"] = "\u4e0a\u4e00\u5f20\u5730\u56fe",
            ["overlay.fe_per_hour"] = "\u6e90\u8d28/\u5c0f\u65f6",
            ["overlay.fe_per_map"] = "\u6e90\u8d28/\u56fe",
            ["overlay.runs"] = "\u5730\u56fe\u6570",
            ["overlay.avg_time"] = "\u5e73\u5747\u65f6\u95f4",
            ["overlay.total_time"] = "\u603b\u65f6\u957f",
            ["overlay.no_active_run"] = "\u5f53\u524d\u672a\u5728\u5730\u56fe\u4e2d",
            ["overlay.unknown_zone"] = "\u672a\u77e5\u533a\u57df",
            ["overlay.tip_decrease_text"] = "\u7f29\u5c0f\u6587\u5b57",
            ["overlay.tip_increase_text"] = "\u653e\u5927\u6587\u5b57",
            ["overlay.tip_transparency"] = "\u5207\u6362\u900f\u660e\u5ea6",
            ["overlay.tip_pause"] = "\u6682\u505c / \u7ee7\u7eed\u8ba1\u65f6",
            ["overlay.tip_lock"] = "\u9501\u5b9a\u60ac\u6d6e\u7a97\uff08\u70b9\u51fb\u7a7f\u900f\uff09",
            ["overlay.tip_close"] = "\u5173\u95ed\u60ac\u6d6e\u7a97",
            ["overlay.supply_alert"] = "\u26a0 \u4f4e\u5e93\u5b58\uff1a{0} \u2014 \u5269\u4f59 {1}",
            ["micro.time"] = "\u65f6\u957f",
            ["micro.fe_per_hr"] = "\u6e90\u8d28/\u65f6",
            ["micro.total"] = "\u603b\u989d",
            ["micro.nw"] = "\u51c0\u8d44",
            ["micro.run"] = "\u672c\u56fe",
            ["micro.fe_per_map"] = "\u6e90\u8d28/\u56fe",
            ["micro.runs"] = "\u5730\u56fe\u6570",
            ["micro.avg"] = "\u5747\u503c",
            ["overlay.unknown_item"] = "\u672a\u77e5\u7269\u54c1\uff08{0}\uff09",
        },
    };

    /// <summary>Translate a key. Falls back to English then the key itself.</summary>
    public static string Tr(string key)
    {
        if (Strings.TryGetValue(CurrentLang, out var dict) && dict.TryGetValue(key, out var s))
            return s;
        if (Strings[LangEn].TryGetValue(key, out var fallback))
            return fallback;
        return key;
    }

    /// <summary>Translate with positional substitution (string.Format-style).</summary>
    public static string Tr(string key, params object?[] args)
    {
        return string.Format(Tr(key), args);
    }

    /// <summary>
    /// Pick the best display name for a JSON-loot item, considering name_cn / name_en
    /// / legacy name in priority order.
    /// </summary>
    public static string PickItemName(string? nameEn, string? nameCn, string? legacyName, int configBaseId)
    {
        if (CurrentLang == LangZh && !string.IsNullOrEmpty(nameCn))
            return nameCn!;
        if (!string.IsNullOrEmpty(nameEn))
            return nameEn!;
        if (!string.IsNullOrEmpty(legacyName))
            return legacyName!;
        return Tr("overlay.unknown_item", configBaseId);
    }

    /// <summary>
    /// Translate a zone display name. Returns the original English string when
    /// no translation table is loaded or no entry matches; preserves the
    /// " (Nightmare)" runtime suffix.
    /// </summary>
    public static string TZone(string? englishName)
    {
        if (string.IsNullOrEmpty(englishName) || CurrentLang == LangEn) return englishName ?? string.Empty;
        if (_zoneNamesCn == null) return englishName!;

        if (_zoneNamesCn.TryGetValue(englishName!, out var hit))
            return hit;

        const string nm = " (Nightmare)";
        if (englishName!.EndsWith(nm, StringComparison.Ordinal))
        {
            var baseName = englishName[..^nm.Length];
            var baseTr = _zoneNamesCn.TryGetValue(baseName, out var b) ? b : baseName;
            var nmSuffix = _zoneNamesCn.TryGetValue("(Nightmare)", out var n) ? n : nm;
            return baseTr + nmSuffix;
        }
        return englishName;
    }

    /// <summary>Set the active language and notify subscribers if it changed.</summary>
    public static void SetLang(string? lang)
    {
        var normalized = lang == LangZh ? LangZh : LangEn;
        if (normalized == CurrentLang) return;
        CurrentLang = normalized;
        LanguageChanged?.Invoke(CurrentLang);
    }

    /// <summary>
    /// Fetch the zone-translation table from /api/i18n/zones. Idempotent: only
    /// runs once per process; subsequent calls are no-ops.
    /// </summary>
    public static async Task EnsureZoneTranslationsAsync(HttpClient http, string baseUrl)
    {
        if (_zonesLoadAttempted) return;
        _zonesLoadAttempted = true;
        try
        {
            var resp = await http.GetAsync($"{baseUrl}/api/i18n/zones");
            if (!resp.IsSuccessStatusCode) return;
            var json = await resp.Content.ReadAsStringAsync();
            using var doc = JsonDocument.Parse(json);
            if (doc.RootElement.TryGetProperty(LangZh, out var zhEl))
            {
                var dict = new Dictionary<string, string>(StringComparer.Ordinal);
                foreach (var prop in zhEl.EnumerateObject())
                {
                    if (prop.Value.ValueKind == JsonValueKind.String)
                    {
                        var v = prop.Value.GetString();
                        if (!string.IsNullOrEmpty(v))
                            dict[prop.Name] = v!;
                    }
                }
                _zoneNamesCn = dict;
            }
        }
        catch
        {
            // Offline-friendly: fall back to English on any error.
            _zonesLoadAttempted = false; // allow retry next refresh
        }
    }
}
