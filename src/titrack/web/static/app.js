// TITrack Dashboard - Frontend Logic

const API_BASE = '/api';
const REFRESH_INTERVAL = 5000; // 5 seconds

let refreshTimer = null;
let lastRunsData = null;
let lastInventoryData = null;
let lastRunsHash = null;
let lastInventoryHash = null;
let lastStatsHash = null;
let lastPlayerHash = null;
const failedIcons = new Set(); // Track icons that failed to load

// Chart instances
let cumulativeValueChart = null;
let valueRateChart = null;
let lootReportChart = null;
let lastChartRealtimeMode = null; // Track chart x-axis mode

// Loot report data cache
let lastLootReportData = null;

// Cloud sync state
let cloudSyncEnabled = false;
let cloudPricesCache = {};
let sparklineHistoryCache = {}; // Cache for sparkline history data
let sparklineFetchInProgress = new Set(); // Track in-flight fetches

// Map costs state
let mapCostsEnabled = false;

// Realtime tracking state
let realtimeTrackingEnabled = false;
let realtimePaused = false;
let realtimeTickerInterval = null;
let realtimeBaseSeconds = 0;
let realtimeBaseTimestamp = 0;

// Low supply alert state
let supplyAlertThresholds = { beacons: 0, compasses: 0, resonance: 0 };
let supplyAlertedCategories = new Set();

// Update state
let updateStatus = null;
let updateCheckInterval = null;

// Inventory sorting state
let inventorySortBy = 'value';
let inventorySortOrder = 'desc';
let inventoryTabFilter = ''; // '' = all, '100' = gear, '101' = skill, '102' = commodity, '103' = misc

// Hidden items state
let hiddenItemIds = new Set();
let hideItemsModalSort = 'value';

// --- API Calls ---

async function fetchJson(endpoint) {
    try {
        const response = await fetch(`${API_BASE}${endpoint}`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error(`Error fetching ${endpoint}:`, error);
        return null;
    }
}

async function fetchStatus() {
    return fetchJson('/status');
}

async function fetchDiagnose() {
    return fetchJson('/collector/diagnose');
}

async function fetchStats() {
    return fetchJson('/runs/stats');
}

async function fetchRuns(page = 1, pageSize = 500) {
    return fetchJson(`/runs?page=${page}&page_size=${pageSize}&exclude_hubs=true`);
}

async function fetchActiveRun() {
    return fetchJson('/runs/active');
}

async function fetchInventory(sortBy = inventorySortBy, sortOrder = inventorySortOrder) {
    let url = `/inventory?sort_by=${sortBy}&sort_order=${sortOrder}`;
    if (inventoryTabFilter) {
        url += `&tab=${inventoryTabFilter}`;
    }
    return fetchJson(url);
}

async function fetchStatsHistory(hours = 24) {
    return fetchJson(`/stats/history?hours=${hours}`);
}

async function fetchPlayer() {
    return fetchJson('/player');
}

async function fetchPrices() {
    return fetchJson('/prices');
}

// --- Cloud Sync API Calls ---

async function fetchCloudStatus() {
    return fetchJson('/cloud/status');
}

async function toggleCloudSync(enabled) {
    try {
        const response = await fetch(`${API_BASE}/cloud/toggle`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled })
        });
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error('Error toggling cloud sync:', error);
        return null;
    }
}

async function triggerCloudSync() {
    try {
        const response = await fetch(`${API_BASE}/cloud/sync`, {
            method: 'POST'
        });
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error('Error triggering cloud sync:', error);
        return null;
    }
}

async function fetchCloudPrices() {
    return fetchJson('/cloud/prices');
}

// Trade tax setting functions
async function fetchTradeTaxSetting() {
    try {
        const response = await fetch(`${API_BASE}/settings/trade_tax_enabled`);
        if (!response.ok) return false;
        const data = await response.json();
        return data.value === 'true';
    } catch (error) {
        console.error('Error fetching trade tax setting:', error);
        return false;
    }
}

async function updateTradeTaxSetting(enabled) {
    try {
        const response = await fetch(`${API_BASE}/settings/trade_tax_enabled`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ value: enabled ? 'true' : 'false' })
        });
        return response.ok;
    } catch (error) {
        console.error('Error updating trade tax setting:', error);
        return false;
    }
}

async function handleTradeTaxToggle(event) {
    const enabled = event.target.checked;
    const toggle = event.target;

    // Disable toggle while processing
    toggle.disabled = true;

    const success = await updateTradeTaxSetting(enabled);

    if (success) {
        // Refresh all data to reflect new values
        await refreshAll(true);
    } else {
        // Revert toggle on failure
        toggle.checked = !enabled;
        alert('Failed to update trade tax setting');
    }

    toggle.disabled = false;
}

// Map costs setting functions
async function fetchMapCostsSetting() {
    try {
        const response = await fetch(`${API_BASE}/settings/map_costs_enabled`);
        if (!response.ok) return false;
        const data = await response.json();
        return data.value === 'true';
    } catch (error) {
        console.error('Error fetching map costs setting:', error);
        return false;
    }
}

async function updateMapCostsSetting(enabled) {
    try {
        const response = await fetch(`${API_BASE}/settings/map_costs_enabled`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ value: enabled ? 'true' : 'false' })
        });
        return response.ok;
    } catch (error) {
        console.error('Error updating map costs setting:', error);
        return false;
    }
}

async function handleMapCostsToggle(event) {
    const enabled = event.target.checked;
    const toggle = event.target;

    // Disable toggle while processing
    toggle.disabled = true;

    const success = await updateMapCostsSetting(enabled);

    if (success) {
        mapCostsEnabled = enabled;
        // Refresh all data to reflect new values
        await refreshAll(true);
    } else {
        // Revert toggle on failure
        toggle.checked = !enabled;
        alert('Failed to update map costs setting');
    }

    toggle.disabled = false;
}

// Realtime tracking setting functions
async function fetchRealtimeTrackingSetting() {
    try {
        const response = await fetch(`${API_BASE}/settings/realtime_tracking_enabled`);
        if (!response.ok) return false;
        const data = await response.json();
        return data.value === 'true';
    } catch (error) {
        console.error('Error fetching realtime tracking setting:', error);
        return false;
    }
}

async function updateRealtimeTrackingSetting(enabled) {
    try {
        const response = await fetch(`${API_BASE}/settings/realtime_tracking_enabled`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ value: enabled ? 'true' : 'false' })
        });
        return response.ok;
    } catch (error) {
        console.error('Error updating realtime tracking setting:', error);
        return false;
    }
}

async function handleRealtimeTrackingToggle(event) {
    const enabled = event.target.checked;
    const toggle = event.target;

    // Disable toggle while processing
    toggle.disabled = true;

    const success = await updateRealtimeTrackingSetting(enabled);

    if (success) {
        realtimeTrackingEnabled = enabled;
        // Refresh all data to reflect new values
        await refreshAll(true);
    } else {
        // Revert toggle on failure
        toggle.checked = !enabled;
        alert('Failed to update realtime tracking setting');
    }

    toggle.disabled = false;
}

// --- Overlay Hide Loot Setting ---

async function fetchOverlayHideLootSetting() {
    try {
        const response = await fetch(`${API_BASE}/settings/overlay_hide_loot`);
        if (!response.ok) return false;
        const data = await response.json();
        return data.value === 'true';
    } catch (error) {
        console.error('Error fetching overlay hide loot setting:', error);
        return false;
    }
}

async function updateOverlayHideLootSetting(enabled) {
    try {
        const response = await fetch(`${API_BASE}/settings/overlay_hide_loot`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ value: enabled ? 'true' : 'false' })
        });
        return response.ok;
    } catch (error) {
        console.error('Error updating overlay hide loot setting:', error);
        return false;
    }
}

async function handleOverlayHideLootToggle(event) {
    const enabled = event.target.checked;
    const toggle = event.target;
    toggle.disabled = true;

    const success = await updateOverlayHideLootSetting(enabled);
    if (!success) {
        toggle.checked = !enabled;
        alert('Failed to update overlay hide loot setting');
    }

    toggle.disabled = false;
}

// --- Low Supply Alert Functions ---

async function fetchSupplyThreshold(category) {
    try {
        const response = await fetch(`${API_BASE}/settings/low_supply_${category}_threshold`);
        if (!response.ok) return 0;
        const data = await response.json();
        return parseInt(data.value, 10) || 0;
    } catch (error) {
        return 0;
    }
}

async function updateSupplyThreshold(category, value) {
    try {
        const response = await fetch(`${API_BASE}/settings/low_supply_${category}_threshold`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ value: String(value) })
        });
        return response.ok;
    } catch (error) {
        return false;
    }
}

async function loadSupplyThresholds() {
    const [beacons, compasses, resonance] = await Promise.all([
        fetchSupplyThreshold('beacon'),
        fetchSupplyThreshold('compass'),
        fetchSupplyThreshold('resonance'),
    ]);
    supplyAlertThresholds = { beacons, compasses, resonance };
}

async function fetchConsumedSupplies() {
    try {
        const response = await fetch(`${API_BASE}/inventory/supplies`);
        if (!response.ok) return null;
        return await response.json();
    } catch (error) {
        return null;
    }
}

async function checkLowSupplyAlerts() {
    // Skip if no thresholds are set
    if (supplyAlertThresholds.beacons === 0 &&
        supplyAlertThresholds.compasses === 0 &&
        supplyAlertThresholds.resonance === 0) {
        return;
    }

    const data = await fetchConsumedSupplies();
    if (!data || !data.items) return;

    for (const item of data.items) {
        const threshold = supplyAlertThresholds[item.category] || 0;
        if (threshold <= 0) continue;

        // Use config_base_id as the alert key for per-item tracking
        const alertKey = String(item.config_base_id);

        if (item.quantity <= threshold && !supplyAlertedCategories.has(alertKey)) {
            showToast(t('toast.low_supply', { name: pickItemName(item), qty: item.quantity, threshold: threshold }), 'warning');
            supplyAlertedCategories.add(alertKey);
        } else if (item.quantity > threshold && supplyAlertedCategories.has(alertKey)) {
            // Re-arm alert when quantity goes back above threshold
            supplyAlertedCategories.delete(alertKey);
        }
    }
}

// --- Overlay Micro Mode Setting ---

const MICRO_STAT_OPTIONS = [
    { key: 'total_time', label: 'Time' },
    { key: 'value_per_hour', label: 'FE/hr' },
    { key: 'total_value', label: 'Total' },
    { key: 'net_worth', label: 'NW' },
    { key: 'this_run', label: 'Run' },
    { key: 'value_per_map', label: 'FE/Map' },
    { key: 'runs', label: 'Runs' },
    { key: 'avg_time', label: 'Avg' },
];
const DEFAULT_MICRO_STATS = ['total_time', 'value_per_hour', 'total_value'];

async function fetchOverlayMicroModeSetting() {
    try {
        const response = await fetch(`${API_BASE}/settings/overlay_micro_mode`);
        if (!response.ok) return false;
        const data = await response.json();
        return data.value === 'true';
    } catch (error) {
        console.error('Error fetching overlay micro mode setting:', error);
        return false;
    }
}

async function updateOverlayMicroModeSetting(enabled) {
    try {
        const response = await fetch(`${API_BASE}/settings/overlay_micro_mode`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ value: enabled ? 'true' : 'false' })
        });
        return response.ok;
    } catch (error) {
        console.error('Error updating overlay micro mode setting:', error);
        return false;
    }
}

async function handleOverlayMicroModeToggle(event) {
    const enabled = event.target.checked;
    const toggle = event.target;
    toggle.disabled = true;

    const success = await updateOverlayMicroModeSetting(enabled);
    if (!success) {
        toggle.checked = !enabled;
        alert('Failed to update overlay micro mode setting');
    } else {
        // Show/hide stat picker
        document.getElementById('micro-stats-picker').classList.toggle('hidden', !enabled);
        if (enabled) {
            await renderMicroStatsChips();
            const orientation = await fetchMicroOrientation();
            document.getElementById('micro-orient-horizontal').classList.toggle('active', orientation === 'horizontal');
            document.getElementById('micro-orient-vertical').classList.toggle('active', orientation === 'vertical');
        }
    }

    toggle.disabled = false;
}

async function fetchOverlayMicroStats() {
    try {
        const response = await fetch(`${API_BASE}/settings/overlay_micro_stats`);
        if (!response.ok) return DEFAULT_MICRO_STATS;
        const data = await response.json();
        if (data.value) {
            return JSON.parse(data.value);
        }
        return DEFAULT_MICRO_STATS;
    } catch (error) {
        console.error('Error fetching overlay micro stats:', error);
        return DEFAULT_MICRO_STATS;
    }
}

async function updateOverlayMicroStats(stats) {
    try {
        const response = await fetch(`${API_BASE}/settings/overlay_micro_stats`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ value: JSON.stringify(stats) })
        });
        return response.ok;
    } catch (error) {
        console.error('Error updating overlay micro stats:', error);
        return false;
    }
}

let _microChipDragKey = null;

async function renderMicroStatsChips() {
    const container = document.getElementById('micro-stats-chips');
    const selectedStats = await fetchOverlayMicroStats();

    // Show selected stats first (in saved order), then unselected
    const selectedOptions = selectedStats
        .map(key => MICRO_STAT_OPTIONS.find(o => o.key === key))
        .filter(Boolean);
    const unselectedOptions = MICRO_STAT_OPTIONS.filter(o => !selectedStats.includes(o.key));
    const orderedOptions = [...selectedOptions, ...unselectedOptions];

    container.innerHTML = '';
    orderedOptions.forEach(opt => {
        const isSelected = selectedStats.includes(opt.key);
        const chip = document.createElement('span');
        chip.className = 'micro-stat-chip' + (isSelected ? ' active' : '');
        chip.textContent = opt.label;
        chip.dataset.key = opt.key;
        chip.draggable = isSelected;

        // Click to toggle selection
        chip.addEventListener('click', async () => {
            let current = await fetchOverlayMicroStats();
            if (current.includes(opt.key)) {
                if (current.length <= 1) return;
                current = current.filter(k => k !== opt.key);
            } else {
                current.push(opt.key);
            }
            await updateOverlayMicroStats(current);
            await renderMicroStatsChips();
        });

        // Drag-to-reorder (selected chips only)
        if (isSelected) {
            chip.addEventListener('dragstart', (e) => {
                _microChipDragKey = opt.key;
                chip.classList.add('dragging');
                e.dataTransfer.effectAllowed = 'move';
            });

            chip.addEventListener('dragend', () => {
                chip.classList.remove('dragging');
                container.querySelectorAll('.drag-over').forEach(c => c.classList.remove('drag-over'));
                _microChipDragKey = null;
            });

            chip.addEventListener('dragover', (e) => {
                e.preventDefault();
                if (_microChipDragKey && _microChipDragKey !== opt.key) {
                    chip.classList.add('drag-over');
                }
            });

            chip.addEventListener('dragleave', () => {
                chip.classList.remove('drag-over');
            });

            chip.addEventListener('drop', async (e) => {
                e.preventDefault();
                chip.classList.remove('drag-over');
                if (!_microChipDragKey || _microChipDragKey === opt.key) return;

                // Reorder: remove dragged key, insert at drop position
                let current = [...selectedStats];
                const fromIdx = current.indexOf(_microChipDragKey);
                const toIdx = current.indexOf(opt.key);
                if (fromIdx === -1 || toIdx === -1) return;
                current.splice(fromIdx, 1);
                current.splice(toIdx, 0, _microChipDragKey);

                await updateOverlayMicroStats(current);
                _microChipDragKey = null;
                await renderMicroStatsChips();
            });
        }

        container.appendChild(chip);
    });
}

// --- Micro Overlay Font Scale ---

async function fetchMicroFontScale() {
    try {
        const response = await fetch(`${API_BASE}/settings/overlay_micro_font_scale`);
        if (!response.ok) return 100;
        const data = await response.json();
        return data.value ? parseInt(data.value, 10) : 100;
    } catch (error) {
        return 100;
    }
}

async function updateMicroFontScale(percent) {
    try {
        await fetch(`${API_BASE}/settings/overlay_micro_font_scale`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ value: String(percent) })
        });
    } catch (error) {
        console.error('Error updating micro font scale:', error);
    }
}

async function fetchMicroOrientation() {
    try {
        const response = await fetch(`${API_BASE}/settings/overlay_micro_orientation`);
        if (!response.ok) return 'horizontal';
        const data = await response.json();
        return data.value || 'horizontal';
    } catch (error) {
        return 'horizontal';
    }
}

async function setMicroOrientation(orientation) {
    try {
        await fetch(`${API_BASE}/settings/overlay_micro_orientation`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ value: orientation })
        });
    } catch (error) {
        console.error('Error updating micro orientation:', error);
    }
    document.getElementById('micro-orient-horizontal').classList.toggle('active', orientation === 'horizontal');
    document.getElementById('micro-orient-vertical').classList.toggle('active', orientation === 'vertical');
}

async function togglePause() {
    try {
        const response = await fetch(`${API_BASE}/runs/pause`, {
            method: 'POST'
        });
        if (!response.ok) {
            const data = await response.json();
            console.error('Pause toggle failed:', data.detail);
            return;
        }
        const data = await response.json();
        realtimePaused = data.paused;
        // Refresh to get updated stats
        await refreshAll(true);
    } catch (error) {
        console.error('Error toggling pause:', error);
    }
}

async function fetchLootReport() {
    return fetchJson('/runs/report');
}

async function postResetStats() {
    try {
        const response = await fetch(`${API_BASE}/runs/reset`, {
            method: 'POST',
        });
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error('Error resetting stats:', error);
        return null;
    }
}

// --- Rendering ---

function formatDuration(seconds) {
    if (!seconds) return '--';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}m ${secs}s`;
}

function formatNumber(num) {
    if (num === null || num === undefined) return '--';
    return num.toLocaleString();
}

function formatFEValue(value) {
    // Format FE values with 2 decimal places
    if (value === null || value === undefined) return '--';
    return value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatFE(value) {
    if (value === null || value === undefined) return '--';
    if (value > 0) {
        return `<span class="positive">+${formatNumber(value)}</span>`;
    } else if (value < 0) {
        return `<span class="negative">${formatNumber(value)}</span>`;
    }
    return formatNumber(value);
}

function formatValue(value) {
    if (value === null || value === undefined) return '--';
    const formatted = value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    if (value > 0) {
        return `<span class="positive">+${formatted}</span>`;
    } else if (value < 0) {
        return `<span class="negative">${formatted}</span>`;
    }
    return formatted;
}

function buildCostTooltip(costItems) {
    if (!costItems || costItems.length === 0) return '';
    const lines = costItems.map(item => {
        const qty = Math.abs(item.quantity);
        const value = item.total_value_fe !== null
            ? `${item.total_value_fe.toFixed(2)} FE`
            : '? FE';
        return t('misc.cost_line', { name: pickItemName(item), qty: qty, value: value });
    });
    // Escape for HTML attribute and use newline character
    return escapeAttr(lines.join('\n'));
}

function showToast(message, type = 'info') {
    // Create toast container if it doesn't exist
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        document.body.appendChild(container);
    }

    // Create toast element
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;

    container.appendChild(toast);

    // Trigger animation
    setTimeout(() => toast.classList.add('show'), 10);

    // Warning toasts stay longer (15s vs 3s)
    const duration = type === 'warning' ? 15000 : 3000;

    // Remove after delay
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

function renderStats(stats, inventory) {
    document.getElementById('net-worth').textContent = formatNumber(Math.round(inventory?.net_worth_fe || 0));
    document.getElementById('cumulative-value').textContent = formatNumber(Math.round(stats?.total_value || 0));
    document.getElementById('value-per-hour').textContent = formatNumber(Math.round(stats?.value_per_hour || 0));
    document.getElementById('value-per-map').textContent = formatNumber(Math.round(stats?.avg_value_per_run || 0));
    document.getElementById('total-runs').textContent = formatNumber(stats?.total_runs || 0);

    // Read realtime tracking state from server response
    const isRealtime = stats?.realtime_tracking || false;
    const isPaused = stats?.realtime_paused || false;
    realtimeTrackingEnabled = isRealtime;
    realtimePaused = isPaused;

    // Calculate and display average run time (always uses map duration)
    const mapDuration = stats?.map_duration_seconds || stats?.total_duration_seconds || 0;
    const avgRunTime = (stats?.total_runs > 0 && mapDuration > 0)
        ? mapDuration / stats.total_runs
        : null;
    document.getElementById('avg-run-time').textContent = formatDuration(avgRunTime);

    // Show/hide pause button
    const pauseBtn = document.getElementById('pause-btn');
    if (isRealtime) {
        pauseBtn.classList.remove('hidden');
        if (isPaused) {
            pauseBtn.textContent = '\u25B6';
            pauseBtn.title = 'Resume tracking';
            pauseBtn.classList.add('paused');
        } else {
            pauseBtn.textContent = '\u23F8';
            pauseBtn.title = 'Pause tracking';
            pauseBtn.classList.remove('paused');
        }
    } else {
        pauseBtn.classList.add('hidden');
    }

    // Update FE/Hour tooltip based on mode
    const valueHourTooltip = isRealtime
        ? 'Calculated from wall-clock time (real elapsed time minus pauses). Includes time in town, hideout, and between runs.'
        : 'Calculated from active run time only. Time spent in town, hideout, or between runs is not counted. This measures your farming efficiency, not total session time.';
    document.querySelectorAll('.info-icon').forEach(icon => {
        // Only update info icons that are about FE/Hour (in stat header and chart)
        if (icon.closest('.stat-label') || icon.closest('h2')) {
            icon.title = valueHourTooltip;
        }
    });

    // Display total time - with local ticker for smooth realtime updates
    clearRealtimeTicker();
    if (isRealtime && !isPaused && stats?.total_duration_seconds > 0) {
        // Start a local ticker that increments the displayed time smoothly
        realtimeBaseSeconds = stats.total_duration_seconds;
        realtimeBaseTimestamp = Date.now();
        document.getElementById('total-time').textContent = formatDurationLong(realtimeBaseSeconds);
        realtimeTickerInterval = setInterval(() => {
            const elapsed = (Date.now() - realtimeBaseTimestamp) / 1000;
            document.getElementById('total-time').textContent = formatDurationLong(realtimeBaseSeconds + elapsed);
        }, 1000);
    } else {
        document.getElementById('total-time').textContent = formatDurationLong(stats?.total_duration_seconds);
    }
}

function clearRealtimeTicker() {
    if (realtimeTickerInterval) {
        clearInterval(realtimeTickerInterval);
        realtimeTickerInterval = null;
    }
}

function renderRuns(data, forceRender = false) {
    const newHash = simpleHash(data?.runs?.map(r => ({ id: r.id, val: r.total_value, dur: r.duration_seconds, cost: r.map_cost_fe, ign: r.is_ignored, igni: r.ignored_items?.length })));
    if (!forceRender && newHash === lastRunsHash) {
        return; // No change, skip re-render
    }
    lastRunsHash = newHash;

    const tbody = document.getElementById('runs-body');

    if (!data || !data.runs || data.runs.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="loading">No runs recorded yet</td></tr>';
        return;
    }

    tbody.innerHTML = data.runs.map(run => {
        const nightmareClass = run.is_nightmare ? ' nightmare' : '';
        const ignoredClass = run.is_ignored ? ' ignored' : '';
        const consolidatedInfo = run.consolidated_run_ids ? ` (${run.consolidated_run_ids.length} segments)` : '';

        // Show net value if costs are enabled and there are costs
        let valueDisplay;
        if (run.net_value_fe !== null && run.net_value_fe !== undefined && run.map_cost_fe > 0) {
            const warningIcon = run.map_cost_has_unpriced ? ' <span class="cost-warning" title="Some costs have unknown prices">⚠</span>' : '';
            valueDisplay = `${formatValue(run.net_value_fe)}${warningIcon}`;
        } else {
            valueDisplay = formatValue(run.total_value);
        }

        const ignoredItemsIcon = (run.ignored_items && run.ignored_items.length > 0 && !run.is_ignored)
            ? ' <span class="ignored-items-icon" title="This run has ignored items">&#x1F6AB;</span>'
            : '';

        return `
            <tr class="${nightmareClass}${ignoredClass}">
                <td class="zone-name" title="${run.zone_signature}${consolidatedInfo}">${escapeHtml(tZone(run.zone_name))}</td>
                <td class="duration">${formatDuration(run.duration_seconds)}</td>
                <td>${valueDisplay}</td>
                <td>
                    <button class="expand-btn" onclick="showRunDetails(${run.id})">
                        Details
                    </button>${ignoredItemsIcon}
                </td>
            </tr>
        `;
    }).join('');
}

let lastActiveRunHash = null;

let lastActiveRunId = null;

function renderActiveRun(data, forceRender = false) {
    const panel = document.getElementById('active-run-panel');
    const zoneEl = document.getElementById('active-run-zone');
    const durationEl = document.getElementById('active-run-duration');
    const valueEl = document.getElementById('active-run-value');
    const lootEl = document.getElementById('active-run-loot');

    // No active run - hide and clear panel
    if (!data) {
        panel.classList.add('hidden');
        lastActiveRunHash = null;
        lastActiveRunId = null;
        // Clear content so old data doesn't flash when new run starts
        zoneEl.textContent = '--';
        valueEl.textContent = '0';
        lootEl.innerHTML = '';
        return;
    }

    // Check if data changed (include cost data in hash)
    const newHash = simpleHash({
        id: data.id,
        val: data.total_value,
        dur: data.duration_seconds,
        loot: data.loot?.length,
        cost: data.map_cost_fe
    });
    if (!forceRender && newHash === lastActiveRunHash) {
        // Just update duration (always changes)
        durationEl.textContent = `(${formatDuration(data.duration_seconds)})`;
        return;
    }
    lastActiveRunHash = newHash;
    lastActiveRunId = data.id;

    // Show panel and update content
    panel.classList.remove('hidden');
    zoneEl.textContent = tZone(data.zone_name);
    durationEl.textContent = `(${formatDuration(data.duration_seconds)})`;

    // Show value with cost info if map costs are enabled
    if (data.map_cost_fe !== null && data.map_cost_fe !== undefined && data.map_cost_fe > 0) {
        const netValue = data.net_value_fe !== null ? data.net_value_fe : data.total_value;
        const warningIcon = data.map_cost_has_unpriced ? ' <span class="cost-warning" title="Some costs have unknown prices">⚠</span>' : '';
        const costTooltip = buildCostTooltip(data.map_cost_items);
        valueEl.innerHTML = `${formatValue(netValue)} <span class="cost-info">(gross: ${formatNumber(Math.round(data.total_value))}, cost: <span class="cost-hover" title="${costTooltip}">-${formatNumber(Math.round(data.map_cost_fe))}</span>${warningIcon})</span>`;
    } else {
        valueEl.innerHTML = formatValue(data.total_value);
    }

    // Render loot items - sorted by value descending
    if (!data.loot || data.loot.length === 0) {
        lootEl.innerHTML = '<span class="no-loot">No drops yet...</span>';
    } else {
        // Sort by total_value_fe descending (items without value go to end)
        const sortedLoot = [...data.loot].sort((a, b) => {
            const aVal = a.total_value_fe || 0;
            const bVal = b.total_value_fe || 0;
            return bVal - aVal;
        });

        lootEl.innerHTML = sortedLoot.map(item => {
            const isNegative = item.quantity < 0;
            const negativeClass = isNegative ? ' negative' : '';
            const qtyPrefix = item.quantity > 0 ? '+' : '';
            const valueText = item.total_value_fe ? formatValue(item.total_value_fe) : '--';
            const iconHtml = getIconHtml(item.config_base_id, 'loot-icon');

            return `
                <div class="loot-item${negativeClass}">
                    ${iconHtml}
                    <span class="loot-name">${escapeHtml(pickItemName(item))}</span>
                    <span class="loot-qty">${qtyPrefix}${item.quantity}</span>
                    <span class="loot-value">${valueText}</span>
                </div>
            `;
        }).join('');
    }
}

function renderInventory(data, forceRender = false) {
    const newHash = simpleHash(data?.items?.map(i => ({ id: i.config_base_id, qty: i.quantity })));
    if (!forceRender && newHash === lastInventoryHash) {
        return; // No change, skip re-render
    }
    lastInventoryHash = newHash;

    const tbody = document.getElementById('inventory-body');
    const sparklineHeader = document.getElementById('sparkline-header');

    // Show/hide sparkline column based on cloud sync status
    if (cloudSyncEnabled && Object.keys(cloudPricesCache).length > 0) {
        sparklineHeader.classList.remove('hidden');
    } else {
        sparklineHeader.classList.add('hidden');
    }

    const colSpan = cloudSyncEnabled ? 4 : 3;

    if (!data || !data.items || data.items.length === 0) {
        tbody.innerHTML = `<tr><td colspan="${colSpan}" class="loading">No items in inventory</td></tr>`;
        return;
    }

    tbody.innerHTML = data.items.slice(0, 20).map(item => {
        const isFE = item.config_base_id === 100300;
        const iconHtml = getIconHtml(item.config_base_id, 'item-icon');

        // Check if we have cloud price for this item
        const cloudPrice = cloudPricesCache[item.config_base_id];
        // Show cloud indicator only if we have 3+ contributors (community validated)
        const hasValidatedCloudPrice = cloudPrice && cloudPrice.unique_devices >= 3;
        // Show sparkline for any cloud price (even single contributor for personal tracking)
        const hasAnyCloudPrice = !!cloudPrice;

        // Cloud price indicator (only for validated prices)
        const cloudIndicator = hasValidatedCloudPrice
            ? `<span class="cloud-price-indicator" title="Community price (${cloudPrice.unique_devices} contributors)"></span>`
            : '';

        // Sparkline cell (only if cloud sync enabled)
        // Note: Canvas needs explicit width/height attributes (not just CSS) to render correctly
        const sparklineCell = cloudSyncEnabled
            ? `<td class="sparkline-cell" onclick="window.open('https://titrack.ninja/item/${item.config_base_id}', '_blank')">
                ${hasAnyCloudPrice ? '<canvas class="sparkline" data-config-id="' + item.config_base_id + '" width="60" height="24"></canvas>' : '<div class="sparkline-placeholder"></div>'}
               </td>`
            : '';

        return `
            <tr>
                <td>
                    <div class="item-row">
                        ${iconHtml}
                        <a href="${pickItemUrl(item) || ('https://titrack.ninja/item/' + item.config_base_id)}" target="_blank" class="item-name item-name-link ${isFE ? 'fe' : ''}">${escapeHtml(pickItemName(item))}${cloudIndicator}</a>
                    </div>
                </td>
                <td>${formatNumber(item.quantity)}</td>
                <td>${item.total_value_fe ? formatFEValue(item.total_value_fe) : '--'}</td>
                ${sparklineCell}
            </tr>
        `;
    }).join('');

    // Render sparklines after DOM update
    // Use setTimeout to ensure DOM is fully ready (requestAnimationFrame can fire too early)
    if (cloudSyncEnabled) {
        setTimeout(() => renderSparklines(), 50);
    }
}

function renderSparklines() {
    const sparklines = document.querySelectorAll('.sparkline[data-config-id]');
    sparklines.forEach(canvas => {
        const configId = parseInt(canvas.dataset.configId);
        const cloudPrice = cloudPricesCache[configId];
        if (!cloudPrice) return;

        // Check if we have cached history
        if (sparklineHistoryCache[configId] !== undefined) {
            // Render with cached data (may be empty array if no history)
            renderSparklineGraph(canvas, sparklineHistoryCache[configId]);
        } else if (!sparklineFetchInProgress.has(configId)) {
            // Show loading state and fetch history
            renderSparklineLoading(canvas);
            fetchSparklineHistory(configId);
        }
    });
}

async function fetchSparklineHistory(configId) {
    if (sparklineFetchInProgress.has(configId)) return;
    sparklineFetchInProgress.add(configId);

    try {
        const response = await fetch(`${API_BASE}/cloud/prices/${configId}/history`);
        if (response.ok) {
            const data = await response.json();
            sparklineHistoryCache[configId] = data.history || [];
        } else {
            sparklineHistoryCache[configId] = [];
        }
    } catch (error) {
        console.error(`Failed to fetch sparkline history for ${configId}:`, error);
        sparklineHistoryCache[configId] = [];
    } finally {
        sparklineFetchInProgress.delete(configId);
        // Re-render this specific sparkline
        const canvas = document.querySelector(`.sparkline[data-config-id="${configId}"]`);
        if (canvas) {
            renderSparklineGraph(canvas, sparklineHistoryCache[configId]);
        }
    }
}

function renderSparklineLoading(canvas) {
    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;

    ctx.clearRect(0, 0, width, height);

    // Draw three dots to indicate loading
    const midY = height / 2;
    ctx.fillStyle = '#4ecca3';
    for (let i = 0; i < 3; i++) {
        ctx.beginPath();
        ctx.arc(width / 2 - 10 + i * 10, midY, 2, 0, Math.PI * 2);
        ctx.fill();
    }
}

function renderSparklineGraph(canvas, history) {
    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;
    const padding = 2;

    ctx.clearRect(0, 0, width, height);

    // If no history or only one point, show a simple indicator
    if (!history || history.length < 2) {
        renderSparklinePlaceholder(canvas);
        return;
    }

    // Extract price values
    const prices = history.map(h => h.price_fe_median);
    const minPrice = Math.min(...prices);
    const maxPrice = Math.max(...prices);
    const priceRange = maxPrice - minPrice;

    // Determine trend (up, down, or flat)
    const firstPrice = prices[0];
    const lastPrice = prices[prices.length - 1];
    const trend = lastPrice > firstPrice * 1.01 ? 'up' :
                  lastPrice < firstPrice * 0.99 ? 'down' : 'flat';

    // Choose color based on trend
    const colors = {
        up: '#4ecca3',    // Green
        down: '#e94560',  // Red
        flat: '#7f8c8d'   // Gray
    };
    const color = colors[trend];

    // Calculate points
    const points = prices.map((price, i) => {
        const x = padding + (i / (prices.length - 1)) * (width - padding * 2);
        // If price range is 0 (all same price), draw flat line in middle
        const y = priceRange === 0
            ? height / 2
            : padding + (1 - (price - minPrice) / priceRange) * (height - padding * 2);
        return { x, y };
    });

    // Draw fill gradient
    const gradient = ctx.createLinearGradient(0, 0, 0, height);
    gradient.addColorStop(0, color + '40'); // 25% opacity at top
    gradient.addColorStop(1, color + '00'); // 0% opacity at bottom

    ctx.beginPath();
    ctx.moveTo(points[0].x, height);
    points.forEach(p => ctx.lineTo(p.x, p.y));
    ctx.lineTo(points[points.length - 1].x, height);
    ctx.closePath();
    ctx.fillStyle = gradient;
    ctx.fill();

    // Draw line
    ctx.beginPath();
    ctx.moveTo(points[0].x, points[0].y);
    for (let i = 1; i < points.length; i++) {
        ctx.lineTo(points[i].x, points[i].y);
    }
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.5;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.stroke();

    // Draw end dot
    const lastPoint = points[points.length - 1];
    ctx.beginPath();
    ctx.arc(lastPoint.x, lastPoint.y, 2, 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.fill();
}

function renderSparklinePlaceholder(canvas) {
    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;
    const midY = height / 2;

    ctx.clearRect(0, 0, width, height);

    // Draw a visible dashed line to indicate "no trend data"
    ctx.strokeStyle = '#7f8c8d';  // More visible gray
    ctx.lineWidth = 1.5;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(4, midY);
    ctx.lineTo(width - 8, midY);
    ctx.stroke();
    ctx.setLineDash([]);

    // Draw a visible dot at the end
    ctx.fillStyle = '#7f8c8d';
    ctx.beginPath();
    ctx.arc(width - 6, midY, 3, 0, Math.PI * 2);
    ctx.fill();
}

function renderStatus(status) {
    const indicator = document.getElementById('status-indicator');
    const collectorStatus = document.getElementById('collector-status');

    if (status?.collector_running) {
        indicator.classList.add('active');
        collectorStatus.textContent = t('footer.collector', { state: t('footer.collector_running') });
    } else {
        indicator.classList.remove('active');
        collectorStatus.textContent = t('footer.collector', { state: t('footer.collector_stopped') });
    }

    // Show/hide awaiting player summary (inline header).
    // The detailed diagnostics live in the Character Not Detected modal,
    // which the user opens from the "See details" link here.
    const awaitingMessage = document.getElementById('awaiting-player-message');
    if (awaitingMessage) {
        if (status?.awaiting_player && !status?.log_path_missing) {
            awaitingMessage.classList.remove('hidden');
            refreshAwaitingDiagnostic();
        } else {
            awaitingMessage.classList.add('hidden');
        }
    }

    // Show log path configuration modal if log file not found
    if (status?.log_path_missing) {
        showLogPathModal();
    }
}

let _awaitingDiagnosticInflight = false;
let _lastDiagnostic = null;
async function refreshAwaitingDiagnostic() {
    if (_awaitingDiagnosticInflight) return;
    _awaitingDiagnosticInflight = true;
    try {
        const diag = await fetchDiagnose();
        if (diag) {
            _lastDiagnostic = diag;
            renderAwaitingSummary(diag);
            // Refresh modal content if it's open
            if (!document.getElementById('no-character-modal').classList.contains('hidden')) {
                renderNoCharacterDiagnostic(diag);
            }
        }
    } finally {
        _awaitingDiagnosticInflight = false;
    }
}

function _formatAgo(seconds) {
    if (seconds == null) return 'unknown';
    if (seconds < 60) return `${seconds}s ago`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)} min ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    return `${Math.floor(seconds / 86400)}d ago`;
}

function _escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, c => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    })[c]);
}

/**
 * Pure function: given a diagnose payload, pick the branch and return
 * {kind, summary, message, actionHtml} for rendering into either the
 * inline summary or the modal.
 *   kind: short label ("missing" | "not-ti" | "newer" | "stale" | "partial" | "active")
 *   summary: short single-line text for the inline header
 *   message: rich HTML for the modal body
 *   actionHtml: button(s) HTML (empty string if no action)
 */
function _pickAwaitingDiagnostic(diag) {
    const STALE_SECONDS = 300;
    const logAge = diag.log_seconds_since_modified;
    const logIsStale = logAge != null && logAge > STALE_SECONDS;

    // A candidate is "better" if it was modified in the last 5 min AND
    // (either the current log is stale or the candidate is meaningfully newer).
    const newerCandidate = (diag.other_candidates || []).find(c => {
        if (c.seconds_since_modified == null) return false;
        if (c.seconds_since_modified > STALE_SECONDS) return false;
        if (logIsStale) return true;
        if (logAge != null && c.seconds_since_modified < logAge - 30) return true;
        return logAge == null;
    });

    if (!diag.log_path_configured || !diag.log_exists) {
        const path = diag.log_path ? ` (<code>${_escapeHtml(diag.log_path)}</code>)` : '';
        return {
            kind: 'missing',
            summary: 'Log file not found',
            message: `Log file not found${path}. Tell TITrack where Torchlight Infinite is installed.`,
            actionHtml: `<button onclick="openSettingsModal()" class="awaiting-btn primary">Configure log path</button>`,
        };
    }
    if (diag.looks_like_ti_log === false) {
        return {
            kind: 'not-ti',
            summary: 'Log file doesn’t look like a Torchlight log',
            message: `This file doesn't look like a Torchlight Infinite log (<code>${_escapeHtml(diag.log_path)}</code>). Point TITrack at the correct game install.`,
            actionHtml: `<button onclick="openSettingsModal()" class="awaiting-btn primary">Configure log path</button>`,
        };
    }
    if (newerCandidate) {
        const ago = _formatAgo(newerCandidate.seconds_since_modified);
        const currentAgo = _formatAgo(logAge);
        return {
            kind: 'newer',
            summary: 'Newer log detected elsewhere — may be watching the wrong client',
            message: `The watched log was last updated ${currentAgo}, but a newer log exists at <code>${_escapeHtml(newerCandidate.path)}</code> (updated ${ago}). You may have two game clients installed — try switching.`,
            actionHtml: `<button onclick="openSettingsModal(${JSON.stringify(newerCandidate.path)})" class="awaiting-btn primary">Switch to newer log</button>`,
        };
    }
    if (logIsStale) {
        const ago = _formatAgo(logAge);
        return {
            kind: 'stale',
            summary: `Log was last updated ${ago}`,
            message: `The log was last updated ${ago}. If you're in-game right now, Torchlight Infinite may not be writing to this log — verify logging is enabled (see general troubleshooting below).`,
            actionHtml: `<button onclick="openSettingsModal()" class="awaiting-btn">Change log path</button>`,
        };
    }
    if (diag.player_lines_seen && !diag.player_detected) {
        return {
            kind: 'partial',
            summary: 'Saw partial character data — try relogging from Select Character',
            message: `Saw partial character data in the log but couldn't match a full character yet. Exit to the <strong>Select Character</strong> screen and log back in — that forces the game to re-send your full character data. Full steps are below.`,
            actionHtml: '',
        };
    }
    return {
        kind: 'active',
        summary: 'Log active but no character data yet — Enable Log then relog from Select Character',
        message: `The log file is being written to, but Torchlight hasn't logged your character details yet. Most likely <strong>Enable Log</strong> is off in-game, or it was off when you last logged in. Turn it on in the in-game Settings menu, exit to the <strong>Select Character</strong> screen, then log back in. Full steps are below.`,
        actionHtml: '',
    };
}

function renderAwaitingSummary(diag) {
    const summaryEl = document.getElementById('awaiting-player-summary');
    if (!summaryEl) return;
    const pick = _pickAwaitingDiagnostic(diag);
    summaryEl.textContent = pick.summary;
}

function renderNoCharacterDiagnostic(diag) {
    const body = document.getElementById('no-character-diagnostic-body');
    const actions = document.getElementById('no-character-diagnostic-actions');
    if (!body || !actions) return;
    const pick = _pickAwaitingDiagnostic(diag);
    body.innerHTML = pick.message;
    actions.innerHTML = pick.actionHtml;
    actions.classList.toggle('hidden', !pick.actionHtml);
}

function renderPlayer(player) {
    const playerInfo = document.getElementById('player-info');
    const playerName = document.getElementById('player-name');
    const playerDetails = document.getElementById('player-details');

    if (player) {
        playerName.textContent = player.name;
        playerDetails.textContent = pickSeasonName(player);
        playerInfo.classList.remove('hidden');
    } else {
        playerInfo.classList.add('hidden');
    }
}

// --- Cloud Sync UI ---

function renderCloudStatus(status) {
    const toggle = document.getElementById('cloud-sync-toggle');
    const indicator = document.getElementById('cloud-sync-status');

    if (!status) {
        toggle.checked = false;
        toggle.disabled = true;
        indicator.className = 'cloud-status-indicator';
        indicator.title = 'Cloud sync not available';
        return;
    }

    // Enable toggle if cloud is available
    toggle.disabled = !status.cloud_available;
    toggle.checked = status.enabled;
    cloudSyncEnabled = status.enabled;

    // Update indicator
    indicator.className = 'cloud-status-indicator';
    if (status.status === 'connected') {
        indicator.classList.add('connected');
        indicator.title = 'Cloud sync connected';
    } else if (status.status === 'syncing') {
        indicator.classList.add('syncing');
        indicator.title = 'Syncing...';
    } else if (status.status === 'error') {
        indicator.classList.add('error');
        indicator.title = status.last_error || 'Cloud sync error';
    } else if (status.status === 'offline') {
        indicator.classList.add('offline');
        indicator.title = 'Cloud sync offline';
    } else {
        indicator.title = 'Cloud sync disabled';
    }

    // Add queue info to title
    if (status.queue_pending > 0) {
        indicator.title += ` (${status.queue_pending} pending)`;
    }
}

async function handleCloudSyncToggle(event) {
    const enabled = event.target.checked;
    const toggle = event.target;

    // Disable toggle while processing
    toggle.disabled = true;

    const result = await toggleCloudSync(enabled);

    if (result) {
        cloudSyncEnabled = result.enabled;
        toggle.checked = result.enabled;

        if (!result.success && result.error) {
            alert(`Cloud sync error: ${result.error}`);
        }

        // Refresh cloud status
        const status = await fetchCloudStatus();
        renderCloudStatus(status);

        // Load cloud prices if newly enabled
        if (result.enabled) {
            await loadCloudPrices();
        }
    } else {
        // Revert on error
        toggle.checked = !enabled;
    }

    toggle.disabled = false;
}

async function loadCloudPrices() {
    if (!cloudSyncEnabled) return;

    const data = await fetchCloudPrices();
    if (data && data.prices) {
        cloudPricesCache = {};
        // Clear sparkline history cache so fresh data is fetched
        sparklineHistoryCache = {};
        sparklineFetchInProgress.clear();
        for (const price of data.prices) {
            cloudPricesCache[price.config_base_id] = price;
        }
    }
}

// --- No Character Modal ---

// Tracks whether the auto-show on startup has fired. The modal can still be
// reopened manually via the "See details" link in the header after dismiss.
let noCharacterModalShown = false;

function showNoCharacterModal(options) {
    // `auto`: only open once per session (used by startup). Manual opens from
    // the "See details" link always open the modal.
    const auto = !!(options && options.auto);
    if (auto && noCharacterModalShown) return;
    noCharacterModalShown = true;
    document.getElementById('no-character-modal').classList.remove('hidden');

    // Paint immediately from the last known diagnostic so the modal doesn't
    // flash the placeholder, then refresh in the background for the latest state.
    if (_lastDiagnostic) {
        renderNoCharacterDiagnostic(_lastDiagnostic);
    }
    refreshAwaitingDiagnostic();
}

function closeNoCharacterModal() {
    document.getElementById('no-character-modal').classList.add('hidden');
}

// Close no-character modal on outside click
document.addEventListener('click', (e) => {
    if (e.target.id === 'no-character-modal') {
        closeNoCharacterModal();
    }
});

// --- Settings Modal ---

let settingsModalShown = false;
let validatedLogPath = null;

async function openSettingsModal(prefillLogPath) {
    const modal = document.getElementById('settings-modal');
    const currentPathEl = document.getElementById('current-log-path');
    const inputEl = document.getElementById('log-directory-input');
    const statusEl = document.getElementById('log-path-status');
    const saveBtn = document.getElementById('save-log-dir-btn');
    const tradeTaxToggle = document.getElementById('settings-trade-tax');
    const mapCostsToggle = document.getElementById('settings-map-costs');

    // Reset log path state
    statusEl.textContent = '';
    statusEl.className = 'log-path-status';
    saveBtn.disabled = true;
    saveBtn.textContent = 'Save & Restart';
    validatedLogPath = null;

    const realtimeToggle = document.getElementById('settings-realtime-tracking');
    const overlayHideLootToggle = document.getElementById('settings-overlay-hide-loot');

    // Load current settings
    tradeTaxToggle.checked = await fetchTradeTaxSetting();
    mapCostsToggle.checked = await fetchMapCostsSetting();
    mapCostsEnabled = mapCostsToggle.checked;
    realtimeToggle.checked = await fetchRealtimeTrackingSetting();
    realtimeTrackingEnabled = realtimeToggle.checked;
    overlayHideLootToggle.checked = await fetchOverlayHideLootSetting();

    const overlayMicroModeToggle = document.getElementById('settings-overlay-micro-mode');
    overlayMicroModeToggle.checked = await fetchOverlayMicroModeSetting();
    document.getElementById('micro-stats-picker').classList.toggle('hidden', !overlayMicroModeToggle.checked);
    // Always render chips, orientation, and font scale so they're ready when toggled on
    await renderMicroStatsChips();
    const microOrientation = await fetchMicroOrientation();
    document.getElementById('micro-orient-horizontal').classList.toggle('active', microOrientation === 'horizontal');
    document.getElementById('micro-orient-vertical').classList.toggle('active', microOrientation === 'vertical');
    const microFontScale = await fetchMicroFontScale();
    const fontSlider = document.getElementById('micro-font-scale-slider');
    fontSlider.value = microFontScale;
    document.getElementById('micro-font-scale-value').textContent = microFontScale + '%';

    // Load supply alert thresholds
    document.getElementById('settings-supply-beacon').value = supplyAlertThresholds.beacons;
    document.getElementById('settings-supply-compass').value = supplyAlertThresholds.compasses;
    document.getElementById('settings-supply-resonance').value = supplyAlertThresholds.resonance;

    // Load current language
    try {
        const langSel = document.getElementById('settings-language');
        if (langSel) {
            langSel.value = (typeof i18n !== 'undefined' && i18n.getLang()) || 'en';
        }
    } catch (_) { /* ignore */ }

    // Fetch current log path from status
    try {
        const status = await fetchStatus();
        if (status && status.log_path) {
            currentPathEl.textContent = status.log_path;
            // Extract game directory from full path
            const pathParts = status.log_path.split('\\');
            if (pathParts.length > 5) {
                const gameDir = pathParts.slice(0, -5).join('\\');
                inputEl.value = gameDir;
            }
        } else {
            currentPathEl.textContent = 'Not found - please configure below';
            inputEl.value = '';
        }
    } catch (error) {
        currentPathEl.textContent = 'Unable to fetch current path';
    }

    // If a prefill path was passed (e.g. "Switch to newer log" from the
    // character-detection panel), override the input and auto-validate so
    // the user can just click Save.
    if (prefillLogPath) {
        inputEl.value = prefillLogPath;
        try { validateLogDirectory(); } catch (_) {}
    }

    modal.classList.remove('hidden');
}

function closeSettingsModal() {
    document.getElementById('settings-modal').classList.add('hidden');
}

// Show settings modal when log path missing (called from renderStatus)
function showLogPathModal() {
    // Only show once per session
    if (settingsModalShown) return;
    settingsModalShown = true;
    openSettingsModal();
}

// Close settings modal on outside click
document.addEventListener('click', (e) => {
    if (e.target.id === 'settings-modal') {
        closeSettingsModal();
    }
});

// Browse for game folder using native dialog (only works in pywebview window mode)
async function browseForGameFolder() {
    // Check if pywebview API is available
    if (window.pywebview && window.pywebview.api) {
        try {
            const path = await window.pywebview.api.browse_folder();
            if (path) {
                document.getElementById('log-directory-input').value = path;
                // Automatically validate after selection
                validateLogDirectory();
            }
        } catch (e) {
            console.error('Browse dialog error:', e);
        }
    } else {
        alert('Browse is only available in native window mode.');
    }
}

// Initialize browse button visibility (show only if pywebview is available)
function initBrowseButton() {
    const browseBtn = document.getElementById('browse-folder-btn');
    if (browseBtn) {
        // pywebview.api may not be immediately available, check with a small delay
        setTimeout(() => {
            if (window.pywebview && window.pywebview.api) {
                browseBtn.style.display = 'inline-block';
            }
        }, 500);
    }
}

// Initialize overlay button visibility (show only if pywebview is available)
function initOverlayButton() {
    const overlayBtn = document.getElementById('overlay-btn');
    if (overlayBtn) {
        // pywebview.api may not be immediately available, check with a small delay
        setTimeout(() => {
            if (window.pywebview && window.pywebview.api && window.pywebview.api.launch_overlay) {
                overlayBtn.classList.remove('hidden');
            }
        }, 500);
    }
}

// Launch the mini overlay window
async function launchOverlay() {
    if (window.pywebview && window.pywebview.api && window.pywebview.api.launch_overlay) {
        try {
            const result = await window.pywebview.api.launch_overlay();
            if (result) {
                showToast('Overlay opened', 'success');
            } else {
                showToast('Could not open overlay', 'error');
            }
        } catch (e) {
            console.error('Error launching overlay:', e);
            showToast('Failed to launch overlay', 'error');
        }
    } else {
        showToast('Overlay is only available in native window mode', 'info');
    }
}

// Call on page load
document.addEventListener('DOMContentLoaded', initBrowseButton);
document.addEventListener('DOMContentLoaded', initOverlayButton);

async function validateLogDirectory() {
    const input = document.getElementById('log-directory-input');
    const status = document.getElementById('log-path-status');
    const saveBtn = document.getElementById('save-log-dir-btn');
    const path = input.value.trim();

    if (!path) {
        status.textContent = 'Please enter a path';
        status.className = 'log-path-status error';
        saveBtn.disabled = true;
        return;
    }

    status.textContent = 'Validating...';
    status.className = 'log-path-status validating';
    saveBtn.disabled = true;

    try {
        const response = await fetch(`${API_BASE}/settings/log-directory/validate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path })
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const result = await response.json();

        if (result.valid) {
            status.textContent = `Found: ${result.log_path}`;
            status.className = 'log-path-status success';
            validatedLogPath = path;
            saveBtn.disabled = false;
        } else {
            status.textContent = result.error || 'Log file not found at this location';
            status.className = 'log-path-status error';
            validatedLogPath = null;
            saveBtn.disabled = true;
        }
    } catch (error) {
        console.error('Error validating log directory:', error);
        status.textContent = 'Error validating path. Please try again.';
        status.className = 'log-path-status error';
        validatedLogPath = null;
        saveBtn.disabled = true;
    }
}

async function saveLogDirectory() {
    if (!validatedLogPath) return;

    const saveBtn = document.getElementById('save-log-dir-btn');
    const status = document.getElementById('log-path-status');

    saveBtn.disabled = true;
    saveBtn.textContent = 'Saving...';

    try {
        const response = await fetch(`${API_BASE}/settings/log_directory`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ value: validatedLogPath })
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        status.textContent = 'Saved! Please restart TITrack for changes to take effect.';
        status.className = 'log-path-status success';
        saveBtn.textContent = 'Saved - Restart Required';

        // Show a more prominent message
        alert('Log directory saved! Please restart TITrack for the changes to take effect.');

    } catch (error) {
        console.error('Error saving log directory:', error);
        status.textContent = 'Error saving. Please try again.';
        status.className = 'log-path-status error';
        saveBtn.disabled = false;
        saveBtn.textContent = 'Save & Restart';
    }
}

// Chart configuration - base options shared by both modes
function getChartOptions(realtimeMode) {
    const xScale = realtimeMode ? {
        type: 'time',
        time: {
            displayFormats: {
                hour: 'HH:mm',
                minute: 'HH:mm',
            },
        },
        grid: {
            color: 'rgba(42, 42, 74, 0.5)',
        },
        ticks: {
            color: '#a0a0a0',
            maxTicksLimit: 6,
        },
    } : {
        type: 'linear',
        grid: {
            color: 'rgba(42, 42, 74, 0.5)',
        },
        ticks: {
            color: '#a0a0a0',
            maxTicksLimit: 6,
            callback: function(value) {
                const hours = Math.floor(value);
                const minutes = Math.round((value - hours) * 60);
                if (minutes === 0) return `${hours}h`;
                return `${hours}h ${minutes}m`;
            },
        },
    };

    return {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
            intersect: false,
            mode: 'index',
        },
        plugins: {
            legend: {
                display: false,
            },
            tooltip: {
                backgroundColor: 'rgba(22, 33, 62, 0.9)',
                titleColor: '#eaeaea',
                bodyColor: '#eaeaea',
                borderColor: '#2a2a4a',
                borderWidth: 1,
            },
        },
        scales: {
            x: xScale,
            y: {
                beginAtZero: true,
                grid: {
                    color: 'rgba(42, 42, 74, 0.5)',
                },
                ticks: {
                    color: '#a0a0a0',
                },
            },
        },
    };
}

function formatElapsedTime(hours) {
    const h = Math.floor(hours);
    const m = Math.round((hours - h) * 60);
    if (m === 0) return `${h}h`;
    return `${h}h ${m}m`;
}

function renderCharts(data, forceRender = false) {
    const newHash = simpleHash(data);
    if (!forceRender && newHash === lastStatsHash) {
        return; // No change
    }
    lastStatsHash = newHash;

    const realtimeMode = !!data?.realtime_tracking;

    // Destroy charts if mode changed (axis type can't be updated in-place)
    if (lastChartRealtimeMode !== null && lastChartRealtimeMode !== realtimeMode) {
        if (cumulativeValueChart) { cumulativeValueChart.destroy(); cumulativeValueChart = null; }
        if (valueRateChart) { valueRateChart.destroy(); valueRateChart = null; }
    }
    lastChartRealtimeMode = realtimeMode;

    const chartOptions = getChartOptions(realtimeMode);

    // Prepare data for cumulative value chart
    const cumulativeValueData = (data?.cumulative_value || []).map(p => ({
        x: realtimeMode ? new Date(p.timestamp) : p.cumulative_seconds / 3600,
        y: p.value,
    }));

    // Prepare data for value/hour chart
    const valueRateData = (data?.value_per_hour || []).map(p => ({
        x: realtimeMode ? new Date(p.timestamp) : p.cumulative_seconds / 3600,
        y: p.value,
    }));

    // Tooltip title callback for map-time mode
    const tooltipTitle = realtimeMode ? undefined : function(items) {
        if (items.length > 0) return formatElapsedTime(items[0].parsed.x);
        return '';
    };

    // Render or update Cumulative Value chart
    const cumulativeValueCtx = document.getElementById('cumulative-value-chart');
    if (cumulativeValueCtx) {
        if (cumulativeValueChart) {
            cumulativeValueChart.data.datasets[0].data = cumulativeValueData;
            cumulativeValueChart.update('none');
        } else {
            cumulativeValueChart = new Chart(cumulativeValueCtx, {
                type: 'line',
                data: {
                    datasets: [{
                        data: cumulativeValueData,
                        borderColor: '#e94560',
                        backgroundColor: 'rgba(233, 69, 96, 0.1)',
                        fill: true,
                        tension: 0.3,
                        pointRadius: 2,
                        pointHoverRadius: 5,
                    }],
                },
                options: {
                    ...chartOptions,
                    plugins: {
                        ...chartOptions.plugins,
                        tooltip: {
                            ...chartOptions.plugins.tooltip,
                            callbacks: {
                                title: tooltipTitle,
                                label: (ctx) => `Value: ${formatNumber(Math.round(ctx.parsed.y))} FE`,
                            },
                        },
                    },
                },
            });
        }
    }

    // Render or update Value Rate chart
    const valueRateCtx = document.getElementById('value-rate-chart');
    if (valueRateCtx) {
        if (valueRateChart) {
            valueRateChart.data.datasets[0].data = valueRateData;
            valueRateChart.update('none');
        } else {
            valueRateChart = new Chart(valueRateCtx, {
                type: 'line',
                data: {
                    datasets: [{
                        data: valueRateData,
                        borderColor: '#4ecca3',
                        backgroundColor: 'rgba(78, 204, 163, 0.1)',
                        fill: true,
                        tension: 0.3,
                        pointRadius: 2,
                        pointHoverRadius: 5,
                    }],
                },
                options: {
                    ...chartOptions,
                    plugins: {
                        ...chartOptions.plugins,
                        tooltip: {
                            ...chartOptions.plugins.tooltip,
                            callbacks: {
                                title: tooltipTitle,
                                label: (ctx) => `Value/hr: ${formatNumber(Math.round(ctx.parsed.y))} FE`,
                            },
                        },
                    },
                },
            });
        }
    }
}

function updateLastRefresh() {
    const now = new Date();
    const timeStr = now.toLocaleTimeString();
    document.getElementById('last-update').textContent = `Last updated: ${timeStr}`;
}

// --- Modal ---

async function showRunDetails(runId) {
    const run = lastRunsData?.runs?.find(r => r.id === runId);
    if (!run) return;

    const modal = document.getElementById('loot-modal');
    const title = document.getElementById('modal-title');
    const body = document.getElementById('modal-body');

    title.textContent = `${tZone(run.zone_name)} - ${formatDuration(run.duration_seconds)}`;

    // Track ignored items state for this modal
    const ignoredItems = new Set(run.ignored_items || []);

    let content = '';

    // Ignore run button
    const isIgnored = run.is_ignored;
    content += `<button class="ignore-run-btn${isIgnored ? ' ignored' : ''}" id="ignore-run-btn" data-run-id="${run.id}" data-ignored="${isIgnored}">
        ${isIgnored ? '✓ Run Ignored' : '✕ Ignore Run'}
    </button>`;

    // Show loot section
    if (!run.loot || run.loot.length === 0) {
        content += '<p>No loot recorded for this run.</p>';
    } else {
        // Sort by FE value (highest first), items without price at the end
        const sortedLoot = [...run.loot].sort((a, b) => {
            const aVal = a.total_value_fe ?? -Infinity;
            const bVal = b.total_value_fe ?? -Infinity;
            return bVal - aVal;
        });
        content += `
            <ul class="loot-list">
                ${sortedLoot.map(item => {
                    const iconHtml = getIconHtml(item.config_base_id, 'loot-item-icon');
                    const valueStr = item.total_value_fe !== null
                        ? `${item.total_value_fe.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} FE`
                        : '<span class="no-price">no price</span>';
                    const itemIgnored = ignoredItems.has(item.config_base_id);
                    const itemIgnoredClass = itemIgnored ? ' item-ignored' : '';
                    const ignoreIcon = itemIgnored ? '👁‍🗨' : '👁';
                    const ignoreTitle = itemIgnored ? 'Include this item in calculations' : 'Ignore this item from calculations';
                    return `
                        <li class="loot-item${itemIgnoredClass}" data-config-id="${item.config_base_id}">
                            <div class="loot-item-name">
                                ${iconHtml}
                                <span>${escapeHtml(pickItemName(item))}</span>
                            </div>
                            <div class="loot-item-values">
                                <span class="loot-item-qty ${item.total_value_fe !== null ? (item.total_value_fe > 0 ? 'positive' : 'negative') : ''}">${valueStr}</span>
                                <span class="loot-item-value">x${formatNumber(Math.abs(item.quantity))}</span>
                            </div>
                            <span class="loot-item-ignore${itemIgnored ? ' ignored' : ''}" title="${ignoreTitle}" data-config-id="${item.config_base_id}">${ignoreIcon}</span>
                        </li>
                    `;
                }).join('')}
            </ul>
        `;
    }

    // Show summary if there are costs
    if (run.map_cost_fe !== null && run.map_cost_fe !== undefined && run.map_cost_fe > 0) {
        const netValue = run.net_value_fe !== null ? run.net_value_fe : run.total_value;
        const costTooltip = buildCostTooltip(run.map_cost_items);
        const warningIcon = run.map_cost_has_unpriced
            ? ' <span class="cost-warning" title="Some items have unknown prices">⚠</span>'
            : '';
        content += `
            <div class="run-summary">
                <div class="run-summary-row">
                    <span class="run-summary-label">Gross Value</span>
                    <span class="run-summary-value">${formatFEValue(run.total_value)} FE</span>
                </div>
                <div class="run-summary-row">
                    <span class="run-summary-label">Map Cost</span>
                    <span class="run-summary-value negative cost-hover" title="${costTooltip}">-${formatFEValue(run.map_cost_fe)} FE${warningIcon}</span>
                </div>
                <div class="run-summary-row total">
                    <span class="run-summary-label">Net Value</span>
                    <span class="run-summary-value ${netValue >= 0 ? 'positive' : 'negative'}">${formatFEValue(netValue)} FE</span>
                </div>
            </div>
        `;
    }

    body.innerHTML = content;
    modal.classList.remove('hidden');

    // Wire up ignore run button
    const ignoreBtn = document.getElementById('ignore-run-btn');
    if (ignoreBtn) {
        ignoreBtn.addEventListener('click', async () => {
            const currentlyIgnored = ignoreBtn.dataset.ignored === 'true';
            const newState = !currentlyIgnored;
            try {
                const resp = await fetch(`${API_BASE}/runs/${run.id}/ignore`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ ignored: newState }),
                });
                if (resp.ok) {
                    ignoreBtn.dataset.ignored = String(newState);
                    ignoreBtn.textContent = newState ? '✓ Run Ignored' : '✕ Ignore Run';
                    ignoreBtn.classList.toggle('ignored', newState);
                    // Update local data and refresh
                    run.is_ignored = newState;
                    lastRunsHash = null;
                    lastStatsHash = null;
                    await refreshAll(true);
                }
            } catch (e) { console.error('Failed to toggle run ignore:', e); }
        });
    }

    // Wire up per-item ignore toggles
    body.querySelectorAll('.loot-item-ignore').forEach(el => {
        el.addEventListener('click', async () => {
            const configId = parseInt(el.dataset.configId);
            if (ignoredItems.has(configId)) {
                ignoredItems.delete(configId);
            } else {
                ignoredItems.add(configId);
            }
            // Update UI immediately
            const li = el.closest('.loot-item');
            const isNowIgnored = ignoredItems.has(configId);
            li.classList.toggle('item-ignored', isNowIgnored);
            el.classList.toggle('ignored', isNowIgnored);
            el.textContent = isNowIgnored ? '👁‍🗨' : '👁';
            el.title = isNowIgnored ? 'Include this item in calculations' : 'Ignore this item from calculations';

            // Save to server
            try {
                await fetch(`${API_BASE}/runs/${run.id}/ignored-items`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ ignored_ids: Array.from(ignoredItems) }),
                });
                // Update local data and refresh
                run.ignored_items = Array.from(ignoredItems);
                lastRunsHash = null;
                lastStatsHash = null;
                await refreshAll(true);
            } catch (e) { console.error('Failed to update ignored items:', e); }
        });
    });
}

function closeModal() {
    document.getElementById('loot-modal').classList.add('hidden');
}

// Close modal on outside click
document.getElementById('loot-modal').addEventListener('click', (e) => {
    if (e.target.id === 'loot-modal') {
        closeModal();
    }
});

// Close modal on Escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeModal();
        closeHelpModal();
        closeSettingsModal();
        closeLootReportModal();
        closeHideItemsModal();
    }
});

// --- Hide Items Modal ---

async function fetchHiddenItems() {
    try {
        const res = await fetch(`${API_BASE}/inventory/hidden`);
        if (!res.ok) return new Set();
        const data = await res.json();
        return new Set(data.hidden_ids || []);
    } catch { return new Set(); }
}

async function saveHiddenItemsToServer(ids) {
    try {
        await fetch(`${API_BASE}/inventory/hidden`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ hidden_ids: Array.from(ids) }),
        });
    } catch (e) { console.error('Failed to save hidden items:', e); }
}

function updateHideItemsButton() {
    const btn = document.getElementById('hide-items-btn');
    if (!btn) return;
    const count = hiddenItemIds.size;
    btn.textContent = count > 0 ? `Hide Items (${count})` : 'Hide Items';
}

async function fetchHiddenExcludeWorthSetting() {
    try {
        const res = await fetch(`${API_BASE}/settings/hidden_items_exclude_worth`);
        if (!res.ok) return false;
        const data = await res.json();
        return data.value === 'true';
    } catch { return false; }
}

async function updateHiddenExcludeWorthSetting(enabled) {
    try {
        await fetch(`${API_BASE}/settings/hidden_items_exclude_worth`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ value: enabled ? 'true' : 'false' }),
        });
    } catch { /* ignore */ }
}

function updateHideItemsHintText(excludeFromWorth) {
    const el = document.getElementById('hide-items-hint-text');
    if (el) {
        el.textContent = excludeFromWorth
            ? 'Check items to hide from inventory display. Hidden items are excluded from net worth.'
            : 'Check items to hide from inventory display. Hidden items still count toward net worth.';
    }
}

async function handleHiddenExcludeWorthToggle(event) {
    const enabled = event.target.checked;
    await updateHiddenExcludeWorthSetting(enabled);
    updateHideItemsHintText(enabled);
    // Refresh to reflect net worth change
    lastInventoryHash = null;
    refreshAll(true);
}

async function openHideItemsModal() {
    const modal = document.getElementById('hide-items-modal');
    // Fetch full inventory (include hidden items)
    try {
        const res = await fetch(`${API_BASE}/inventory?include_hidden=true`);
        if (!res.ok) return;
        const data = await res.json();
        modal._allItems = data.items || [];
    } catch { return; }

    // Refresh hidden ids from server
    hiddenItemIds = await fetchHiddenItems();
    // Store a working copy for the modal
    modal._pendingHidden = new Set(hiddenItemIds);
    hideItemsModalSort = 'value';
    // Clear search
    const searchInput = document.getElementById('hide-items-search');
    if (searchInput) searchInput.value = '';
    // Reset sortable header state
    const qtyTh = document.getElementById('hide-sort-quantity').closest('th');
    const valTh = document.getElementById('hide-sort-value').closest('th');
    qtyTh.classList.remove('active');
    valTh.classList.add('active', 'desc');

    // Load exclude-from-worth setting
    const excludeWorth = await fetchHiddenExcludeWorthSetting();
    document.getElementById('settings-hidden-exclude-worth').checked = excludeWorth;
    updateHideItemsHintText(excludeWorth);

    renderHideItemsTable();
    modal.classList.remove('hidden');
}

function closeHideItemsModal() {
    document.getElementById('hide-items-modal').classList.add('hidden');
}

function sortHideItemsTable(sortBy) {
    hideItemsModalSort = sortBy;
    // Update sortable header classes
    const qtyTh = document.getElementById('hide-sort-quantity').closest('th');
    const valTh = document.getElementById('hide-sort-value').closest('th');
    qtyTh.classList.toggle('active', sortBy === 'quantity');
    qtyTh.classList.add('desc');
    valTh.classList.toggle('active', sortBy === 'value');
    valTh.classList.add('desc');
    renderHideItemsTable();
}

function renderHideItemsTable() {
    const modal = document.getElementById('hide-items-modal');
    const searchTerm = (document.getElementById('hide-items-search')?.value || '').toLowerCase();
    let items = [...(modal._allItems || [])];
    const pending = modal._pendingHidden || new Set();

    if (searchTerm) {
        items = items.filter(item => pickItemName(item).toLowerCase().includes(searchTerm));
    }

    // Sort
    if (hideItemsModalSort === 'value') {
        items.sort((a, b) => (b.total_value_fe || 0) - (a.total_value_fe || 0));
    } else {
        items.sort((a, b) => b.quantity - a.quantity);
    }

    const tbody = document.getElementById('hide-items-body');
    if (items.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;color:var(--text-secondary)">No items in inventory</td></tr>';
        updateHideItemsCount(pending);
        return;
    }

    tbody.innerHTML = items.map(item => {
        const checked = pending.has(item.config_base_id);
        const iconHtml = getIconHtml(item.config_base_id, 'item-icon');
        const valueStr = item.total_value_fe ? formatFEValue(item.total_value_fe) : '--';
        return `
            <tr class="${checked ? 'hide-items-row-hidden' : ''}">
                <td><input type="checkbox" data-id="${item.config_base_id}" ${checked ? 'checked' : ''}
                    onchange="toggleHideItem(${item.config_base_id}, this.checked)"></td>
                <td><div class="item-name-cell">${iconHtml}<span>${escapeHtml(pickItemName(item))}</span></div></td>
                <td>${formatNumber(item.quantity)}</td>
                <td>${valueStr}</td>
            </tr>`;
    }).join('');
    updateHideItemsCount(pending);
}

function toggleHideItem(configBaseId, isChecked) {
    const modal = document.getElementById('hide-items-modal');
    const pending = modal._pendingHidden || new Set();
    if (isChecked) {
        pending.add(configBaseId);
    } else {
        pending.delete(configBaseId);
    }
    modal._pendingHidden = pending;
    // Update row styling
    const checkbox = document.querySelector(`#hide-items-body input[data-id="${configBaseId}"]`);
    if (checkbox) {
        checkbox.closest('tr').classList.toggle('hide-items-row-hidden', isChecked);
    }
    updateHideItemsCount(pending);
}

function updateHideItemsCount(pending) {
    const el = document.getElementById('hide-items-count');
    if (el) {
        const count = pending.size;
        el.textContent = count > 0 ? `${count} item${count !== 1 ? 's' : ''} hidden` : '';
    }
}

async function saveHideItems() {
    const modal = document.getElementById('hide-items-modal');
    const pending = modal._pendingHidden || new Set();
    hiddenItemIds = new Set(pending);
    await saveHiddenItemsToServer(hiddenItemIds);
    updateHideItemsButton();
    closeHideItemsModal();
    // Force inventory re-render
    lastInventoryHash = null;
    refreshAll(true);
}

// Close hide items modal on outside click
document.getElementById('hide-items-modal').addEventListener('click', (e) => {
    if (e.target.id === 'hide-items-modal') {
        closeHideItemsModal();
    }
});

// Exclude from net worth toggle
document.getElementById('settings-hidden-exclude-worth').addEventListener('change', handleHiddenExcludeWorthToggle);

// --- Economy Website ---

function openEconomy() {
    window.open('https://titrack.ninja', '_blank');
}

// --- Loot Report Modal ---

function formatDurationLong(seconds) {
    if (!seconds) return '--';
    const hours = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    if (hours > 0) {
        return `${hours}h ${mins}m ${secs}s`;
    }
    return `${mins}m ${secs}s`;
}

async function showLootReport() {
    const modal = document.getElementById('loot-report-modal');
    const tableBody = document.getElementById('loot-report-table-body');

    // Show loading state
    tableBody.innerHTML = '<tr><td colspan="6" class="loading">Loading report...</td></tr>';
    document.getElementById('report-total-value').textContent = '...';
    document.getElementById('report-profit').textContent = '...';
    document.getElementById('report-total-items').textContent = '...';
    document.getElementById('report-run-count').textContent = '...';
    document.getElementById('report-total-time').textContent = '...';
    document.getElementById('report-profit-per-hour').textContent = '...';
    document.getElementById('report-profit-per-map').textContent = '...';

    modal.classList.remove('hidden');

    // Fetch report data
    const data = await fetchLootReport();
    lastLootReportData = data;

    if (!data) {
        tableBody.innerHTML = '<tr><td colspan="6" class="loading">Failed to load report</td></tr>';
        return;
    }

    // Update summary stats
    document.getElementById('report-total-value').textContent = formatFEValue(data.total_value_fe) + ' FE';
    document.getElementById('report-profit').textContent = formatFEValue(data.profit_fe) + ' FE';
    document.getElementById('report-total-items').textContent = formatNumber(data.total_items);
    document.getElementById('report-run-count').textContent = formatNumber(data.run_count);
    document.getElementById('report-total-time').textContent = formatDurationLong(data.total_duration_seconds);
    document.getElementById('report-profit-per-hour').textContent = formatNumber(Math.round(data.profit_per_hour)) + ' FE';
    document.getElementById('report-profit-per-map').textContent = formatNumber(Math.round(data.profit_per_map)) + ' FE';

    // Show/hide map costs based on setting
    const costStat = document.getElementById('report-cost-stat');
    if (data.map_costs_enabled && data.total_map_cost_fe > 0) {
        document.getElementById('report-map-costs').textContent = '-' + formatFEValue(data.total_map_cost_fe) + ' FE';
        costStat.classList.remove('hidden');
    } else {
        costStat.classList.add('hidden');
    }

    // Handle empty state
    if (!data.items || data.items.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="6" class="loading">No loot recorded yet. Complete some runs to see your report.</td></tr>';
        // Clear any existing chart
        if (lootReportChart) {
            lootReportChart.destroy();
            lootReportChart = null;
        }
        return;
    }

    // Render table
    tableBody.innerHTML = data.items.map(item => {
        const iconHtml = getIconHtml(item.config_base_id, 'item-icon');
        const priceText = item.price_fe !== null ? formatFEValue(item.price_fe) : '<span class="no-price">--</span>';
        const valueText = item.total_value_fe !== null ? formatFEValue(item.total_value_fe) : '<span class="no-price">--</span>';
        const percentText = item.percentage !== null ? `${item.percentage.toFixed(1)}%` : '--';
        const isIgnored = item.is_ignored;
        const ignoreIcon = isIgnored ? '👁‍🗨' : '👁';
        const ignoreTitle = isIgnored ? 'Include this item in report totals' : 'Exclude this item from report totals';

        return `
            <tr class="${isIgnored ? 'report-item-ignored' : ''}">
                <td>
                    <div class="item-col">
                        ${iconHtml}
                        <a href="${pickItemUrl(item) || ('https://titrack.ninja/item/' + item.config_base_id)}" target="_blank" class="item-name-link">${escapeHtml(pickItemName(item))}</a>
                    </div>
                </td>
                <td>${formatNumber(item.quantity)}</td>
                <td>${priceText}</td>
                <td>${valueText}</td>
                <td>${percentText}</td>
                <td><span class="report-item-ignore${isIgnored ? ' ignored' : ''}" title="${ignoreTitle}" data-config-id="${item.config_base_id}">${ignoreIcon}</span></td>
            </tr>
        `;
    }).join('');

    // Wire up report item ignore toggles
    tableBody.querySelectorAll('.report-item-ignore').forEach(el => {
        el.addEventListener('click', async () => {
            const configId = parseInt(el.dataset.configId);
            const item = data.items.find(i => i.config_base_id === configId);
            if (!item) return;

            // Toggle state
            item.is_ignored = !item.is_ignored;
            const isNowIgnored = item.is_ignored;

            // Update row UI immediately
            const tr = el.closest('tr');
            tr.classList.toggle('report-item-ignored', isNowIgnored);
            el.classList.toggle('ignored', isNowIgnored);
            el.textContent = isNowIgnored ? '👁‍🗨' : '👁';
            el.title = isNowIgnored ? 'Include this item in report totals' : 'Exclude this item from report totals';

            // Recalculate totals client-side
            recalcReportTotals(data);

            // Save to server
            const ignoredIds = data.items.filter(i => i.is_ignored).map(i => i.config_base_id);
            try {
                await fetch(`${API_BASE}/runs/report/ignored-items`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ ignored_ids: ignoredIds }),
                });
            } catch (e) { console.error('Failed to update report ignored items:', e); }
        });
    });

    // Render chart (top 10 items + "Other") - only non-ignored items
    renderLootReportChart(data);
}

function recalcReportTotals(data) {
    // Recalculate total_value from non-ignored items
    let totalValue = 0;
    for (const item of data.items) {
        if (!item.is_ignored && item.total_value_fe !== null) {
            totalValue += item.total_value_fe;
        }
    }
    data.total_value_fe = Math.round(totalValue * 100) / 100;

    // Recalculate percentages
    for (const item of data.items) {
        if (item.is_ignored) {
            item.percentage = null;
        } else if (item.total_value_fe !== null && totalValue > 0) {
            item.percentage = Math.round((item.total_value_fe / totalValue) * 10000) / 100;
        }
    }

    // Update percent cells in the table
    const rows = document.querySelectorAll('#loot-report-table-body tr');
    rows.forEach(row => {
        const ignoreEl = row.querySelector('.report-item-ignore');
        if (!ignoreEl) return;
        const configId = parseInt(ignoreEl.dataset.configId);
        const item = data.items.find(i => i.config_base_id === configId);
        if (!item) return;
        const cells = row.querySelectorAll('td');
        const percentCell = cells[4]; // 5th column (0-indexed)
        percentCell.textContent = item.percentage !== null ? `${item.percentage.toFixed(1)}%` : '--';
    });

    // Recalculate profit
    const profit = totalValue - (data.map_costs_enabled ? data.total_map_cost_fe : 0);
    data.profit_fe = Math.round(profit * 100) / 100;

    // Recalculate rates
    const profitPerHour = data.total_duration_seconds > 0 ? (profit / data.total_duration_seconds * 3600) : 0;
    const profitPerMap = data.run_count > 0 ? (profit / data.run_count) : 0;

    // Count non-ignored items
    const nonIgnoredCount = data.items.filter(i => !i.is_ignored).length;

    // Update summary display
    document.getElementById('report-total-value').textContent = formatFEValue(data.total_value_fe) + ' FE';
    document.getElementById('report-profit').textContent = formatFEValue(data.profit_fe) + ' FE';
    document.getElementById('report-total-items').textContent = formatNumber(nonIgnoredCount);
    document.getElementById('report-profit-per-hour').textContent = formatNumber(Math.round(profitPerHour)) + ' FE';
    document.getElementById('report-profit-per-map').textContent = formatNumber(Math.round(profitPerMap)) + ' FE';

    // Re-render chart with updated data
    renderLootReportChart(data);
}

function renderLootReportChart(data) {
    const canvas = document.getElementById('loot-report-chart');

    // Destroy existing chart
    if (lootReportChart) {
        lootReportChart.destroy();
        lootReportChart = null;
    }

    // Filter items with value and sort by value (exclude ignored items)
    const pricedItems = data.items.filter(item => item.total_value_fe !== null && item.total_value_fe > 0 && !item.is_ignored);

    if (pricedItems.length === 0) {
        return;
    }

    // Take top 10, group rest as "Other"
    const top10 = pricedItems.slice(0, 10);
    const others = pricedItems.slice(10);

    const labels = top10.map(item => pickItemName(item));
    const values = top10.map(item => item.total_value_fe);

    // Add "Other" category if there are more items
    if (others.length > 0) {
        const otherValue = others.reduce((sum, item) => sum + (item.total_value_fe || 0), 0);
        labels.push(`Other (${others.length} items)`);
        values.push(otherValue);
    }

    // Color palette matching app theme
    const colors = [
        '#e94560',  // Accent red
        '#4ecca3',  // Positive green
        '#ff6b6b',  // Accent secondary
        '#64b5f6',  // Light blue
        '#ffb74d',  // Orange
        '#ba68c8',  // Purple
        '#4db6ac',  // Teal
        '#f06292',  // Pink
        '#7986cb',  // Indigo
        '#aed581',  // Light green
        '#9e9e9e',  // Gray (for "Other")
    ];

    // Include percentage in labels for the legend
    const labelsWithPercent = labels.map((label, i) => {
        const total = values.reduce((a, b) => a + b, 0);
        const percentage = ((values[i] / total) * 100).toFixed(1);
        const truncLabel = label.length > 18 ? label.substring(0, 16) + '...' : label;
        return `${truncLabel} (${percentage}%)`;
    });

    lootReportChart = new Chart(canvas, {
        type: 'doughnut',
        data: {
            labels: labelsWithPercent,
            datasets: [{
                data: values,
                backgroundColor: colors.slice(0, labels.length),
                borderColor: 'rgba(22, 33, 62, 0.8)',
                borderWidth: 2,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'right',
                    labels: {
                        color: '#a0a0a0',
                        padding: 8,
                        usePointStyle: true,
                        font: {
                            size: 11,
                        }
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(22, 33, 62, 0.9)',
                    titleColor: '#eaeaea',
                    bodyColor: '#eaeaea',
                    borderColor: '#2a2a4a',
                    borderWidth: 1,
                    callbacks: {
                        label: function(ctx) {
                            const value = ctx.parsed;
                            const total = ctx.dataset.data.reduce((a, b) => a + b, 0);
                            const percentage = ((value / total) * 100).toFixed(1);
                            return `${formatFEValue(value)} FE (${percentage}%)`;
                        }
                    }
                }
            }
        }
    });
}

function closeLootReportModal() {
    document.getElementById('loot-report-modal').classList.add('hidden');
}

// Close loot report modal on outside click
document.addEventListener('click', (e) => {
    if (e.target.id === 'loot-report-modal') {
        closeLootReportModal();
    }
});

async function exportLootReportCSV() {
    if (!lastLootReportData || !lastLootReportData.items) {
        alert('No data to export');
        return;
    }

    try {
        // Fetch CSV from server
        const response = await fetch(`${API_BASE}/runs/report/csv`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const csvContent = await response.text();
        const filename = `titrack-loot-report-${new Date().toISOString().split('T')[0]}.csv`;

        // Try using the File System Access API (modern browsers)
        if (window.showSaveFilePicker) {
            try {
                const handle = await window.showSaveFilePicker({
                    suggestedName: filename,
                    types: [{
                        description: 'CSV Files',
                        accept: { 'text/csv': ['.csv'] },
                    }],
                });
                const writable = await handle.createWritable();
                await writable.write(csvContent);
                await writable.close();
                showToast(`Exported to ${handle.name}`, 'success');
                return;
            } catch (err) {
                // User cancelled or API not supported, fall through to legacy method
                if (err.name === 'AbortError') {
                    return; // User cancelled
                }
            }
        }

        // Fallback: Create blob and download link
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        link.style.display = 'none';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);

        showToast(`Exported to Downloads folder as ${filename}`, 'success');
    } catch (error) {
        console.error('Error exporting CSV:', error);
        showToast('Failed to export CSV', 'error');
    }
}

// --- Help Modal ---

function openHelpModal() {
    document.getElementById('help-modal').classList.remove('hidden');
}

function closeHelpModal() {
    document.getElementById('help-modal').classList.add('hidden');
}

// Close help modal on outside click
document.getElementById('help-modal').addEventListener('click', (e) => {
    if (e.target.id === 'help-modal') {
        closeHelpModal();
    }
});

// --- Data Refresh ---

async function refreshAll(forceRender = false) {
    try {
        const [status, stats, runs, inventory, statsHistory, player, cloudStatus, activeRun] = await Promise.all([
            fetchStatus(),
            fetchStats(),
            fetchRuns(),
            fetchInventory(),
            fetchStatsHistory(24),
            fetchPlayer(),
            fetchCloudStatus(),
            fetchActiveRun()
        ]);

        lastRunsData = runs;
        lastInventoryData = inventory;

        renderStatus(status);
        renderStats(stats, inventory);
        renderCloudStatus(cloudStatus);
        renderActiveRun(activeRun, forceRender);

        // Filter out active/incomplete runs from recent runs list
        // A run is complete if it has end_ts set
        let filteredRuns = runs;
        if (runs?.runs) {
            filteredRuns = {
                ...runs,
                runs: runs.runs.filter(r => r.end_ts != null)
            };
        }
        renderRuns(filteredRuns, forceRender);

        // Load cloud prices if sync is enabled
        if (cloudStatus && cloudStatus.enabled && Object.keys(cloudPricesCache).length === 0) {
            await loadCloudPrices();
        }

        renderInventory(inventory, forceRender);
        renderCharts(statsHistory, forceRender);

        // Check low supply alerts after inventory is rendered
        await checkLowSupplyAlerts();

        // Check if player changed and update display
        const playerHash = simpleHash(player);
        if (forceRender || playerHash !== lastPlayerHash) {
            renderPlayer(player);
            lastPlayerHash = playerHash;

            // Reload per-player data when player changes
            hiddenItemIds = await fetchHiddenItems();
            updateHideItemsButton();

            // Clear supply alert state on player change
            supplyAlertedCategories.clear();

            // Auto-close no-character modal when character is detected
            if (player && noCharacterModalShown) {
                closeNoCharacterModal();
            }
        }

        updateLastRefresh();
    } catch (error) {
        console.error('Error refreshing data:', error);
    }
}

function startAutoRefresh() {
    if (refreshTimer) return;
    refreshTimer = setInterval(refreshAll, REFRESH_INTERVAL);
}

function stopAutoRefresh() {
    if (refreshTimer) {
        clearInterval(refreshTimer);
        refreshTimer = null;
    }
}

// --- Reset Stats ---

async function resetStats() {
    if (!confirm('Reset all run tracking data? This will clear all runs and loot history.\n\nYour inventory, prices, and settings will be preserved.')) {
        return;
    }

    const btn = document.getElementById('reset-stats-btn');
    btn.disabled = true;
    btn.textContent = t('controls.resetting');

    const result = await postResetStats();

    btn.disabled = false;
    btn.textContent = t('controls.reset_stats');

    if (result && result.success) {
        // Clear chart data hashes to force re-render
        lastRunsHash = null;
        lastStatsHash = null;

        // Refresh all data
        await refreshAll(true);
    } else {
        alert('Failed to reset stats. Please try again.');
    }
}

// --- Inventory Sorting ---

async function sortInventory(field) {
    // Toggle order if same field, otherwise default to desc
    if (inventorySortBy === field) {
        inventorySortOrder = inventorySortOrder === 'desc' ? 'asc' : 'desc';
    } else {
        inventorySortBy = field;
        inventorySortOrder = 'desc';
    }

    // Update UI indicators
    updateSortIndicators();

    // Fetch and render with new sort
    const inventory = await fetchInventory();
    lastInventoryData = inventory;
    renderInventory(inventory, true);
}

function toggleInvFilterMenu() {
    document.getElementById('inv-filter-menu').classList.toggle('hidden');
}

async function filterInventoryTab(btn) {
    inventoryTabFilter = btn.dataset.tab;

    // Update active state
    document.querySelectorAll('.inv-filter-option').forEach(c => c.classList.remove('active'));
    btn.classList.add('active');

    // Highlight the filter icon when a non-All tab is selected
    document.getElementById('inv-filter-btn').classList.toggle('filtered', !!inventoryTabFilter);

    // Close the menu
    document.getElementById('inv-filter-menu').classList.add('hidden');

    // Fetch and render with new filter
    const inventory = await fetchInventory();
    lastInventoryData = inventory;
    renderInventory(inventory, true);
}

function updateSortIndicators() {
    // Remove active class from all sortable headers
    document.querySelectorAll('th.sortable').forEach(th => {
        th.classList.remove('active', 'asc', 'desc');
    });

    // Add active class to current sort column
    const activeHeader = document.querySelector(`th.sortable[data-sort="${inventorySortBy}"]`);
    if (activeHeader) {
        activeHeader.classList.add('active', inventorySortOrder);
    }
}

// --- Utility ---

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function escapeAttr(text) {
    if (!text) return '';
    return text
        .replace(/&/g, '&amp;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}

function simpleHash(obj) {
    // Simple hash for comparing data changes
    return JSON.stringify(obj);
}

function handleIconError(img) {
    // Track failed icon and hide it
    if (img.dataset.configId) {
        failedIcons.add(img.dataset.configId);
    }
    img.style.display = 'none';
}

function getIconHtml(configBaseId, cssClass) {
    // Don't render icons that have previously failed
    if (!configBaseId || failedIcons.has(String(configBaseId))) {
        return '';
    }
    // Use proxy endpoint to fetch icons (handles CDN headers server-side)
    const proxyUrl = `/api/icons/${configBaseId}`;
    return `<img src="${proxyUrl}" alt="" class="${cssClass}" data-config-id="${configBaseId}" onerror="handleIconError(this)">`;
}

// --- Update System ---

async function fetchUpdateStatus() {
    return fetchJson('/update/status');
}

async function triggerUpdateCheck() {
    try {
        const response = await fetch(`${API_BASE}/update/check`, {
            method: 'POST'
        });
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error('Error checking for updates:', error);
        return null;
    }
}

async function triggerUpdateDownload() {
    try {
        const response = await fetch(`${API_BASE}/update/download`, {
            method: 'POST'
        });
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error('Error downloading update:', error);
        return null;
    }
}

async function triggerUpdateInstall() {
    try {
        const response = await fetch(`${API_BASE}/update/install`, {
            method: 'POST'
        });
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error('Error installing update:', error);
        return null;
    }
}

function renderVersion(status) {
    const versionEl = document.getElementById('app-version');
    const badgeEl = document.getElementById('update-badge');
    const checkBtn = document.getElementById('check-updates-btn');

    if (!status) {
        versionEl.textContent = 'v--';
        return;
    }

    versionEl.textContent = `v${status.current_version}`;

    // Show/hide update badge
    if (status.status === 'available' || status.status === 'ready') {
        badgeEl.classList.remove('hidden');
        badgeEl.title = `Update available: v${status.latest_version}`;
    } else {
        badgeEl.classList.add('hidden');
    }

    // Update button state
    if (!status.can_update) {
        checkBtn.style.display = 'none'; // Hide in dev mode
    } else {
        checkBtn.style.display = '';
        if (status.status === 'checking') {
            checkBtn.textContent = 'Checking...';
            checkBtn.disabled = true;
        } else if (status.status === 'available') {
            checkBtn.textContent = 'Update Available!';
            checkBtn.disabled = false;
            checkBtn.classList.add('update-available');
        } else if (status.status === 'downloading') {
            checkBtn.textContent = 'Downloading...';
            checkBtn.disabled = true;
        } else if (status.status === 'ready') {
            checkBtn.textContent = 'Install Update';
            checkBtn.disabled = false;
            checkBtn.classList.add('update-ready');
        } else {
            checkBtn.textContent = 'Check for Updates';
            checkBtn.disabled = false;
            checkBtn.classList.remove('update-available', 'update-ready');
        }
    }
}

async function checkForUpdates() {
    const status = await fetchUpdateStatus();

    if (status && (status.status === 'available' || status.status === 'ready')) {
        showUpdateModal(status);
        return;
    }

    // Trigger update check
    await triggerUpdateCheck();

    // Start polling for result
    startUpdateStatusPolling();
}

function startUpdateStatusPolling() {
    if (updateCheckInterval) return;

    updateCheckInterval = setInterval(async () => {
        const status = await fetchUpdateStatus();
        updateStatus = status;
        renderVersion(status);

        // Stop polling when done checking
        if (status && status.status !== 'checking' && status.status !== 'downloading') {
            stopUpdateStatusPolling();

            if (status.status === 'available') {
                showUpdateModal(status);
            } else if (status.status === 'up_to_date') {
                showToast(`You're on the latest version (v${status.current_version})`, 'success');
            } else if (status.status === 'error') {
                showToast('Update check failed: ' + (status.error_message || 'Unknown error'), 'error');
            }
        }
    }, 1000);
}

function stopUpdateStatusPolling() {
    if (updateCheckInterval) {
        clearInterval(updateCheckInterval);
        updateCheckInterval = null;
    }
}

function startSilentUpdateCheck() {
    triggerUpdateCheck();

    let silentInterval = setInterval(async () => {
        const status = await fetchUpdateStatus();
        updateStatus = status;

        if (status && status.status !== 'checking') {
            clearInterval(silentInterval);
            renderVersion(status);

            if (status.status === 'available') {
                showUpdateModal(status);
            }
        }
    }, 1000);
}

function showUpdateModal(status) {
    const modal = document.getElementById('update-modal');
    const currentVersionEl = document.getElementById('update-current-version');
    const newVersionEl = document.getElementById('update-new-version');
    const releaseNotesEl = document.getElementById('update-release-notes');
    const progressContainer = document.getElementById('update-progress-container');
    const actionsEl = document.getElementById('update-actions');

    currentVersionEl.textContent = `v${status.current_version}`;
    newVersionEl.textContent = `v${status.latest_version}`;

    const warningEl = document.getElementById('update-install-warning');
    if (warningEl) {
        if (status.install_path_warning) {
            warningEl.textContent = status.install_path_warning;
            warningEl.classList.remove('hidden');
        } else {
            warningEl.textContent = '';
            warningEl.classList.add('hidden');
        }
    }

    // Show release notes (simple markdown to HTML)
    if (status.release_notes) {
        releaseNotesEl.innerHTML = simpleMarkdown(status.release_notes);
    } else {
        releaseNotesEl.textContent = 'No release notes available.';
    }

    // Reset progress
    progressContainer.classList.add('hidden');
    actionsEl.classList.remove('hidden');

    modal.classList.remove('hidden');
}

function closeUpdateModal() {
    document.getElementById('update-modal').classList.add('hidden');
    stopUpdateStatusPolling();
}

async function downloadAndInstallUpdate() {
    const downloadBtn = document.getElementById('update-download-btn');
    const progressContainer = document.getElementById('update-progress-container');
    const progressBar = document.getElementById('update-progress-bar');
    const progressText = document.getElementById('update-progress-text');

    // Start download
    downloadBtn.disabled = true;
    downloadBtn.textContent = 'Downloading...';

    const result = await triggerUpdateDownload();
    if (!result || !result.success) {
        alert('Failed to start download: ' + (result?.message || 'Unknown error'));
        downloadBtn.disabled = false;
        downloadBtn.textContent = 'Download & Install';
        return;
    }

    // Show progress
    progressContainer.classList.remove('hidden');

    // Poll for download progress
    const progressInterval = setInterval(async () => {
        const status = await fetchUpdateStatus();
        updateStatus = status;

        if (status) {
            if (status.download_size > 0) {
                const percent = Math.round((status.download_progress / status.download_size) * 100);
                progressBar.style.width = `${percent}%`;
                const mb = (status.download_progress / 1024 / 1024).toFixed(1);
                const totalMb = (status.download_size / 1024 / 1024).toFixed(1);
                progressText.textContent = `Downloading... ${mb} / ${totalMb} MB`;
            }

            if (status.status === 'ready') {
                clearInterval(progressInterval);
                progressText.textContent = 'Download complete. Installing...';
                progressBar.style.width = '100%';

                // Confirm and install
                if (confirm('Update downloaded. TITrack will restart to apply the update.\n\nContinue?')) {
                    await triggerUpdateInstall();
                    // If we get here, install failed
                    alert('Failed to start installation. Please try again.');
                } else {
                    downloadBtn.disabled = false;
                    downloadBtn.textContent = 'Install Update';
                    progressText.textContent = 'Ready to install';
                }
            } else if (status.status === 'error') {
                clearInterval(progressInterval);
                progressText.textContent = 'Download failed: ' + (status.error_message || 'Unknown error');
                downloadBtn.disabled = false;
                downloadBtn.textContent = 'Retry';
            }
        }
    }, 500);
}

function simpleMarkdown(text) {
    // Very basic markdown to HTML conversion
    return text
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.+?)\*/g, '<em>$1</em>')
        .replace(/`(.+?)`/g, '<code>$1</code>')
        .replace(/^### (.+)$/gm, '<h5>$1</h5>')
        .replace(/^## (.+)$/gm, '<h4>$1</h4>')
        .replace(/^# (.+)$/gm, '<h3>$1</h3>')
        .replace(/^- (.+)$/gm, '<li>$1</li>')
        .replace(/(<li>.*<\/li>)/gs, '<ul>$1</ul>')
        .replace(/\n\n/g, '<br><br>')
        .replace(/\n/g, '<br>');
}

// Close update modal on outside click and escape
document.addEventListener('click', (e) => {
    if (e.target.id === 'update-modal') {
        closeUpdateModal();
    }
});

// --- Browser Mode / Exit App ---

async function checkBrowserMode() {
    try {
        const response = await fetch(`${API_BASE}/browser-mode`);
        if (response.ok) {
            const data = await response.json();
            if (data.browser_mode) {
                // Show Exit button and toast notification
                document.getElementById('exit-app-btn').classList.remove('hidden');
                showToast('Running in browser mode (native window unavailable)', 'info');
            }
        }
    } catch (error) {
        console.error('Error checking browser mode:', error);
    }
}

async function exitApp() {
    if (!confirm('Are you sure you want to exit TITrack?')) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/shutdown`, { method: 'POST' });
        if (response.ok) {
            showToast('Shutting down...', 'info');
            // Close the browser tab after a short delay
            setTimeout(() => {
                window.close();
                // If window.close() doesn't work (most browsers block it),
                // show a message
                document.body.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100vh;background:#1a1a2e;color:#eaeaea;font-family:sans-serif;"><h1>TITrack has been shut down. You can close this tab.</h1></div>';
            }, 500);
        }
    } catch (error) {
        console.error('Error shutting down:', error);
        showToast('Failed to shut down', 'error');
    }
}

// --- Initialization ---

document.addEventListener('DOMContentLoaded', async () => {
    // Apply persisted language to static text BEFORE first render. Try to
    // sync with the server-side `language` setting (this may override the
    // localStorage cache if the user changed language on another device).
    try {
        const resp = await fetch(`${API_BASE}/settings/language`);
        if (resp.ok) {
            const data = await resp.json();
            if (data && data.value) {
                i18n.setLang(data.value);
            }
        }
    } catch (_) { /* offline-friendly */ }

    // Re-render dynamic content when the language changes.
    document.addEventListener('langchange', () => {
        try {
            i18n.loadZoneTranslations().then(() => {
                if (typeof refreshAll === 'function') refreshAll(true);
                if (typeof fetchPlayer === 'function') {
                    fetchPlayer().then(p => {
                        if (typeof renderPlayer === 'function') renderPlayer(p);
                    });
                }
            });
        } catch (e) { console.error('langchange handler:', e); }
    });

    // Set initial sort indicators
    updateSortIndicators();

    // Close inventory filter menu on outside click
    document.addEventListener('click', (e) => {
        const wrap = document.querySelector('.inv-filter-wrap');
        if (wrap && !wrap.contains(e.target)) {
            document.getElementById('inv-filter-menu').classList.add('hidden');
        }
    });

    // Check if running in browser fallback mode
    await checkBrowserMode();

    // Fetch and display version info
    const versionStatus = await fetchUpdateStatus();
    updateStatus = versionStatus;
    renderVersion(versionStatus);

    // Auto-check for updates on startup (only in packaged mode)
    if (versionStatus && versionStatus.status === 'idle' && versionStatus.can_update) {
        startSilentUpdateCheck();
    }

    // Fetch player info initially
    const player = await fetchPlayer();
    renderPlayer(player);
    lastPlayerHash = simpleHash(player);

    // Show warning modal if no character detected
    if (!player) {
        showNoCharacterModal({auto: true});
    }

    // Set up settings modal toggles
    const settingsTradeTaxToggle = document.getElementById('settings-trade-tax');
    settingsTradeTaxToggle.addEventListener('change', handleTradeTaxToggle);
    // Wire language <select>: persist to server and switch UI language.
    const settingsLanguage = document.getElementById('settings-language');
    if (settingsLanguage) {
        settingsLanguage.addEventListener('change', async (e) => {
            const lang = e.target.value || 'en';
            try {
                await fetch(`${API_BASE}/settings/language`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ value: lang }),
                });
            } catch (err) {
                console.error('Failed to save language setting:', err);
            }
            i18n.setLang(lang);
        });
    }

    const settingsMapCostsToggle = document.getElementById('settings-map-costs');
    settingsMapCostsToggle.addEventListener('change', handleMapCostsToggle);

    const settingsRealtimeToggle = document.getElementById('settings-realtime-tracking');
    settingsRealtimeToggle.addEventListener('change', handleRealtimeTrackingToggle);

    const settingsOverlayHideLootToggle = document.getElementById('settings-overlay-hide-loot');
    settingsOverlayHideLootToggle.addEventListener('change', handleOverlayHideLootToggle);

    const settingsOverlayMicroModeToggle = document.getElementById('settings-overlay-micro-mode');
    settingsOverlayMicroModeToggle.addEventListener('change', handleOverlayMicroModeToggle);

    document.getElementById('micro-font-scale-slider').addEventListener('input', (e) => {
        document.getElementById('micro-font-scale-value').textContent = e.target.value + '%';
    });
    document.getElementById('micro-font-scale-slider').addEventListener('change', (e) => {
        updateMicroFontScale(parseInt(e.target.value, 10));
    });

    // Supply alert threshold inputs
    for (const [inputId, category] of [
        ['settings-supply-beacon', 'beacon'],
        ['settings-supply-compass', 'compass'],
        ['settings-supply-resonance', 'resonance'],
    ]) {
        document.getElementById(inputId).addEventListener('change', async (e) => {
            const value = Math.max(0, parseInt(e.target.value, 10) || 0);
            e.target.value = value;
            await updateSupplyThreshold(category, value);
            // Update local state
            const catKey = category === 'beacon' ? 'beacons' : category === 'compass' ? 'compasses' : 'resonance';
            supplyAlertThresholds[catKey] = value;
            // Clear alerted state so alerts can re-trigger with new thresholds
            supplyAlertedCategories.clear();
        });
    }

    // Load supply alert thresholds
    await loadSupplyThresholds();

    // Load initial map costs state
    mapCostsEnabled = await fetchMapCostsSetting();

    // Load hidden items
    hiddenItemIds = await fetchHiddenItems();
    updateHideItemsButton();

    // Set up cloud sync toggle
    const cloudSyncToggle = document.getElementById('cloud-sync-toggle');
    cloudSyncToggle.addEventListener('change', handleCloudSyncToggle);

    // Initial cloud status check
    const cloudStatus = await fetchCloudStatus();
    renderCloudStatus(cloudStatus);

    // Load cloud prices if already enabled
    if (cloudStatus && cloudStatus.enabled) {
        await loadCloudPrices();
    }

    // Initial load (force render on first load)
    refreshAll(true);

    // Auto-refresh toggle
    const autoRefreshCheckbox = document.getElementById('auto-refresh');
    autoRefreshCheckbox.addEventListener('change', (e) => {
        if (e.target.checked) {
            startAutoRefresh();
        } else {
            stopAutoRefresh();
        }
    });

    // Start auto-refresh by default
    if (autoRefreshCheckbox.checked) {
        startAutoRefresh();
    }
});
