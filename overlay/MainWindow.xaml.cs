using System.Net.Http;
using System.Runtime.InteropServices;
using System.Text.Json;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Interop;
using System.Windows.Media;
using System.Windows.Media.Effects;
using System.Windows.Media.Imaging;
using System.Windows.Threading;

namespace TITrackOverlay;

public partial class MainWindow : Window
{
    // Win32 interop for click-through lock
    private const int GWL_EXSTYLE = -20;
    private const int WS_EX_TRANSPARENT = 0x00000020;

    [DllImport("user32.dll")]
    private static extern int GetWindowLong(IntPtr hwnd, int index);

    [DllImport("user32.dll")]
    private static extern int SetWindowLong(IntPtr hwnd, int index, int newStyle);

    private readonly HttpClient _httpClient;
    private readonly DispatcherTimer _refreshTimer;
    private readonly Dictionary<int, BitmapImage?> _iconCache = new();
    private readonly HashSet<int> _failedIcons = new();

    private bool _isTransparent = false;
    private bool _isLocked = false;
    private Window? _unlockWindow;
    private double _fontScale = 1.0;
    private const double MinFontScale = 0.7;
    private const double MaxFontScale = 1.6;
    private const double FontScaleStep = 0.1;

    // Overlay settings
    private bool _hideLoot = false;
    private bool _hideLootInitialized = false;
    private double _savedHeight = 500;
    private const double CompactMinHeight = 120;
    private const double DefaultWidth = 320;
    private const double MinPaddingScale = 0.25;

    // Micro mode state
    private bool _microMode = false;
    private bool _microModeInitialized = false;
    private List<string> _microStats = new() { "total_time", "value_per_hour", "total_value" };
    private string _microStatsJson = "";
    private string _microOrientation = "horizontal";
    private double _microFontScale = 1.0;
    private readonly Dictionary<string, TextBlock> _microValueBlocks = new();
    private double _savedNormalWidth = 320;
    private double _savedNormalHeight = 500;
    private double _savedNormalLeft = double.NaN;
    private double _savedNormalTop = double.NaN;

    // Micro stat display config
    private static readonly Dictionary<string, string> MicroStatLabels = new()
    {
        { "total_time", "Time" },
        { "value_per_hour", "FE/hr" },
        { "total_value", "Total" },
        { "net_worth", "NW" },
        { "this_run", "Run" },
        { "value_per_map", "Val/Map" },
        { "runs", "Runs" },
        { "avg_time", "Avg" },
    };

    // Track previous run to show after map ends
    private ActiveRunResponse? _previousRun = null;
    private int? _lastActiveRunId = null;

    // Local ticker for smooth Total Time counting
    private readonly DispatcherTimer _tickTimer;
    private double _tickBaseSeconds = 0;
    private DateTime _tickBaseTimestamp;
    private bool _tickRunning = false;

    // Size save debounce
    private DispatcherTimer? _sizeDebounceTimer;

    // Colors for opaque mode
    private static readonly Color OpaqueMainBg = Color.FromArgb(0xF0, 0x1a, 0x1a, 0x2e);
    private static readonly Color OpaqueHeaderBg = Color.FromArgb(0xE0, 0x2a, 0x2a, 0x4a);
    private static readonly Color OpaqueStatBoxBg = Color.FromArgb(0xE0, 0x2a, 0x2a, 0x4a);
    private static readonly Color OpaqueLootSectionBg = Color.FromArgb(0xC0, 0x2a, 0x2a, 0x4a);
    private static readonly Color OpaqueZoneHeaderBg = Color.FromArgb(0xA0, 0x2a, 0x2a, 0x4a);
    private static readonly Color OpaqueBorderColor = Color.FromArgb(0xFF, 0x3a, 0x3a, 0x5a);

    // Drop shadow effect for transparent mode
    private static readonly DropShadowEffect TextShadow = new()
    {
        ShadowDepth = 1,
        BlurRadius = 3,
        Color = Colors.Black,
        Opacity = 0.9
    };

    // API response models
    private record StatsResponse(
        int total_runs,
        double total_value,
        double avg_value_per_run,
        double total_duration_seconds,
        double value_per_hour,
        bool realtime_tracking = false,
        bool realtime_paused = false,
        double map_duration_seconds = 0.0
    );

    private record LootItem(
        int config_base_id,
        string name,
        int quantity,
        string? icon_url,
        double? price_fe,
        double? total_value_fe
    );

    private record ActiveRunResponse(
        int id,
        string zone_name,
        string? zone_signature,
        double duration_seconds,
        double total_value,
        List<LootItem> loot,
        double? map_cost_fe,
        double? net_value_fe
    );

    private record InventoryResponse(
        double net_worth_fe
    );

    public MainWindow()
    {
        InitializeComponent();

        _httpClient = new HttpClient
        {
            Timeout = TimeSpan.FromSeconds(5)
        };

        _refreshTimer = new DispatcherTimer
        {
            Interval = TimeSpan.FromSeconds(2)
        };
        _refreshTimer.Tick += async (s, e) => await RefreshDataAsync();

        _tickTimer = new DispatcherTimer
        {
            Interval = TimeSpan.FromSeconds(1)
        };
        _tickTimer.Tick += (s, e) =>
        {
            if (_tickRunning)
            {
                var elapsed = (DateTime.UtcNow - _tickBaseTimestamp).TotalSeconds;
                var formatted = FormatDurationLong(_tickBaseSeconds + elapsed);
                TotalTimeText.Text = formatted;

                // Also update micro mode total_time if active
                if (_microMode && _microValueBlocks.TryGetValue("total_time", out var microBlock))
                {
                    microBlock.Text = formatted;
                }
            }
        };

        Loaded += async (s, e) =>
        {
            await LoadTransparencyAsync();
            await LoadFontScaleAsync();
            await LoadHideLootAsync();
            await LoadMicroModeAsync();
            if (_microMode)
            {
                await LoadMicroOrientationAsync();
                await LoadMicroStatsAsync();
                await LoadMicroFontScaleAsync();
            }
            await LoadPositionAsync();
            await LoadSizeAsync();
            await RefreshDataAsync();
            _refreshTimer.Start();
        };

        Closed += async (s, e) =>
        {
            _refreshTimer.Stop();
            _unlockWindow?.Close();
            // Save position and size before disposing
            try
            {
                await SavePositionAsync();
                await SaveSizeAsync();
            }
            catch
            {
                // Best-effort save on close
            }
            _httpClient.Dispose();
        };
    }

    private void Header_MouseLeftButtonDown(object sender, MouseButtonEventArgs e)
    {
        if (e.ClickCount == 2)
        {
            // Double-click to reset position
            Left = 100;
            Top = 100;
            _ = SavePositionAsync();
        }
        else
        {
            DragMove();
            _ = SavePositionAsync();
        }
    }

    private void Window_SizeChanged(object sender, SizeChangedEventArgs e)
    {
        // No padding scaling in micro mode
        if (_microMode) return;

        // Debounce size save to avoid spamming API during resize
        _sizeDebounceTimer?.Stop();
        _sizeDebounceTimer = new DispatcherTimer { Interval = TimeSpan.FromMilliseconds(500) };
        _sizeDebounceTimer.Tick += (_, _) =>
        {
            _sizeDebounceTimer.Stop();
            _ = SaveSizeAsync();
        };
        _sizeDebounceTimer.Start();

        // Scale padding proportionally as window shrinks below default width
        double scale = Math.Clamp(ActualWidth / DefaultWidth, MinPaddingScale, 1.0);

        double outerH = Math.Round(8 * scale);
        double outerV = Math.Round(6 * scale);
        double headerH = Math.Round(10 * scale);
        double headerV = Math.Round(8 * scale);
        double statPad = Math.Round(6 * scale);
        double statGap = Math.Round(3 * scale);
        double statRowGap = Math.Round(6 * scale);
        double zoneH = Math.Round(8 * scale);
        double zoneV = Math.Round(6 * scale);

        HeaderGrid.Margin = new Thickness(headerH, headerV, headerH, headerV);
        StatsGrid.Margin = new Thickness(outerH, outerV, outerH, 0);
        LootSectionBorder.Margin = new Thickness(outerH, outerV, outerH, outerH);
        ZoneHeaderBorder.Padding = new Thickness(zoneH, zoneV, zoneH, zoneV);

        // Stat box padding and gap margins
        var pad = new Thickness(statPad);
        ThisRunBox.Padding = pad;
        ValuePerHourBox.Padding = pad;
        ValuePerMapBox.Padding = pad;
        RunsBox.Padding = pad;
        AvgTimeBox.Padding = pad;
        TotalTimeBox.Padding = pad;

        ThisRunBox.Margin = new Thickness(0, 0, statGap, statRowGap);
        ValuePerHourBox.Margin = new Thickness(statGap, 0, 0, statRowGap);
        ValuePerMapBox.Margin = new Thickness(0, 0, statGap, statRowGap);
        RunsBox.Margin = new Thickness(statGap, 0, 0, statRowGap);
        AvgTimeBox.Margin = new Thickness(0, 0, statGap, 0);
        TotalTimeBox.Margin = new Thickness(statGap, 0, 0, 0);
    }

    private void CloseButton_Click(object sender, RoutedEventArgs e)
    {
        Close();
    }

    private void LockButton_Click(object sender, RoutedEventArgs e)
    {
        if (_isLocked)
            UnlockOverlay();
        else
            LockOverlay();
    }

    private void LockOverlay()
    {
        _isLocked = true;

        // Make entire window click-through via Win32
        var hwnd = new WindowInteropHelper(this).Handle;
        var extendedStyle = GetWindowLong(hwnd, GWL_EXSTYLE);
        SetWindowLong(hwnd, GWL_EXSTYLE, extendedStyle | WS_EX_TRANSPARENT);

        // Ensure always on top when locked
        Topmost = true;

        // Update icons in both layouts
        LockIcon.Text = "🔒";
        MicroLockIcon.Text = "🔒";

        // Show floating unlock button at the lock button's position
        ShowUnlockButton();
    }

    private void UnlockOverlay()
    {
        _isLocked = false;

        // Remove click-through
        var hwnd = new WindowInteropHelper(this).Handle;
        var extendedStyle = GetWindowLong(hwnd, GWL_EXSTYLE);
        SetWindowLong(hwnd, GWL_EXSTYLE, extendedStyle & ~WS_EX_TRANSPARENT);

        // Update icons in both layouts
        LockIcon.Text = "🔓";
        MicroLockIcon.Text = "🔓";

        // Hide floating unlock button
        _unlockWindow?.Hide();
    }

    private void ShowUnlockButton()
    {
        if (_unlockWindow == null)
            CreateUnlockWindow();

        PositionUnlockButton();
        _unlockWindow!.Show();
        _unlockWindow.Activate();
    }

    private void PositionUnlockButton()
    {
        if (_unlockWindow == null) return;

        // Use the appropriate lock button based on current mode
        var targetButton = _microMode ? MicroLockButton : LockButton;

        // Position relative to main window to avoid DPI coordinate mismatches
        var relativePoint = targetButton.TransformToAncestor(this).Transform(new Point(0, 0));
        _unlockWindow.Left = Left + relativePoint.X;
        _unlockWindow.Top = Top + relativePoint.Y;
        _unlockWindow.Width = targetButton.ActualWidth;
        _unlockWindow.Height = targetButton.ActualHeight;
    }

    private void CreateUnlockWindow()
    {
        _unlockWindow = new Window
        {
            WindowStyle = WindowStyle.None,
            AllowsTransparency = true,
            Background = Brushes.Transparent,
            Topmost = true,
            ShowInTaskbar = false,
            ResizeMode = ResizeMode.NoResize,
        };

        var border = new Border
        {
            Background = new SolidColorBrush(Color.FromArgb(0xE0, 0x2a, 0x2a, 0x4a)),
            CornerRadius = new CornerRadius(4),
            Cursor = Cursors.Hand,
            ToolTip = "Unlock overlay",
        };

        var text = new TextBlock
        {
            Text = "🔒",
            FontSize = 12,
            Foreground = new SolidColorBrush(Color.FromRgb(0xa0, 0xa0, 0xa0)),
            HorizontalAlignment = HorizontalAlignment.Center,
            VerticalAlignment = VerticalAlignment.Center,
        };

        border.Child = text;
        border.MouseLeftButtonDown += (s, e) => UnlockOverlay();
        border.MouseEnter += (s, e) => border.Background = new SolidColorBrush(Color.FromRgb(0x3a, 0x3a, 0x5a));
        border.MouseLeave += (s, e) => border.Background = new SolidColorBrush(Color.FromArgb(0xE0, 0x2a, 0x2a, 0x4a));

        _unlockWindow.Content = border;
    }

    private async void PauseButton_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            var response = await _httpClient.PostAsync($"{App.BaseUrl}/api/runs/pause", null);
            if (response.IsSuccessStatusCode)
            {
                // Trigger an immediate refresh to update the UI
                await RefreshDataAsync();
            }
        }
        catch
        {
            // Silently ignore errors
        }
    }

    private void FontDecreaseButton_Click(object sender, RoutedEventArgs e)
    {
        SetFontScale(_fontScale - FontScaleStep);
    }

    private void FontIncreaseButton_Click(object sender, RoutedEventArgs e)
    {
        SetFontScale(_fontScale + FontScaleStep);
    }

    private void SetFontScale(double scale)
    {
        _fontScale = Math.Clamp(scale, MinFontScale, MaxFontScale);
        ApplyFontScale();
        _ = SaveFontScaleAsync();
    }

    private void ApplyFontScale()
    {
        StatsScaleTransform.ScaleX = _fontScale;
        StatsScaleTransform.ScaleY = _fontScale;
        LootScaleTransform.ScaleX = _fontScale;
        LootScaleTransform.ScaleY = _fontScale;

        // Update button states
        FontDecreaseButton.IsEnabled = _fontScale > MinFontScale;
        FontIncreaseButton.IsEnabled = _fontScale < MaxFontScale;
        FontDecreaseButton.Opacity = _fontScale > MinFontScale ? 1.0 : 0.4;
        FontIncreaseButton.Opacity = _fontScale < MaxFontScale ? 1.0 : 0.4;
    }

    private async Task LoadFontScaleAsync()
    {
        try
        {
            var response = await _httpClient.GetAsync($"{App.BaseUrl}/api/settings/overlay_font_scale");
            if (response.IsSuccessStatusCode)
            {
                var json = await response.Content.ReadAsStringAsync();
                var doc = JsonDocument.Parse(json);
                if (doc.RootElement.TryGetProperty("value", out var valueElement) &&
                    valueElement.ValueKind != JsonValueKind.Null)
                {
                    var valueStr = valueElement.GetString();
                    if (double.TryParse(valueStr, System.Globalization.NumberStyles.Any,
                        System.Globalization.CultureInfo.InvariantCulture, out var savedScale))
                    {
                        _fontScale = Math.Clamp(savedScale, MinFontScale, MaxFontScale);
                    }
                }
            }
        }
        catch
        {
            // Use default scale on error
        }

        ApplyFontScale();
    }

    private async Task LoadHideLootAsync()
    {
        bool newHideLoot = _hideLoot;
        try
        {
            var response = await _httpClient.GetAsync($"{App.BaseUrl}/api/settings/overlay_hide_loot");
            if (response.IsSuccessStatusCode)
            {
                var json = await response.Content.ReadAsStringAsync();
                var doc = JsonDocument.Parse(json);
                if (doc.RootElement.TryGetProperty("value", out var valueElement) &&
                    valueElement.ValueKind != JsonValueKind.Null)
                {
                    newHideLoot = valueElement.GetString() == "true";
                }
            }
        }
        catch
        {
            // Use default on error
        }

        // Only apply layout changes when the setting actually changes
        if (newHideLoot == _hideLoot && _hideLootInitialized)
            return;

        _hideLoot = newHideLoot;
        _hideLootInitialized = true;

        LootSectionBorder.Visibility = _hideLoot ? Visibility.Collapsed : Visibility.Visible;
        ResizeGrip.Visibility = _hideLoot ? Visibility.Collapsed : Visibility.Visible;

        if (_hideLoot)
        {
            // Save current height before shrinking
            if (SizeToContent != SizeToContent.Height)
                _savedHeight = Height;
            MinHeight = CompactMinHeight;
            SizeToContent = SizeToContent.Height;
        }
        else
        {
            SizeToContent = SizeToContent.Manual;
            MinHeight = 300;
            Height = _savedHeight;
        }
    }

    private async Task SaveFontScaleAsync()
    {
        await SaveSettingAsync("overlay_font_scale",
            _fontScale.ToString(System.Globalization.CultureInfo.InvariantCulture));
    }

    // Generic settings helpers
    private async Task SaveSettingAsync(string key, string value)
    {
        try
        {
            var content = new StringContent(
                JsonSerializer.Serialize(new { value }),
                System.Text.Encoding.UTF8,
                "application/json");
            await _httpClient.PutAsync($"{App.BaseUrl}/api/settings/{key}", content);
        }
        catch
        {
            // Silently ignore save errors
        }
    }

    private async Task<string?> LoadSettingStringAsync(string key)
    {
        try
        {
            var response = await _httpClient.GetAsync($"{App.BaseUrl}/api/settings/{key}");
            if (response.IsSuccessStatusCode)
            {
                var json = await response.Content.ReadAsStringAsync();
                var doc = JsonDocument.Parse(json);
                if (doc.RootElement.TryGetProperty("value", out var valueElement) &&
                    valueElement.ValueKind != JsonValueKind.Null)
                {
                    return valueElement.GetString();
                }
            }
        }
        catch
        {
            // Return null on error
        }
        return null;
    }

    // Position/size persistence
    private async Task SavePositionAsync()
    {
        var key = _microMode ? "overlay_micro_position" : "overlay_position";
        var value = $"{Left.ToString(System.Globalization.CultureInfo.InvariantCulture)},{Top.ToString(System.Globalization.CultureInfo.InvariantCulture)}";
        await SaveSettingAsync(key, value);
    }

    private async Task LoadPositionAsync()
    {
        var key = _microMode ? "overlay_micro_position" : "overlay_position";
        var value = await LoadSettingStringAsync(key);
        if (value != null)
        {
            var parts = value.Split(',');
            if (parts.Length == 2 &&
                double.TryParse(parts[0], System.Globalization.NumberStyles.Any,
                    System.Globalization.CultureInfo.InvariantCulture, out var left) &&
                double.TryParse(parts[1], System.Globalization.NumberStyles.Any,
                    System.Globalization.CultureInfo.InvariantCulture, out var top))
            {
                // Validate position is on-screen
                var screenLeft = SystemParameters.VirtualScreenLeft;
                var screenTop = SystemParameters.VirtualScreenTop;
                var screenRight = screenLeft + SystemParameters.VirtualScreenWidth;
                var screenBottom = screenTop + SystemParameters.VirtualScreenHeight;

                if (left >= screenLeft && left < screenRight - 50 &&
                    top >= screenTop && top < screenBottom - 50)
                {
                    Left = left;
                    Top = top;
                }
            }
        }
    }

    private async Task SaveSizeAsync()
    {
        // Only save size in normal mode (micro auto-sizes)
        if (_microMode) return;
        var value = $"{Width.ToString(System.Globalization.CultureInfo.InvariantCulture)},{Height.ToString(System.Globalization.CultureInfo.InvariantCulture)}";
        await SaveSettingAsync("overlay_size", value);
    }

    private async Task LoadSizeAsync()
    {
        // Only load size in normal mode
        if (_microMode) return;
        var value = await LoadSettingStringAsync("overlay_size");
        if (value != null)
        {
            var parts = value.Split(',');
            if (parts.Length == 2 &&
                double.TryParse(parts[0], System.Globalization.NumberStyles.Any,
                    System.Globalization.CultureInfo.InvariantCulture, out var width) &&
                double.TryParse(parts[1], System.Globalization.NumberStyles.Any,
                    System.Globalization.CultureInfo.InvariantCulture, out var height))
            {
                if (width >= MinWidth && height >= MinHeight)
                {
                    Width = width;
                    Height = height;
                }
            }
        }
    }

    // Transparency persistence
    private async Task LoadTransparencyAsync()
    {
        var value = await LoadSettingStringAsync("overlay_transparent");
        if (value == "true")
        {
            _isTransparent = true;
            ApplyTransparency();
        }
    }

    private async Task SaveTransparencyAsync()
    {
        await SaveSettingAsync("overlay_transparent", _isTransparent ? "true" : "false");
    }

    private async Task LoadMicroModeAsync()
    {
        bool newMicroMode = _microMode;
        try
        {
            var response = await _httpClient.GetAsync($"{App.BaseUrl}/api/settings/overlay_micro_mode");
            if (response.IsSuccessStatusCode)
            {
                var json = await response.Content.ReadAsStringAsync();
                var doc = JsonDocument.Parse(json);
                if (doc.RootElement.TryGetProperty("value", out var valueElement) &&
                    valueElement.ValueKind != JsonValueKind.Null)
                {
                    newMicroMode = valueElement.GetString() == "true";
                }
            }
        }
        catch
        {
            // Use default on error
        }

        if (newMicroMode == _microMode && _microModeInitialized)
            return;

        _microMode = newMicroMode;
        _microModeInitialized = true;
        ApplyMicroMode();
    }

    private async Task LoadMicroStatsAsync()
    {
        try
        {
            var response = await _httpClient.GetAsync($"{App.BaseUrl}/api/settings/overlay_micro_stats");
            if (response.IsSuccessStatusCode)
            {
                var json = await response.Content.ReadAsStringAsync();
                var doc = JsonDocument.Parse(json);
                if (doc.RootElement.TryGetProperty("value", out var valueElement) &&
                    valueElement.ValueKind != JsonValueKind.Null)
                {
                    var valueStr = valueElement.GetString();
                    if (!string.IsNullOrEmpty(valueStr) && valueStr != _microStatsJson)
                    {
                        _microStatsJson = valueStr;
                        var parsed = JsonSerializer.Deserialize<List<string>>(valueStr);
                        if (parsed != null && parsed.Count > 0)
                        {
                            _microStats = parsed;
                            RebuildMicroStats();
                        }
                    }
                }
            }
        }
        catch
        {
            // Use defaults on error
        }
    }

    private async Task LoadMicroOrientationAsync()
    {
        try
        {
            var response = await _httpClient.GetAsync($"{App.BaseUrl}/api/settings/overlay_micro_orientation");
            if (response.IsSuccessStatusCode)
            {
                var json = await response.Content.ReadAsStringAsync();
                var doc = JsonDocument.Parse(json);
                if (doc.RootElement.TryGetProperty("value", out var valueElement) &&
                    valueElement.ValueKind != JsonValueKind.Null)
                {
                    var newOrientation = valueElement.GetString() ?? "horizontal";
                    if (newOrientation != _microOrientation)
                    {
                        _microOrientation = newOrientation;
                        ApplyMicroOrientation();
                    }
                }
            }
        }
        catch
        {
            // Use default on error
        }
    }

    private async Task LoadMicroFontScaleAsync()
    {
        try
        {
            var response = await _httpClient.GetAsync($"{App.BaseUrl}/api/settings/overlay_micro_font_scale");
            if (response.IsSuccessStatusCode)
            {
                var json = await response.Content.ReadAsStringAsync();
                var doc = JsonDocument.Parse(json);
                if (doc.RootElement.TryGetProperty("value", out var valueElement) &&
                    valueElement.ValueKind != JsonValueKind.Null)
                {
                    var valueStr = valueElement.GetString();
                    if (int.TryParse(valueStr, out var percent))
                    {
                        var newScale = Math.Clamp(percent / 100.0, 0.7, 1.6);
                        if (Math.Abs(newScale - _microFontScale) > 0.01)
                        {
                            _microFontScale = newScale;
                            ApplyMicroFontScale();
                        }
                    }
                }
            }
        }
        catch
        {
            // Use default on error
        }
    }

    private void ApplyMicroFontScale()
    {
        MicroStatsPanel.LayoutTransform = new ScaleTransform(_microFontScale, _microFontScale);
    }

    private void ApplyMicroOrientation()
    {
        if (_microOrientation == "vertical")
        {
            MicroStatsPanel.Orientation = Orientation.Vertical;
            // Buttons dock to top, right-aligned
            DockPanel.SetDock(MicroButtonsPanel, Dock.Top);
            MicroButtonsPanel.HorizontalAlignment = HorizontalAlignment.Right;
            MicroDockPanel.Margin = new Thickness(8, 4, 8, 6);
            // Vertical: auto-size both dimensions
            SizeToContent = SizeToContent.WidthAndHeight;
            Width = double.NaN;
            MinWidth = 100;
        }
        else
        {
            MicroStatsPanel.Orientation = Orientation.Horizontal;
            // Buttons dock to right
            DockPanel.SetDock(MicroButtonsPanel, Dock.Right);
            MicroButtonsPanel.HorizontalAlignment = HorizontalAlignment.Stretch;
            MicroDockPanel.Margin = new Thickness(8, 4, 8, 4);
            // Horizontal: auto-size both dimensions to fit all stats
            SizeToContent = SizeToContent.WidthAndHeight;
            Width = double.NaN;
            MinWidth = 100;
        }
        RebuildMicroStats();
    }

    private void ApplyMicroMode()
    {
        if (_microMode)
        {
            // Save normal mode geometry
            _savedNormalWidth = Width;
            _savedNormalHeight = Height;
            _savedNormalLeft = Left;
            _savedNormalTop = Top;

            // Switch to micro layout
            MainBorder.Visibility = Visibility.Collapsed;
            MicroBorder.Visibility = Visibility.Visible;
            ResizeMode = ResizeMode.NoResize;
            MinHeight = 0;

            // Apply orientation-specific sizing
            ApplyMicroOrientation();
        }
        else
        {
            // Switch back to normal layout
            MicroBorder.Visibility = Visibility.Collapsed;
            MainBorder.Visibility = Visibility.Visible;

            // Restore normal window properties
            SizeToContent = SizeToContent.Manual;
            ResizeMode = ResizeMode.CanResizeWithGrip;
            MinWidth = 180;
            MinHeight = _hideLoot ? CompactMinHeight : 200;

            if (!double.IsNaN(_savedNormalLeft))
            {
                Left = _savedNormalLeft;
                Top = _savedNormalTop;
            }
            Width = _savedNormalWidth;
            Height = _savedNormalHeight;
        }
    }

    private void RebuildMicroStats()
    {
        MicroStatsPanel.Children.Clear();
        _microValueBlocks.Clear();

        bool isVertical = _microOrientation == "vertical";

        for (int i = 0; i < _microStats.Count; i++)
        {
            var key = _microStats[i];
            if (!MicroStatLabels.TryGetValue(key, out var label))
                continue;

            if (isVertical)
            {
                // Vertical: each stat is a horizontal row with label left, value right
                var row = new DockPanel { Margin = new Thickness(0, 1, 0, 1) };

                var labelBlock = new TextBlock
                {
                    Text = label,
                    Foreground = new SolidColorBrush(Color.FromRgb(0xa0, 0xa0, 0xa0)),
                    FontSize = 12,
                    VerticalAlignment = VerticalAlignment.Center
                };
                DockPanel.SetDock(labelBlock, Dock.Left);
                row.Children.Add(labelBlock);

                var valueBlock = new TextBlock
                {
                    Text = "--",
                    Foreground = key == "this_run"
                        ? (Brush)FindResource("AccentGreenBrush")
                        : key == "net_worth"
                            ? (Brush)FindResource("AccentRedBrush")
                            : new SolidColorBrush(Color.FromRgb(0xea, 0xea, 0xea)),
                    FontSize = 12,
                    FontWeight = FontWeights.SemiBold,
                    HorizontalAlignment = HorizontalAlignment.Right,
                    VerticalAlignment = VerticalAlignment.Center,
                    Margin = new Thickness(12, 0, 0, 0)
                };
                _microValueBlocks[key] = valueBlock;
                row.Children.Add(valueBlock);

                MicroStatsPanel.Children.Add(row);
            }
            else
            {
                // Horizontal: inline label: value · label: value
                if (i > 0)
                {
                    var dot = new TextBlock
                    {
                        Text = "\u00B7",
                        Foreground = new SolidColorBrush(Color.FromRgb(0x60, 0x60, 0x80)),
                        FontSize = 12,
                        FontWeight = FontWeights.Bold,
                        VerticalAlignment = VerticalAlignment.Center,
                        Margin = new Thickness(6, 0, 6, 0)
                    };
                    MicroStatsPanel.Children.Add(dot);
                }

                var labelBlock = new TextBlock
                {
                    Text = label + ":",
                    Foreground = new SolidColorBrush(Color.FromRgb(0xa0, 0xa0, 0xa0)),
                    FontSize = 12,
                    VerticalAlignment = VerticalAlignment.Center,
                    Margin = new Thickness(0, 0, 4, 0)
                };
                MicroStatsPanel.Children.Add(labelBlock);

                var valueBlock = new TextBlock
                {
                    Text = "--",
                    Foreground = key == "this_run"
                        ? (Brush)FindResource("AccentGreenBrush")
                        : key == "net_worth"
                            ? (Brush)FindResource("AccentRedBrush")
                            : new SolidColorBrush(Color.FromRgb(0xea, 0xea, 0xea)),
                    FontSize = 12,
                    FontWeight = FontWeights.SemiBold,
                    VerticalAlignment = VerticalAlignment.Center
                };
                _microValueBlocks[key] = valueBlock;
                MicroStatsPanel.Children.Add(valueBlock);
            }
        }
    }

    private void UpdateMicroStats(StatsResponse? stats, ActiveRunResponse? activeRun, InventoryResponse? inventory)
    {
        foreach (var kvp in _microValueBlocks)
        {
            var key = kvp.Key;
            var block = kvp.Value;

            switch (key)
            {
                case "total_time":
                    // Use tick timer value when ticking (avoids overwriting smooth count)
                    if (_tickRunning && stats != null)
                        block.Text = FormatDurationLong(_tickBaseSeconds);
                    else
                        block.Text = stats != null ? FormatDurationLong(stats.total_duration_seconds) : "--";
                    break;
                case "value_per_hour":
                    block.Text = stats != null ? FormatNumber(stats.value_per_hour) : "--";
                    break;
                case "total_value":
                    block.Text = stats != null ? FormatNumber(stats.total_value) : "--";
                    break;
                case "net_worth":
                    block.Text = inventory != null ? Math.Round(inventory.net_worth_fe).ToString("N0") : "--";
                    break;
                case "this_run":
                    var displayRun = activeRun ?? _previousRun;
                    if (displayRun != null)
                    {
                        var runValue = displayRun.net_value_fe ?? displayRun.total_value;
                        block.Text = FormatNumber(runValue);
                        block.Foreground = runValue >= 0
                            ? (Brush)FindResource("AccentGreenBrush")
                            : (Brush)FindResource("AccentRedBrush");
                    }
                    else
                    {
                        block.Text = "--";
                    }
                    break;
                case "value_per_map":
                    block.Text = stats != null ? FormatNumber(stats.avg_value_per_run) : "--";
                    break;
                case "runs":
                    block.Text = stats != null ? stats.total_runs.ToString("N0") : "--";
                    break;
                case "avg_time":
                    if (stats != null && stats.total_runs > 0)
                    {
                        var mapDur = stats.map_duration_seconds > 0 ? stats.map_duration_seconds : stats.total_duration_seconds;
                        block.Text = FormatDuration(mapDur / stats.total_runs);
                    }
                    else
                    {
                        block.Text = "--";
                    }
                    break;
            }
        }
    }

    private void MicroHeader_MouseLeftButtonDown(object sender, MouseButtonEventArgs e)
    {
        if (e.ClickCount == 2)
        {
            Left = 100;
            Top = 100;
            _ = SavePositionAsync();
        }
        else
        {
            DragMove();
            _ = SavePositionAsync();
        }
    }

    private void TransparencyButton_Click(object sender, RoutedEventArgs e)
    {
        _isTransparent = !_isTransparent;
        ApplyTransparency();
        _ = SaveTransparencyAsync();
    }

    private void ApplyTransparency()
    {
        if (_isTransparent)
        {
            // Transparent mode - everything transparent, text with shadows
            MainBorder.Background = Brushes.Transparent;
            MainBorder.BorderBrush = Brushes.Transparent;
            HeaderBorder.Background = Brushes.Transparent;
            LootSectionBorder.Background = Brushes.Transparent;
            ZoneHeaderBorder.Background = Brushes.Transparent;
            ResizeGrip.Stroke = Brushes.Transparent;

            // Make stat boxes transparent too
            ThisRunBox.Background = Brushes.Transparent;
            ValuePerHourBox.Background = Brushes.Transparent;
            ValuePerMapBox.Background = Brushes.Transparent;
            RunsBox.Background = Brushes.Transparent;
            AvgTimeBox.Background = Brushes.Transparent;
            TotalTimeBox.Background = Brushes.Transparent;

            // Brighten text colors for visibility
            ApplyTransparentTextColors();

            // Add text shadows for visibility
            ApplyTextShadows(true);

            // Update icons
            TransparencyIcon.Text = "◑";
            TransparencyIcon.Opacity = 0.7;
            MicroTransparencyIcon.Text = "◑";
            MicroTransparencyIcon.Opacity = 0.7;

            // Micro overlay transparency
            MicroBorder.Background = Brushes.Transparent;
            MicroBorder.BorderBrush = Brushes.Transparent;
            ApplyMicroTextShadows(true);
        }
        else
        {
            // Opaque mode - show backgrounds
            MainBorder.Background = new SolidColorBrush(OpaqueMainBg);
            MainBorder.BorderBrush = new SolidColorBrush(OpaqueBorderColor);
            HeaderBorder.Background = new SolidColorBrush(OpaqueHeaderBg);
            LootSectionBorder.Background = new SolidColorBrush(OpaqueLootSectionBg);
            ZoneHeaderBorder.Background = new SolidColorBrush(OpaqueZoneHeaderBg);
            ResizeGrip.Stroke = new SolidColorBrush(OpaqueBorderColor);

            // Restore stat box backgrounds
            var statBoxBg = new SolidColorBrush(OpaqueStatBoxBg);
            ThisRunBox.Background = statBoxBg;
            ValuePerHourBox.Background = statBoxBg;
            ValuePerMapBox.Background = statBoxBg;
            RunsBox.Background = statBoxBg;
            AvgTimeBox.Background = statBoxBg;
            TotalTimeBox.Background = statBoxBg;

            // Restore normal text colors
            ApplyOpaqueTextColors();

            // Remove text shadows
            ApplyTextShadows(false);

            // Update icons
            TransparencyIcon.Text = "◐";
            TransparencyIcon.Opacity = 1.0;
            MicroTransparencyIcon.Text = "◐";
            MicroTransparencyIcon.Opacity = 1.0;

            // Micro overlay opaque
            MicroBorder.Background = new SolidColorBrush(OpaqueMainBg);
            MicroBorder.BorderBrush = new SolidColorBrush(OpaqueBorderColor);
            ApplyMicroTextShadows(false);
        }
    }

    private void ApplyTransparentTextColors()
    {
        // Pure white for labels
        var brightLabel = new SolidColorBrush(Colors.White);
        // Pure white for values
        var brightValue = new SolidColorBrush(Colors.White);
        // Bright green for accents
        var brightGreen = new SolidColorBrush(Color.FromRgb(0x6F, 0xFF, 0xCE));
        // Bright red for net worth
        var brightRed = new SolidColorBrush(Color.FromRgb(0xFF, 0x6B, 0x8A));

        // Header
        NetWorthLabel.Foreground = brightLabel;
        NetWorthText.Foreground = brightRed;

        // Stat labels
        ThisRunLabel.Foreground = brightLabel;
        ValuePerHourLabel.Foreground = brightLabel;
        ValuePerMapLabel.Foreground = brightLabel;
        RunsLabel.Foreground = brightLabel;
        AvgTimeLabel.Foreground = brightLabel;
        TotalTimeLabel.Foreground = brightLabel;

        // Stat values
        ThisRunText.Foreground = brightGreen;
        ValuePerHourText.Foreground = brightValue;
        ValuePerMapText.Foreground = brightValue;
        RunsText.Foreground = brightValue;
        AvgTimeText.Foreground = brightValue;
        TotalTimeText.Foreground = brightValue;

        // Zone text
        ZoneNameText.Foreground = brightValue;
        RunDurationText.Foreground = brightLabel;
        NoRunText.Foreground = brightLabel;
    }

    private void ApplyOpaqueTextColors()
    {
        // Original muted colors
        var mutedLabel = new SolidColorBrush(Color.FromRgb(0xa0, 0xa0, 0xa0));
        var normalValue = new SolidColorBrush(Color.FromRgb(0xea, 0xea, 0xea));
        var accentGreen = (Brush)FindResource("AccentGreenBrush");
        var accentRed = (Brush)FindResource("AccentRedBrush");

        // Header
        NetWorthLabel.Foreground = mutedLabel;
        NetWorthText.Foreground = accentRed;

        // Stat labels
        ThisRunLabel.Foreground = mutedLabel;
        ValuePerHourLabel.Foreground = mutedLabel;
        ValuePerMapLabel.Foreground = mutedLabel;
        RunsLabel.Foreground = mutedLabel;
        AvgTimeLabel.Foreground = mutedLabel;
        TotalTimeLabel.Foreground = mutedLabel;

        // Stat values
        ThisRunText.Foreground = accentGreen;
        ValuePerHourText.Foreground = normalValue;
        ValuePerMapText.Foreground = normalValue;
        RunsText.Foreground = normalValue;
        AvgTimeText.Foreground = normalValue;
        TotalTimeText.Foreground = normalValue;

        // Zone text
        ZoneNameText.Foreground = normalValue;
        RunDurationText.Foreground = mutedLabel;
        NoRunText.Foreground = mutedLabel;
    }

    private void ApplyTextShadows(bool enabled)
    {
        var effect = enabled ? TextShadow : null;

        // Header text
        NetWorthLabel.Effect = effect;
        NetWorthText.Effect = effect;

        // Stat labels and values
        ThisRunLabel.Effect = effect;
        ThisRunText.Effect = effect;
        ValuePerHourLabel.Effect = effect;
        ValuePerHourText.Effect = effect;
        ValuePerMapLabel.Effect = effect;
        ValuePerMapText.Effect = effect;
        RunsLabel.Effect = effect;
        RunsText.Effect = effect;
        AvgTimeLabel.Effect = effect;
        AvgTimeText.Effect = effect;
        TotalTimeLabel.Effect = effect;
        TotalTimeText.Effect = effect;

        // Zone/run text
        ZoneNameText.Effect = effect;
        RunDurationText.Effect = effect;
        NoRunText.Effect = effect;
    }

    private void ApplyMicroTextShadows(bool enabled)
    {
        var effect = enabled ? TextShadow : null;
        foreach (var child in MicroStatsPanel.Children)
        {
            if (child is TextBlock tb)
            {
                tb.Effect = effect;
                if (enabled)
                    tb.Foreground = new SolidColorBrush(Colors.White);
            }
            else if (child is DockPanel dp)
            {
                foreach (var inner in dp.Children)
                {
                    if (inner is TextBlock itb)
                    {
                        itb.Effect = effect;
                        if (enabled)
                            itb.Foreground = new SolidColorBrush(Colors.White);
                    }
                }
            }
        }
    }

    private async Task RefreshDataAsync()
    {
        try
        {
            var statsTask = FetchAsync<StatsResponse>("/api/runs/stats");
            var activeRunTask = FetchAsync<ActiveRunResponse?>("/api/runs/active");
            var inventoryTask = FetchAsync<InventoryResponse>("/api/inventory");

            await Task.WhenAll(statsTask, activeRunTask, inventoryTask);

            var stats = await statsTask;
            var activeRun = await activeRunTask;
            var inventory = await inventoryTask;

            UpdateStats(stats, activeRun, inventory);
            UpdateActiveRun(activeRun);
            await LoadMicroModeAsync();
            if (_microMode)
            {
                await LoadMicroStatsAsync();
                await LoadMicroOrientationAsync();
                await LoadMicroFontScaleAsync();
                UpdateMicroStats(stats, activeRun, inventory);
            }
            else
            {
                await LoadHideLootAsync();
            }

            // Safety: ensure unlock button stays visible when locked
            if (_isLocked && _unlockWindow != null && !_unlockWindow.IsVisible)
            {
                PositionUnlockButton();
                _unlockWindow.Show();
                _unlockWindow.Activate();
            }
        }
        catch (Exception ex)
        {
            System.Diagnostics.Debug.WriteLine($"Refresh error: {ex.Message}");
        }
    }

    private async Task<T?> FetchAsync<T>(string endpoint)
    {
        try
        {
            var response = await _httpClient.GetAsync($"{App.BaseUrl}{endpoint}");
            if (!response.IsSuccessStatusCode)
                return default;

            var json = await response.Content.ReadAsStringAsync();
            return JsonSerializer.Deserialize<T>(json, new JsonSerializerOptions
            {
                PropertyNameCaseInsensitive = true
            });
        }
        catch
        {
            return default;
        }
    }

    private void UpdateStats(StatsResponse? stats, ActiveRunResponse? activeRun, InventoryResponse? inventory)
    {
        // Net Worth (rounded to whole number)
        NetWorthText.Text = inventory != null
            ? Math.Round(inventory.net_worth_fe).ToString("N0")
            : "--";

        if (stats == null)
        {
            ThisRunText.Text = "--";
            ValuePerHourText.Text = "--";
            ValuePerMapText.Text = "--";
            RunsText.Text = "--";
            AvgTimeText.Text = "--";
            TotalTimeText.Text = "--";
            return;
        }

        // This Run / Previous Run value
        // Use active run if available, otherwise use previous run
        var displayRun = activeRun ?? _previousRun;
        if (displayRun != null)
        {
            var runValue = displayRun.net_value_fe ?? displayRun.total_value;
            ThisRunText.Text = FormatNumber(runValue);
            ThisRunText.Foreground = runValue >= 0
                ? (Brush)FindResource("AccentGreenBrush")
                : (Brush)FindResource("AccentRedBrush");

            // Update label based on whether it's active or previous
            ThisRunLabel.Text = activeRun != null ? "This Run" : "Previous Run";
        }
        else
        {
            ThisRunText.Text = "--";
            ThisRunLabel.Text = "This Run";
        }

        // Other stats
        ValuePerHourText.Text = FormatNumber(stats.value_per_hour);
        ValuePerMapText.Text = FormatNumber(stats.avg_value_per_run);
        RunsText.Text = stats.total_runs.ToString("N0");

        // Time calculations - always use map_duration for Avg Time
        var mapDuration = stats.map_duration_seconds > 0 ? stats.map_duration_seconds : stats.total_duration_seconds;
        if (stats.total_runs > 0 && mapDuration > 0)
        {
            var avgSeconds = mapDuration / stats.total_runs;
            AvgTimeText.Text = FormatDuration(avgSeconds);
        }
        else
        {
            AvgTimeText.Text = "--";
        }

        // Total Time - with local ticker for smooth second counting
        bool shouldTick = false;

        if (stats.realtime_tracking && !stats.realtime_paused && stats.total_duration_seconds > 0)
        {
            // Realtime mode: wall-clock time from API, tick smoothly between polls
            _tickBaseSeconds = stats.total_duration_seconds;
            shouldTick = true;
        }
        else if (!stats.realtime_tracking && activeRun != null)
        {
            // Non-realtime with active run: completed runs + active run's live duration
            _tickBaseSeconds = stats.total_duration_seconds + activeRun.duration_seconds;
            shouldTick = true;
        }

        if (shouldTick)
        {
            _tickBaseTimestamp = DateTime.UtcNow;
            _tickRunning = true;
            _tickTimer.Start();
            TotalTimeText.Text = FormatDurationLong(_tickBaseSeconds);
        }
        else
        {
            _tickRunning = false;
            _tickTimer.Stop();
            TotalTimeText.Text = FormatDurationLong(stats.total_duration_seconds);
        }

        // Show/hide pause button based on realtime tracking
        PauseButton.Visibility = stats.realtime_tracking ? Visibility.Visible : Visibility.Collapsed;
        PauseIcon.Text = stats.realtime_paused ? "\u25B6" : "\u23F8";
    }

    private void UpdateActiveRun(ActiveRunResponse? activeRun)
    {
        // Track run transitions to detect when a run ends
        if (activeRun != null)
        {
            // Active run - store it and track the ID
            _lastActiveRunId = activeRun.id;
            _previousRun = activeRun;
        }
        else if (_lastActiveRunId != null)
        {
            // Run just ended - keep _previousRun as is, clear the active ID
            _lastActiveRunId = null;
        }

        // Determine what to display
        var displayRun = activeRun ?? _previousRun;
        var isShowingPreviousRun = activeRun == null && _previousRun != null;

        if (displayRun == null)
        {
            ActiveRunPanel.Visibility = Visibility.Collapsed;
            NoRunPanel.Visibility = Visibility.Visible;
            return;
        }

        ActiveRunPanel.Visibility = Visibility.Visible;
        NoRunPanel.Visibility = Visibility.Collapsed;

        // Zone name and duration
        ZoneNameText.Text = displayRun.zone_name ?? "Unknown Zone";
        RunDurationText.Text = $"({FormatDurationShort(displayRun.duration_seconds)})";

        // Show/hide pulse indicator based on active vs previous run
        PulseIndicator.Visibility = isShowingPreviousRun ? Visibility.Collapsed : Visibility.Visible;

        // Loot list - only update if showing active run or first time showing previous
        if (!isShowingPreviousRun || LootList.Children.Count == 0)
        {
            UpdateLootList(displayRun);
        }
    }

    private void UpdateLootList(ActiveRunResponse run)
    {
        LootList.Children.Clear();

        if (run.loot == null || run.loot.Count == 0)
        {
            var noLoot = new TextBlock
            {
                Text = "No loot yet",
                Foreground = _isTransparent
                    ? new SolidColorBrush(Color.FromRgb(0xDD, 0xDD, 0xDD))
                    : (Brush)FindResource("SecondaryTextBrush"),
                FontSize = 11,
                HorizontalAlignment = HorizontalAlignment.Center,
                Margin = new Thickness(0, 10, 0, 0),
                Effect = _isTransparent ? TextShadow : null
            };
            LootList.Children.Add(noLoot);
            return;
        }

        // Sort by value descending, take top 10
        var sortedLoot = run.loot
            .OrderByDescending(l => l.total_value_fe ?? 0)
            .Take(10)
            .ToList();

        foreach (var item in sortedLoot)
        {
            var lootItem = CreateLootItemElement(item);
            LootList.Children.Add(lootItem);
        }
    }

    private Border CreateLootItemElement(LootItem item)
    {
        var isNegative = item.quantity < 0;
        var qtyPrefix = item.quantity > 0 ? "+" : "";
        var effect = _isTransparent ? TextShadow : null;

        // Colors based on transparency mode
        Brush nameBrush, qtyBrush, valueBrush;
        if (_isTransparent)
        {
            // Bright colors for transparent mode
            nameBrush = isNegative
                ? new SolidColorBrush(Color.FromRgb(0xFF, 0x6B, 0x8A))
                : new SolidColorBrush(Colors.White);
            qtyBrush = isNegative
                ? new SolidColorBrush(Color.FromRgb(0xFF, 0x6B, 0x8A))
                : new SolidColorBrush(Color.FromRgb(0xDD, 0xDD, 0xDD));
            valueBrush = isNegative
                ? new SolidColorBrush(Color.FromRgb(0xFF, 0x6B, 0x8A))
                : new SolidColorBrush(Color.FromRgb(0x6F, 0xFF, 0xCE));
        }
        else
        {
            // Normal colors for opaque mode
            nameBrush = isNegative
                ? (Brush)FindResource("AccentRedBrush")
                : (Brush)FindResource("TextBrush");
            qtyBrush = isNegative
                ? (Brush)FindResource("AccentRedBrush")
                : (Brush)FindResource("SecondaryTextBrush");
            valueBrush = isNegative
                ? (Brush)FindResource("AccentRedBrush")
                : (Brush)FindResource("AccentGreenBrush");
        }

        var grid = new Grid();
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(22) });  // Icon
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });  // Name
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });  // Qty
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(55) });  // Value

        // Icon - use high quality scaling for crisp display at small sizes
        var iconImage = new Image
        {
            Width = 18,
            Height = 18,
            Margin = new Thickness(0, 0, 4, 0)
        };
        RenderOptions.SetBitmapScalingMode(iconImage, BitmapScalingMode.HighQuality);
        LoadIconAsync(item.config_base_id, iconImage);
        Grid.SetColumn(iconImage, 0);
        grid.Children.Add(iconImage);

        // Name
        var nameText = new TextBlock
        {
            Text = item.name ?? $"Unknown ({item.config_base_id})",
            Foreground = nameBrush,
            FontSize = 11,
            TextTrimming = TextTrimming.CharacterEllipsis,
            VerticalAlignment = VerticalAlignment.Center,
            Effect = effect
        };
        Grid.SetColumn(nameText, 1);
        grid.Children.Add(nameText);

        // Quantity
        var qtyText = new TextBlock
        {
            Text = $"{qtyPrefix}{item.quantity}",
            Foreground = qtyBrush,
            FontSize = 10,
            Margin = new Thickness(6, 0, 6, 0),
            VerticalAlignment = VerticalAlignment.Center,
            HorizontalAlignment = HorizontalAlignment.Right,
            Effect = effect
        };
        Grid.SetColumn(qtyText, 2);
        grid.Children.Add(qtyText);

        // Value
        var valueText = new TextBlock
        {
            Text = item.total_value_fe.HasValue
                ? FormatNumber(item.total_value_fe.Value)
                : "--",
            Foreground = valueBrush,
            FontSize = 10,
            VerticalAlignment = VerticalAlignment.Center,
            HorizontalAlignment = HorizontalAlignment.Right,
            Effect = effect
        };
        Grid.SetColumn(valueText, 3);
        grid.Children.Add(valueText);

        var border = new Border
        {
            Child = grid,
            Padding = new Thickness(4, 3, 4, 3),
            CornerRadius = new CornerRadius(2)
        };

        // Hover effect (only in opaque mode)
        if (!_isTransparent)
        {
            border.MouseEnter += (s, e) => border.Background = new SolidColorBrush(Color.FromArgb(0x40, 0x2a, 0x2a, 0x4a));
            border.MouseLeave += (s, e) => border.Background = Brushes.Transparent;
        }

        return border;
    }

    private async void LoadIconAsync(int configBaseId, Image imageControl)
    {
        // Check cache
        if (_iconCache.TryGetValue(configBaseId, out var cached))
        {
            if (cached != null)
                imageControl.Source = cached;
            return;
        }

        // Check failed list
        if (_failedIcons.Contains(configBaseId))
            return;

        try
        {
            var response = await _httpClient.GetAsync($"{App.BaseUrl}/api/icons/{configBaseId}");
            if (!response.IsSuccessStatusCode)
            {
                _failedIcons.Add(configBaseId);
                return;
            }

            var bytes = await response.Content.ReadAsByteArrayAsync();
            var bitmap = new BitmapImage();
            bitmap.BeginInit();
            bitmap.StreamSource = new System.IO.MemoryStream(bytes);
            bitmap.CacheOption = BitmapCacheOption.OnLoad;
            // Decode at 2x display size for crisp rendering on high-DPI displays
            bitmap.DecodePixelWidth = 36;
            bitmap.DecodePixelHeight = 36;
            bitmap.EndInit();
            bitmap.Freeze();

            _iconCache[configBaseId] = bitmap;

            // Update on UI thread
            await Dispatcher.InvokeAsync(() =>
            {
                imageControl.Source = bitmap;
            });
        }
        catch
        {
            _failedIcons.Add(configBaseId);
            _iconCache[configBaseId] = null;
        }
    }

    private static string FormatNumber(double value)
    {
        return value.ToString("N2");
    }

    private static string FormatDuration(double seconds)
    {
        var ts = TimeSpan.FromSeconds(seconds);
        if (ts.TotalHours >= 1)
            return $"{(int)ts.TotalHours}h {ts.Minutes}m";
        return $"{ts.Minutes}m {ts.Seconds}s";
    }

    private static string FormatDurationShort(double seconds)
    {
        var ts = TimeSpan.FromSeconds(seconds);
        return $"{(int)ts.TotalMinutes}:{ts.Seconds:D2}";
    }

    private static string FormatDurationLong(double seconds)
    {
        var ts = TimeSpan.FromSeconds(seconds);
        if (ts.TotalHours >= 1)
            return $"{(int)ts.TotalHours}h {ts.Minutes}m {ts.Seconds}s";
        return $"{ts.Minutes}m {ts.Seconds}s";
    }
}
