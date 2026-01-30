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
let priceHistoryChart = null;

// Cloud sync state
let cloudSyncEnabled = false;
let cloudPricesCache = {};

// Update state
let updateStatus = null;
let updateCheckInterval = null;

// Inventory sorting state
let inventorySortBy = 'value';
let inventorySortOrder = 'desc';

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

async function fetchStats() {
    return fetchJson('/runs/stats');
}

async function fetchRuns(page = 1, pageSize = 20) {
    return fetchJson(`/runs?page=${page}&page_size=${pageSize}&exclude_hubs=true`);
}

async function fetchInventory(sortBy = inventorySortBy, sortOrder = inventorySortOrder) {
    return fetchJson(`/inventory?sort_by=${sortBy}&sort_order=${sortOrder}`);
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

async function fetchCloudPriceHistory(configBaseId) {
    return fetchJson(`/cloud/prices/${configBaseId}/history`);
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

function renderStats(stats, inventory) {
    document.getElementById('net-worth').textContent = formatNumber(Math.round(inventory?.net_worth_fe || 0));
    document.getElementById('value-per-hour').textContent = formatNumber(Math.round(stats?.value_per_hour || 0));
    document.getElementById('value-per-map').textContent = formatNumber(Math.round(stats?.avg_value_per_run || 0));
    document.getElementById('total-runs').textContent = formatNumber(stats?.total_runs || 0);

    // Calculate and display average run time
    const avgRunTime = (stats?.total_runs > 0 && stats?.total_duration_seconds > 0)
        ? stats.total_duration_seconds / stats.total_runs
        : null;
    document.getElementById('avg-run-time').textContent = formatDuration(avgRunTime);
}

function renderRuns(data, forceRender = false) {
    const newHash = simpleHash(data?.runs?.map(r => ({ id: r.id, val: r.total_value, dur: r.duration_seconds })));
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
        const consolidatedInfo = run.consolidated_run_ids ? ` (${run.consolidated_run_ids.length} segments)` : '';
        return `
            <tr class="${nightmareClass}">
                <td class="zone-name" title="${run.zone_signature}${consolidatedInfo}">${escapeHtml(run.zone_name)}</td>
                <td class="duration">${formatDuration(run.duration_seconds)}</td>
                <td>${formatValue(run.total_value)}</td>
                <td>
                    <button class="expand-btn" onclick="showRunDetails(${run.id})">
                        Details
                    </button>
                </td>
            </tr>
        `;
    }).join('');
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
        const hasCloudPrice = cloudPrice && cloudPrice.unique_devices >= 3;

        // Cloud price indicator
        const cloudIndicator = hasCloudPrice
            ? `<span class="cloud-price-indicator" title="Community price (${cloudPrice.unique_devices} contributors)"></span>`
            : '';

        // Sparkline cell (only if cloud sync enabled)
        const sparklineCell = cloudSyncEnabled
            ? `<td class="sparkline-cell" onclick="showPriceHistory(${item.config_base_id}, '${escapeHtml(item.name).replace(/'/g, "\\'")}')">
                ${hasCloudPrice ? '<canvas class="sparkline" data-config-id="' + item.config_base_id + '"></canvas>' : '<div class="sparkline-placeholder"></div>'}
               </td>`
            : '';

        return `
            <tr>
                <td>
                    <div class="item-row">
                        ${iconHtml}
                        <span class="item-name ${isFE ? 'fe' : ''}">${escapeHtml(item.name)}${cloudIndicator}</span>
                    </div>
                </td>
                <td>${formatNumber(item.quantity)}</td>
                <td>${item.total_value_fe ? formatFEValue(item.total_value_fe) : '--'}</td>
                ${sparklineCell}
            </tr>
        `;
    }).join('');

    // Render sparklines after DOM update
    if (cloudSyncEnabled) {
        requestAnimationFrame(() => renderSparklines());
    }
}

function renderSparklines() {
    const sparklines = document.querySelectorAll('.sparkline[data-config-id]');
    sparklines.forEach(canvas => {
        const configId = parseInt(canvas.dataset.configId);
        const cloudPrice = cloudPricesCache[configId];
        if (!cloudPrice) return;

        // For now, just show a simple indicator based on recent trend
        // Full sparkline would need history data per item
        renderSimpleSparkline(canvas, cloudPrice);
    });
}

function renderSimpleSparkline(canvas, cloudPrice) {
    const ctx = canvas.getContext('2d');
    const width = canvas.offsetWidth || 60;
    const height = canvas.offsetHeight || 24;

    canvas.width = width;
    canvas.height = height;

    // Simple placeholder visualization
    // In a full implementation, this would fetch per-item history
    ctx.strokeStyle = '#4ecca3';
    ctx.lineWidth = 1.5;
    ctx.beginPath();

    // Draw a simple line representing the price
    const midY = height / 2;
    ctx.moveTo(0, midY);
    ctx.lineTo(width, midY);
    ctx.stroke();

    // Draw dot for current price
    ctx.fillStyle = '#4ecca3';
    ctx.beginPath();
    ctx.arc(width - 4, midY, 3, 0, Math.PI * 2);
    ctx.fill();
}

function renderStatus(status) {
    const indicator = document.getElementById('status-indicator');
    const collectorStatus = document.getElementById('collector-status');

    if (status?.collector_running) {
        indicator.classList.add('active');
        collectorStatus.textContent = 'Collector: Running';
    } else {
        indicator.classList.remove('active');
        collectorStatus.textContent = 'Collector: Stopped';
    }

    // Show/hide awaiting player message
    const awaitingMessage = document.getElementById('awaiting-player-message');
    if (awaitingMessage) {
        if (status?.awaiting_player && !status?.log_path_missing) {
            awaitingMessage.classList.remove('hidden');
        } else {
            awaitingMessage.classList.add('hidden');
        }
    }

    // Show log path configuration modal if log file not found
    if (status?.log_path_missing) {
        showLogPathModal();
    }
}

function renderPlayer(player) {
    const playerInfo = document.getElementById('player-info');
    const playerName = document.getElementById('player-name');
    const playerDetails = document.getElementById('player-details');

    if (player) {
        playerName.textContent = player.name;
        playerDetails.textContent = player.season_name;
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
        for (const price of data.prices) {
            cloudPricesCache[price.config_base_id] = price;
        }
    }
}

// --- No Character Modal ---

let noCharacterModalShown = false;

function showNoCharacterModal() {
    // Only show once per session
    if (noCharacterModalShown) return;
    noCharacterModalShown = true;
    document.getElementById('no-character-modal').classList.remove('hidden');
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

// --- Log Path Configuration Modal ---

let logPathModalShown = false;
let validatedLogPath = null;

function showLogPathModal() {
    // Only show once per session
    if (logPathModalShown) return;
    logPathModalShown = true;
    document.getElementById('log-path-modal').classList.remove('hidden');
}

function closeLogPathModal() {
    document.getElementById('log-path-modal').classList.add('hidden');
}

// Close log-path modal on outside click
document.addEventListener('click', (e) => {
    if (e.target.id === 'log-path-modal') {
        closeLogPathModal();
    }
});

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

// Chart configuration
const chartOptions = {
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
        x: {
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
        },
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

function renderCharts(data, forceRender = false) {
    const newHash = simpleHash(data);
    if (!forceRender && newHash === lastStatsHash) {
        return; // No change
    }
    lastStatsHash = newHash;

    // Prepare data for cumulative value chart
    const cumulativeValueData = (data?.cumulative_value || []).map(p => ({
        x: new Date(p.timestamp),
        y: p.value,
    }));

    // Prepare data for value/hour chart
    const valueRateData = (data?.value_per_hour || []).map(p => ({
        x: new Date(p.timestamp),
        y: p.value,
    }));

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

    title.textContent = `${run.zone_name} - ${formatDuration(run.duration_seconds)}`;

    if (!run.loot || run.loot.length === 0) {
        body.innerHTML = '<p>No loot recorded for this run.</p>';
    } else {
        body.innerHTML = `
            <ul class="loot-list">
                ${run.loot.map(item => {
                    const iconHtml = getIconHtml(item.config_base_id, 'loot-item-icon');
                    const qtyStr = (item.quantity > 0 ? '+' : '') + formatNumber(item.quantity);
                    const valueStr = item.total_value_fe !== null
                        ? `= ${item.total_value_fe.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} FE`
                        : '<span class="no-price">no price</span>';
                    return `
                        <li class="loot-item">
                            <div class="loot-item-name">
                                ${iconHtml}
                                <span>${escapeHtml(item.name)}</span>
                            </div>
                            <div class="loot-item-values">
                                <span class="loot-item-qty ${item.quantity > 0 ? 'positive' : 'negative'}">${qtyStr}</span>
                                <span class="loot-item-value">${valueStr}</span>
                            </div>
                        </li>
                    `;
                }).join('')}
            </ul>
        `;
    }

    modal.classList.remove('hidden');
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
        closePriceHistoryModal();
        closeLogPathModal();
    }
});

// --- Price History Modal ---

async function showPriceHistory(configBaseId, itemName) {
    const modal = document.getElementById('price-history-modal');
    const title = document.getElementById('price-history-title');
    const chartCanvas = document.getElementById('price-history-chart');

    title.textContent = `Price History: ${itemName}`;

    // Show loading state
    document.getElementById('price-stat-median').textContent = '...';
    document.getElementById('price-stat-p10').textContent = '...';
    document.getElementById('price-stat-p90').textContent = '...';
    document.getElementById('price-stat-contributors').textContent = '...';

    modal.classList.remove('hidden');

    // Fetch history data
    const data = await fetchCloudPriceHistory(configBaseId);

    if (!data || !data.history || data.history.length === 0) {
        // No history available
        if (priceHistoryChart) {
            priceHistoryChart.destroy();
            priceHistoryChart = null;
        }
        document.getElementById('price-stat-median').textContent = 'No data';
        document.getElementById('price-stat-p10').textContent = '--';
        document.getElementById('price-stat-p90').textContent = '--';
        document.getElementById('price-stat-contributors').textContent = '--';
        return;
    }

    // Prepare chart data
    const chartData = data.history.map(h => ({
        x: new Date(h.hour_bucket),
        y: h.price_fe_median
    }));

    const p10Data = data.history.map(h => ({
        x: new Date(h.hour_bucket),
        y: h.price_fe_p10 || h.price_fe_median
    }));

    const p90Data = data.history.map(h => ({
        x: new Date(h.hour_bucket),
        y: h.price_fe_p90 || h.price_fe_median
    }));

    // Update stats from latest point
    const latest = data.history[data.history.length - 1];
    document.getElementById('price-stat-median').textContent = formatFEValue(latest.price_fe_median);
    document.getElementById('price-stat-p10').textContent = latest.price_fe_p10 ? formatFEValue(latest.price_fe_p10) : '--';
    document.getElementById('price-stat-p90').textContent = latest.price_fe_p90 ? formatFEValue(latest.price_fe_p90) : '--';

    // Get contributors from cloud cache
    const cloudPrice = cloudPricesCache[configBaseId];
    document.getElementById('price-stat-contributors').textContent = cloudPrice?.unique_devices || '--';

    // Create or update chart
    if (priceHistoryChart) {
        priceHistoryChart.destroy();
    }

    priceHistoryChart = new Chart(chartCanvas, {
        type: 'line',
        data: {
            datasets: [
                {
                    label: 'Median',
                    data: chartData,
                    borderColor: '#e94560',
                    backgroundColor: 'rgba(233, 69, 96, 0.1)',
                    fill: false,
                    tension: 0.3,
                    pointRadius: 2,
                    pointHoverRadius: 5,
                },
                {
                    label: 'P10 (Low)',
                    data: p10Data,
                    borderColor: 'rgba(78, 204, 163, 0.5)',
                    backgroundColor: 'rgba(78, 204, 163, 0.1)',
                    fill: '+1',
                    tension: 0.3,
                    pointRadius: 0,
                    borderDash: [5, 5],
                },
                {
                    label: 'P90 (High)',
                    data: p90Data,
                    borderColor: 'rgba(255, 107, 107, 0.5)',
                    backgroundColor: 'transparent',
                    fill: false,
                    tension: 0.3,
                    pointRadius: 0,
                    borderDash: [5, 5],
                }
            ],
        },
        options: {
            ...chartOptions,
            plugins: {
                ...chartOptions.plugins,
                legend: {
                    display: true,
                    position: 'top',
                    labels: {
                        color: '#a0a0a0',
                        usePointStyle: true,
                    }
                },
                tooltip: {
                    ...chartOptions.plugins.tooltip,
                    callbacks: {
                        label: (ctx) => `${ctx.dataset.label}: ${formatFEValue(ctx.parsed.y)} FE`,
                    },
                },
            },
        },
    });
}

function closePriceHistoryModal() {
    document.getElementById('price-history-modal').classList.add('hidden');
}

// Close price history modal on outside click
document.addEventListener('click', (e) => {
    if (e.target.id === 'price-history-modal') {
        closePriceHistoryModal();
    }
});

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
        const [status, stats, runs, inventory, statsHistory, player, cloudStatus] = await Promise.all([
            fetchStatus(),
            fetchStats(),
            fetchRuns(),
            fetchInventory(),
            fetchStatsHistory(24),
            fetchPlayer(),
            fetchCloudStatus()
        ]);

        lastRunsData = runs;
        lastInventoryData = inventory;

        renderStatus(status);
        renderStats(stats, inventory);
        renderCloudStatus(cloudStatus);
        renderRuns(runs, forceRender);

        // Load cloud prices if sync is enabled
        if (cloudStatus && cloudStatus.enabled && Object.keys(cloudPricesCache).length === 0) {
            await loadCloudPrices();
        }

        renderInventory(inventory, forceRender);
        renderCharts(statsHistory, forceRender);

        // Check if player changed and update display
        const playerHash = simpleHash(player);
        if (forceRender || playerHash !== lastPlayerHash) {
            renderPlayer(player);
            lastPlayerHash = playerHash;

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
    btn.textContent = 'Resetting...';

    const result = await postResetStats();

    btn.disabled = false;
    btn.textContent = 'Reset Stats';

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
            } else if (status.status === 'error') {
                alert('Update check failed: ' + (status.error_message || 'Unknown error'));
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

function showUpdateModal(status) {
    const modal = document.getElementById('update-modal');
    const currentVersionEl = document.getElementById('update-current-version');
    const newVersionEl = document.getElementById('update-new-version');
    const releaseNotesEl = document.getElementById('update-release-notes');
    const progressContainer = document.getElementById('update-progress-container');
    const actionsEl = document.getElementById('update-actions');

    currentVersionEl.textContent = `v${status.current_version}`;
    newVersionEl.textContent = `v${status.latest_version}`;

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

// --- Initialization ---

document.addEventListener('DOMContentLoaded', async () => {
    // Set initial sort indicators
    updateSortIndicators();

    // Fetch and display version info
    const versionStatus = await fetchUpdateStatus();
    updateStatus = versionStatus;
    renderVersion(versionStatus);

    // Fetch player info initially
    const player = await fetchPlayer();
    renderPlayer(player);
    lastPlayerHash = simpleHash(player);

    // Show warning modal if no character detected
    if (!player) {
        showNoCharacterModal();
    }

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
