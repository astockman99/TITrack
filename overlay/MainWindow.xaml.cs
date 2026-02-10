using System.Net.Http;
using System.Text.Json;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Effects;
using System.Windows.Media.Imaging;
using System.Windows.Threading;

namespace TITrackOverlay;

public partial class MainWindow : Window
{
    private readonly HttpClient _httpClient;
    private readonly DispatcherTimer _refreshTimer;
    private readonly Dictionary<int, BitmapImage?> _iconCache = new();
    private readonly HashSet<int> _failedIcons = new();

    private bool _isTransparent = false;
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

    // Track previous run to show after map ends
    private ActiveRunResponse? _previousRun = null;
    private int? _lastActiveRunId = null;

    // Local ticker for smooth Total Time counting
    private readonly DispatcherTimer _tickTimer;
    private double _tickBaseSeconds = 0;
    private DateTime _tickBaseTimestamp;
    private bool _tickRunning = false;

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
                TotalTimeText.Text = FormatDurationLong(_tickBaseSeconds + elapsed);
            }
        };

        Loaded += async (s, e) =>
        {
            await LoadFontScaleAsync();
            await LoadHideLootAsync();
            await RefreshDataAsync();
            _refreshTimer.Start();
        };

        Closed += (s, e) =>
        {
            _refreshTimer.Stop();
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
        }
        else
        {
            DragMove();
        }
    }

    private void Window_SizeChanged(object sender, SizeChangedEventArgs e)
    {
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

    private void PinButton_Click(object sender, RoutedEventArgs e)
    {
        Topmost = !Topmost;
        PinIcon.Text = Topmost ? "📌" : "📍";
        PinIcon.Opacity = Topmost ? 1.0 : 0.5;
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
        try
        {
            var content = new StringContent(
                JsonSerializer.Serialize(new { value = _fontScale.ToString(System.Globalization.CultureInfo.InvariantCulture) }),
                System.Text.Encoding.UTF8,
                "application/json");
            await _httpClient.PutAsync($"{App.BaseUrl}/api/settings/overlay_font_scale", content);
        }
        catch
        {
            // Silently ignore save errors
        }
    }

    private void TransparencyButton_Click(object sender, RoutedEventArgs e)
    {
        _isTransparent = !_isTransparent;
        ApplyTransparency();
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

            // Update icon
            TransparencyIcon.Text = "◑";
            TransparencyIcon.Opacity = 0.7;
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

            // Update icon
            TransparencyIcon.Text = "◐";
            TransparencyIcon.Opacity = 1.0;
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
            await LoadHideLootAsync();
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

        // Total Time - with local ticker for smooth realtime updates
        if (stats.realtime_tracking && !stats.realtime_paused && stats.total_duration_seconds > 0)
        {
            _tickBaseSeconds = stats.total_duration_seconds;
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
