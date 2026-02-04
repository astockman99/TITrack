// TITrack Mini-Overlay JavaScript

const API_BASE = '/api';
const REFRESH_INTERVAL = 2000; // 2 seconds for responsive updates

let refreshTimer = null;
let isTransparent = false;
const failedIcons = new Set();

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

async function fetchStats() {
    return fetchJson('/runs/stats');
}

async function fetchInventory() {
    return fetchJson('/inventory');
}

async function fetchActiveRun() {
    return fetchJson('/runs/active');
}

async function fetchTransparencySetting() {
    try {
        const response = await fetch(`${API_BASE}/settings/overlay_transparent`);
        if (!response.ok) return false;
        const data = await response.json();
        return data.value === 'true';
    } catch (error) {
        return false;
    }
}

async function saveTransparencySetting(enabled) {
    try {
        await fetch(`${API_BASE}/settings/overlay_transparent`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ value: enabled ? 'true' : 'false' })
        });
    } catch (error) {
        console.error('Error saving transparency setting:', error);
    }
}

// --- Formatting ---

function formatDuration(seconds) {
    if (!seconds) return '--';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}m ${secs}s`;
}

function formatDurationShort(seconds) {
    if (!seconds) return '--';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `(${mins}:${secs.toString().padStart(2, '0')})`;
}

function formatDurationLong(seconds) {
    if (!seconds) return '--';
    const hours = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    if (hours > 0) {
        return `${hours}h ${mins}m`;
    }
    return `${mins}m`;
}

function formatNumber(num) {
    if (num === null || num === undefined) return '--';
    return num.toLocaleString();
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

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function handleIconError(img) {
    if (img.dataset.configId) {
        failedIcons.add(img.dataset.configId);
    }
    img.style.display = 'none';
}

function getIconHtml(configBaseId) {
    if (!configBaseId || failedIcons.has(String(configBaseId))) {
        return '';
    }
    const proxyUrl = `/api/icons/${configBaseId}`;
    return `<img src="${proxyUrl}" alt="" class="loot-icon" data-config-id="${configBaseId}" onerror="handleIconError(this)">`;
}

// --- Rendering ---

function renderStats(stats, inventory, activeRun) {
    document.getElementById('net-worth').textContent = formatNumber(Math.round(inventory?.net_worth_fe || 0));
    document.getElementById('value-per-hour').textContent = formatNumber(Math.round(stats?.value_per_hour || 0));
    document.getElementById('value-per-map').textContent = formatNumber(Math.round(stats?.avg_value_per_run || 0));
    document.getElementById('total-runs').textContent = formatNumber(stats?.total_runs || 0);

    // Current run value in stats grid
    const currentRunValueEl = document.getElementById('current-run-value');
    if (activeRun) {
        const runValue = activeRun.net_value_fe !== null && activeRun.net_value_fe !== undefined
            ? activeRun.net_value_fe
            : activeRun.total_value;
        currentRunValueEl.innerHTML = formatValue(runValue || 0);
    } else {
        currentRunValueEl.textContent = '--';
    }

    const avgRunTime = (stats?.total_runs > 0 && stats?.total_duration_seconds > 0)
        ? stats.total_duration_seconds / stats.total_runs
        : null;
    document.getElementById('avg-run-time').textContent = formatDuration(avgRunTime);
    document.getElementById('total-time').textContent = formatDurationLong(stats?.total_duration_seconds);
}

function renderActiveRun(data) {
    const panel = document.getElementById('active-run-panel');
    const noRunPanel = document.getElementById('no-active-run');
    const zoneEl = document.getElementById('active-run-zone');
    const durationEl = document.getElementById('active-run-duration');
    const lootEl = document.getElementById('active-run-loot');

    if (!data) {
        panel.classList.add('hidden');
        noRunPanel.style.display = 'flex';
        return;
    }

    panel.classList.remove('hidden');
    noRunPanel.style.display = 'none';

    zoneEl.textContent = data.zone_name;
    durationEl.textContent = formatDurationShort(data.duration_seconds);

    // Render loot items - top 10 by value
    if (!data.loot || data.loot.length === 0) {
        lootEl.innerHTML = '<div class="no-run"><span class="no-run-text">No drops yet...</span></div>';
    } else {
        // Sort by total_value_fe descending
        const sortedLoot = [...data.loot].sort((a, b) => {
            const aVal = a.total_value_fe || 0;
            const bVal = b.total_value_fe || 0;
            return bVal - aVal;
        });

        // Take top 10
        const topLoot = sortedLoot.slice(0, 10);

        lootEl.innerHTML = topLoot.map(item => {
            const isNegative = item.quantity < 0;
            const negativeClass = isNegative ? ' negative' : '';
            const qtyPrefix = item.quantity > 0 ? '+' : '';
            const valueText = item.total_value_fe ? formatValue(item.total_value_fe) : '--';
            const iconHtml = getIconHtml(item.config_base_id);

            return `
                <div class="loot-item${negativeClass}">
                    ${iconHtml}
                    <span class="loot-name">${escapeHtml(item.name)}</span>
                    <span class="loot-qty">${qtyPrefix}${item.quantity}</span>
                    <span class="loot-value">${valueText}</span>
                </div>
            `;
        }).join('');
    }
}

// --- Transparency Toggle ---

async function toggleTransparency() {
    isTransparent = !isTransparent;
    await applyTransparency(isTransparent);
    // Save preference
    saveTransparencySetting(isTransparent);
}

async function applyTransparency(enabled) {
    // Update CSS classes
    document.body.classList.toggle('opaque', !enabled);
    document.body.classList.toggle('transparent', enabled);

    // Update icon
    const icon = document.getElementById('transparency-icon');
    icon.textContent = enabled ? 'O' : 'T';

    // Call pywebview API to enable/disable WinForms chroma key
    if (window.pywebview && window.pywebview.api && window.pywebview.api.toggle_overlay_transparency) {
        try {
            await window.pywebview.api.toggle_overlay_transparency(enabled);
        } catch (error) {
            console.error('Error toggling transparency:', error);
        }
    }
}

// --- Close Overlay ---

function closeOverlay() {
    // Try pywebview API first
    if (window.pywebview && window.pywebview.api && window.pywebview.api.close_overlay) {
        window.pywebview.api.close_overlay();
    } else {
        // Fallback: just close the window
        window.close();
    }
}

// --- Data Refresh ---

async function refreshAll() {
    try {
        const [stats, inventory, activeRun] = await Promise.all([
            fetchStats(),
            fetchInventory(),
            fetchActiveRun()
        ]);

        renderStats(stats, inventory, activeRun);
        renderActiveRun(activeRun);
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

// --- Initialization ---

document.addEventListener('DOMContentLoaded', async () => {
    // Check for ?transparent=1 query parameter (used by MSHTML backend)
    const urlParams = new URLSearchParams(window.location.search);
    const forceTransparent = urlParams.get('transparent') === '1';

    if (forceTransparent) {
        // MSHTML mode: apply transparent CSS immediately, chroma key applied by Python
        isTransparent = true;
        document.body.classList.remove('opaque');
        document.body.classList.add('transparent');
        document.getElementById('transparency-icon').textContent = 'O';
    } else {
        // Normal mode: load transparency preference and apply it
        isTransparent = await fetchTransparencySetting();

        // Wait a moment for pywebview API to be ready, then apply transparency
        // pywebview injects the API after DOM ready, so we need a small delay
        setTimeout(async () => {
            await applyTransparency(isTransparent);
        }, 100);
    }

    // Initial data load
    await refreshAll();

    // Start auto-refresh
    startAutoRefresh();
});
