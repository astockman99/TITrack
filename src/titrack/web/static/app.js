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

function exportPrices() {
    // Trigger download by opening the export URL
    window.location.href = `${API_BASE}/prices/export`;
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

    if (!data || !data.items || data.items.length === 0) {
        tbody.innerHTML = '<tr><td colspan="3" class="loading">No items in inventory</td></tr>';
        return;
    }

    tbody.innerHTML = data.items.slice(0, 20).map(item => {
        const isFE = item.config_base_id === 100300;
        const iconHtml = getIconHtml(item.config_base_id, 'item-icon');

        return `
            <tr>
                <td>
                    <div class="item-row">
                        ${iconHtml}
                        <span class="item-name ${isFE ? 'fe' : ''}">${escapeHtml(item.name)}</span>
                    </div>
                </td>
                <td>${formatNumber(item.quantity)}</td>
                <td>${item.total_value_fe ? formatFEValue(item.total_value_fe) : '--'}</td>
            </tr>
        `;
    }).join('');
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
        closeEditItemModal();
        closeHelpModal();
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

// --- Edit Item Modal ---

let currentEditItemId = null;

function openEditItemModal() {
    document.getElementById('edit-item-modal').classList.remove('hidden');
    document.getElementById('item-search-input').value = '';
    document.getElementById('item-search-results').innerHTML = '';
    document.getElementById('item-edit-form').classList.add('hidden');
    document.getElementById('item-search-input').focus();
}

function closeEditItemModal() {
    document.getElementById('edit-item-modal').classList.add('hidden');
    currentEditItemId = null;
}

// Close edit item modal on outside click
document.addEventListener('click', (e) => {
    if (e.target.id === 'edit-item-modal') {
        closeEditItemModal();
    }
});

function searchItems(event) {
    if (event.key === 'Enter') {
        performItemSearch();
    }
}

async function performItemSearch() {
    const query = document.getElementById('item-search-input').value.trim();
    if (!query) return;

    const resultsDiv = document.getElementById('item-search-results');
    resultsDiv.innerHTML = '<p class="loading">Searching...</p>';
    document.getElementById('item-edit-form').classList.add('hidden');

    // Check if query is a number (config_base_id)
    const isId = /^\d+$/.test(query);

    if (isId) {
        // Fetch single item by ID
        const item = await fetchJson(`/items/${query}`);
        if (item) {
            resultsDiv.innerHTML = '';
            showItemForEdit(item);
        } else {
            resultsDiv.innerHTML = `<p class="no-results">No item found with ID ${query}</p>`;
        }
    } else {
        // Search by name
        const data = await fetchJson(`/items?search=${encodeURIComponent(query)}&limit=20`);
        if (data && data.items && data.items.length > 0) {
            resultsDiv.innerHTML = data.items.map(item => `
                <div class="item-search-result" onclick="selectItemForEdit(${item.config_base_id})">
                    ${item.icon_url ? `<img src="${item.icon_url}" alt="" class="search-result-icon" onerror="this.style.display='none'">` : ''}
                    <span class="search-result-name">${escapeHtml(item.name_en || 'Unknown')}</span>
                    <span class="search-result-id">#${item.config_base_id}</span>
                </div>
            `).join('');
        } else {
            resultsDiv.innerHTML = '<p class="no-results">No items found</p>';
        }
    }
}

async function selectItemForEdit(configBaseId) {
    const item = await fetchJson(`/items/${configBaseId}`);
    if (item) {
        document.getElementById('item-search-results').innerHTML = '';
        showItemForEdit(item);
    }
}

function showItemForEdit(item) {
    currentEditItemId = item.config_base_id;

    const iconEl = document.getElementById('edit-item-icon');
    if (item.icon_url) {
        iconEl.src = item.icon_url;
        iconEl.style.display = 'block';
    } else {
        iconEl.style.display = 'none';
    }

    document.getElementById('edit-item-id').textContent = `#${item.config_base_id}`;
    document.getElementById('edit-item-current-name').textContent = item.name_en || 'Unknown';
    document.getElementById('edit-item-name').value = item.name_en || '';
    document.getElementById('item-edit-form').classList.remove('hidden');
    document.getElementById('edit-item-name').focus();
    document.getElementById('edit-item-name').select();
}

function cancelItemEdit() {
    document.getElementById('item-edit-form').classList.add('hidden');
    currentEditItemId = null;
}

async function saveItemName() {
    if (!currentEditItemId) return;

    const newName = document.getElementById('edit-item-name').value.trim();
    if (!newName) {
        alert('Please enter a name');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/items/${currentEditItemId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name_en: newName })
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const result = await response.json();

        // Update the display
        document.getElementById('edit-item-current-name').textContent = result.name_en;

        // Show success and refresh data
        alert(`Item updated: #${currentEditItemId} → "${newName}"\n\nPlease report this correction:\nID: ${currentEditItemId}\nName: ${newName}`);

        // Refresh the dashboard to show updated names
        await refreshAll(true);

    } catch (error) {
        console.error('Error saving item name:', error);
        alert('Failed to save item name. Please try again.');
    }
}

// --- Data Refresh ---

async function refreshAll(forceRender = false) {
    try {
        const [status, stats, runs, inventory, statsHistory, player] = await Promise.all([
            fetchStatus(),
            fetchStats(),
            fetchRuns(),
            fetchInventory(),
            fetchStatsHistory(24),
            fetchPlayer()
        ]);

        lastRunsData = runs;
        lastInventoryData = inventory;

        renderStatus(status);
        renderStats(stats, inventory);
        renderRuns(runs, forceRender);
        renderInventory(inventory, forceRender);
        renderCharts(statsHistory, forceRender);

        // Check if player changed and update display
        const playerHash = simpleHash(player);
        if (forceRender || playerHash !== lastPlayerHash) {
            renderPlayer(player);
            lastPlayerHash = playerHash;
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

// --- Initialization ---

document.addEventListener('DOMContentLoaded', async () => {
    // Set initial sort indicators
    updateSortIndicators();

    // Fetch player info initially
    const player = await fetchPlayer();
    renderPlayer(player);
    lastPlayerHash = simpleHash(player);

    // Show warning modal if no character detected
    if (!player) {
        showNoCharacterModal();
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
