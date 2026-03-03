// Global state
let currentSellPosition = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', function () {
    refreshAll();
    // Auto-refresh every 30 seconds
    setInterval(() => {
        loadStatus();
        loadPortfolioStats();
        loadPositions();
    }, 30000);
});

// ============================================================================
// BOT CONTROL FUNCTIONS
// ============================================================================

async function startBot() {
    try {
        const response = await fetch('/api/bot/start', {
            method: 'POST'
        });

        const data = await response.json();

        if (data.success) {
            document.getElementById('startBtn').disabled = true;
            document.getElementById('stopBtn').disabled = false;
            showNotification('Bot started successfully', 'success');
            setTimeout(loadStatus, 1000);
        } else {
            showNotification(data.error || 'Failed to start bot', 'error');
        }
    } catch (error) {
        showNotification('Error starting bot: ' + error.message, 'error');
    }
}

async function stopBot() {
    try {
        const response = await fetch('/api/bot/stop', {
            method: 'POST'
        });

        const data = await response.json();

        if (data.success) {
            document.getElementById('startBtn').disabled = false;
            document.getElementById('stopBtn').disabled = true;
            showNotification('Bot stopped', 'info');
            setTimeout(loadStatus, 1000);
        } else {
            showNotification(data.error || 'Failed to stop bot', 'error');
        }
    } catch (error) {
        showNotification('Error stopping bot: ' + error.message, 'error');
    }
}

async function toggleDryRun() {
    const dryRun = document.getElementById('dryRunToggle').checked;

    try {
        const response = await fetch('/api/bot/dry-run', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ dry_run: dryRun })
        });

        const data = await response.json();

        if (data.success) {
            showNotification(dryRun ? 'Dry run mode enabled' : 'Live trading enabled', 'info');
        }
    } catch (error) {
        showNotification('Error toggling dry run: ' + error.message, 'error');
    }
}

// ============================================================================
// DATA LOADING FUNCTIONS
// ============================================================================

async function loadStatus() {
    try {
        const response = await fetch('/api/status');
        const status = await response.json();

        const indicator = document.getElementById('statusIndicator');
        const text = document.getElementById('statusText');

        if (status.running) {
            indicator.className = 'status-indicator running';
            text.textContent = 'Bot Running';
            document.getElementById('startBtn').disabled = true;
            document.getElementById('stopBtn').disabled = false;
        } else {
            indicator.className = 'status-indicator stopped';
            text.textContent = status.message || 'Bot Stopped';
            document.getElementById('startBtn').disabled = false;
            document.getElementById('stopBtn').disabled = true;
        }

        // Update dry run toggle
        document.getElementById('dryRunToggle').checked = status.dry_run || false;

        // Update accounts badge
        const trackedCount = status.tracked_accounts || 0;
        const enabledCount = status.enabled_accounts || 0;
        const badge = document.getElementById('accountsBadge');
        badge.textContent = `${enabledCount} of ${trackedCount} Accounts Active`;

    } catch (error) {
        console.error('Error loading status:', error);
    }
}

async function loadPortfolioStats() {
    try {
        const response = await fetch('/api/portfolio');
        const stats = await response.json();
        if (document.getElementById('accountBalance')) {
            document.getElementById('accountBalance').textContent = formatCurrency(stats.account_balance || 0);
        }

        document.getElementById('openPositions').textContent = stats.open_positions;
        document.getElementById('totalValue').textContent = formatCurrency(stats.total_current_value);

        const unrealizedEl = document.getElementById('unrealizedPnl');
        unrealizedEl.textContent = formatCurrency(stats.unrealized_pnl);
        unrealizedEl.className = 'stat-value ' + (stats.unrealized_pnl >= 0 ? 'positive' : 'negative');

        const realizedEl = document.getElementById('realizedPnl');
        realizedEl.textContent = formatCurrency(stats.realized_pnl);
        realizedEl.className = 'stat-value ' + (stats.realized_pnl >= 0 ? 'positive' : 'negative');

        const totalPnlEl = document.getElementById('totalPnl');
        totalPnlEl.textContent = formatCurrency(stats.total_pnl);
        totalPnlEl.className = 'stat-value ' + (stats.total_pnl >= 0 ? 'positive' : 'negative');

        document.getElementById('totalWithdrawn').textContent = formatCurrency(stats.total_withdrawn);

    } catch (error) {
        console.error('Error loading portfolio stats:', error);
    }
}

async function loadPositions() {
    try {
        const response = await fetch('/api/positions');
        const positions = await response.json();

        const container = document.getElementById('positionsList');

        if (positions.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">📭</div>
                    <p>No open positions</p>
                </div>
            `;
            return;
        }

        container.innerHTML = `
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Market</th>
                        <th>Outcome</th>
                        <th>Cost</th>
                        <th>Value</th>
                        <th>P&L</th>
                        <th style="text-align: right;">Actions</th>
                    </tr>
                </thead>
                <tbody>
                    ${positions.map(pos => `
                        <tr>
                            <td>
                                <div style="font-weight: 600; color: #fff; max-width: 250px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="${escapeHtml(pos.title || 'Unknown Market')}">
                                    ${escapeHtml(pos.title || 'Unknown Market')}
                                </div>
                            </td>
                            <td>
                                <div style="font-weight: 500;">${escapeHtml(pos.outcome || 'Unknown')}</div>
                                <div style="font-size: 11px; color: var(--text-dim);">${pos.size.toFixed(2)} sh</div>
                            </td>
                            <td>${formatCurrency(pos.cost_basis)}</td>
                            <td>
                                <div style="font-weight: 600;">${formatCurrency(pos.current_value)}</div>
                            </td>
                            <td>
                                <div class="${pos.pnl >= 0 ? 'positive' : 'negative'}">
                                    ${formatCurrency(pos.pnl)}
                                </div>
                                <div class="${pos.pnl >= 0 ? 'positive' : 'negative'}" style="font-size: 11px;">
                                    ${pos.pnl_percent >= 0 ? '+' : ''}${pos.pnl_percent.toFixed(2)}%
                                </div>
                            </td>
                            <td style="text-align: right;">
                                <div style="display: flex; gap: 8px; justify-content: flex-end;">
                                    <button class="btn btn-secondary btn-sm" style="padding: 6px 12px; font-size: 11px;" onclick='showPartialSellModal(${JSON.stringify(pos)})'>
                                        Sell
                                    </button>
                                    <button class="btn btn-danger btn-sm" style="padding: 6px 12px; font-size: 11px;" onclick='closeFullPosition(${JSON.stringify(pos)})'>
                                        Close
                                    </button>
                                </div>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;

    } catch (error) {
        console.error('Error loading positions:', error);
        document.getElementById('positionsList').innerHTML = `
            <div class="empty-state">
                <p style="color: #f56565;">Error loading positions</p>
            </div>
        `;
    }
}

async function loadAccounts() {
    try {
        const response = await fetch('/api/accounts');
        const accounts = await response.json();

        const container = document.getElementById('accountsList');

        if (accounts.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">👥</div>
                    <p>No accounts configured. Add an account to start tracking trades.</p>
                </div>
            `;
            return;
        }

        // Load status to get per-account stats
        const statusResponse = await fetch('/api/status');
        const status = await statusResponse.json();
        const accountStats = status.stats?.accounts || {};

        container.innerHTML = accounts.map(account => {
            const stats = accountStats[account.address] || {};
            const enabled = account.enabled !== false;

            return `
                <div class="account-card ${!enabled ? 'disabled' : ''}">
                    <div class="account-header">
                        <div class="account-info">
                            <div class="account-name" title="${escapeHtml(account.name || 'Unknown')}">
                                ${escapeHtml(account.name || 'Unknown')}
                                ${!enabled ? '<span class="techno-badge">Disabled</span>' : ''}
                            </div>
                            <div class="account-addr" title="${account.address}">
                                <span>${account.address.substring(0, 6)}...${account.address.substring(account.address.length - 4)}</span>
                                <span style="cursor: pointer; opacity: 0.7;" onclick="copyToClipboard('${account.address}')" title="Copy Address">📋</span>
                            </div>
                            ${(account.pnl !== undefined || account.winRate !== undefined) ? `
                                <div class="account-stats">
                                    <div class="stat-group">
                                        <span>PnL:</span>
                                        <span class="${account.pnl >= 0 ? 'positive' : 'negative'}">$${Math.abs(account.pnl || 0).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}</span>
                                    </div>
                                    <div class="stat-group">
                                        <span>WinRate:</span>
                                        <span style="color: #fff;">${((account.winRate || 0) * 100).toFixed(0)}%</span>
                                    </div>
                                    <div class="stat-group">
                                        <span>Rank:</span>
                                        <span style="color: #fff;">#${account.rank || '?'}</span>
                                    </div>
                                </div>
                            ` : ''}
                            ${(account.tags && account.tags.length > 0) ? `
                                <div class="account-tags">
                                    ${account.tags.map(tag => `<span class="account-tag">${escapeHtml(tag)}</span>`).join('')}
                                </div>
                            ` : ''}
                        </div>
                        <div class="account-actions">
                            <label class="toggle-switch">
                                <input type="checkbox" ${enabled ? 'checked' : ''} 
                                    onchange="toggleAccount('${account.address}', this.checked)">
                                <span class="slider"></span>
                            </label>
                            <button class="btn btn-danger btn-sm" onclick="removeAccount('${account.address}')">
                                Remove
                            </button>
                        </div>
                    </div>
                    <div class="account-stats">
                        <div class="detail-item">
                            <div class="detail-label">Trades Copied</div>
                            <div>${stats.trades_copied || 0}</div>
                        </div>
                        <div class="detail-item">
                            <div class="detail-label">Last Check</div>
                            <div>${stats.last_check ? formatTimestamp(stats.last_check) : 'Never'}</div>
                        </div>
                        ${account.bet_amount_override ? `
                            <div class="detail-item">
                                <div class="detail-label">Bet Amount Override</div>
                                <div>${formatCurrency(account.bet_amount_override)}</div>
                            </div>
                        ` : ''}
                        ${stats.last_trade ? `
                            <div class="detail-item" style="grid-column: 1 / -1;">
                                <div class="detail-label">Last Trade</div>
                                <div style="font-size: 12px;">${escapeHtml(stats.last_trade.title || 'Unknown')}</div>
                            </div>
                        ` : ''}
                    </div>
                </div>
            `;
        }).join('');

    } catch (error) {
        console.error('Error loading accounts:', error);
        document.getElementById('accountsList').innerHTML = `
            <div class="empty-state">
                <p style="color: #f56565;">Error loading accounts</p>
            </div>
        `;
    }
}

async function loadWithdrawals() {
    try {
        const response = await fetch('/api/withdrawals');
        const withdrawals = await response.json();

        const container = document.getElementById('withdrawalsList');

        if (withdrawals.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">💸</div>
                    <p>No withdrawals recorded</p>
                </div>
            `;
            return;
        }

        // Sort by date descending
        withdrawals.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));

        container.innerHTML = withdrawals.slice(0, 10).map(w => `
            <div class="position-card">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <div style="font-weight: 600; color: #2d3748;">
                            ${formatCurrency(w.amount)}
                        </div>
                        <div style="font-size: 13px; color: #718096; margin-top: 4px;">
                            ${w.date} ${w.note ? `• ${escapeHtml(w.note)}` : ''}
                        </div>
                    </div>
                </div>
            </div>
        `).join('');

        if (withdrawals.length > 10) {
            container.innerHTML += `
                <div style="text-align: center; padding: 12px; color: #718096; font-size: 13px;">
                    Showing 10 most recent withdrawals
                </div>
            `;
        }

    } catch (error) {
        console.error('Error loading withdrawals:', error);
    }
}

function refreshAll() {
    loadStatus();
    loadPortfolioStats();
    loadPositions();
    loadAccounts();
    loadWithdrawals();
}

// ============================================================================
// ACCOUNT MANAGEMENT FUNCTIONS
// ============================================================================

function showAddAccountModal() {
    document.getElementById('accountAddress').value = '';
    document.getElementById('accountName').value = '';
    document.getElementById('accountBetAmount').value = '';
    showModal('addAccountModal');
}

async function addAccount() {
    const address = document.getElementById('accountAddress').value.trim();
    const name = document.getElementById('accountName').value.trim();
    const betAmount = document.getElementById('accountBetAmount').value;

    if (!address) {
        showNotification('Please enter a wallet address', 'error');
        return;
    }

    try {
        const response = await fetch('/api/accounts', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                address: address,
                name: name || null,
                bet_amount: betAmount ? parseFloat(betAmount) : null
            })
        });

        const data = await response.json();

        if (data.success) {
            showNotification('Account added successfully', 'success');
            closeModal('addAccountModal');
            loadAccounts();
            loadStatus();
        } else {
            showNotification(data.error || 'Failed to add account', 'error');
        }
    } catch (error) {
        showNotification('Error adding account: ' + error.message, 'error');
    }
}

async function removeAccount(address) {
    if (!confirm('Are you sure you want to remove this account from tracking?')) {
        return;
    }

    try {
        const response = await fetch(`/api/accounts/${encodeURIComponent(address)}`, {
            method: 'DELETE'
        });

        const data = await response.json();

        if (data.success) {
            showNotification('Account removed', 'info');
            loadAccounts();
            loadStatus();
        } else {
            showNotification(data.error || 'Failed to remove account', 'error');
        }
    } catch (error) {
        showNotification('Error removing account: ' + error.message, 'error');
    }
}

async function toggleAccount(address, enabled) {
    try {
        const response = await fetch(`/api/accounts/${encodeURIComponent(address)}/toggle`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ enabled: enabled })
        });

        const data = await response.json();

        if (data.success) {
            showNotification(enabled ? 'Account enabled' : 'Account disabled', 'info');
            loadAccounts();
            loadStatus();
        } else {
            showNotification(data.error || 'Failed to toggle account', 'error');
        }
    } catch (error) {
        showNotification('Error toggling account: ' + error.message, 'error');
    }
}

// ============================================================================
// POSITION MANAGEMENT FUNCTIONS
// ============================================================================

function showPartialSellModal(position) {
    currentSellPosition = position;
    document.getElementById('sellPositionTitle').textContent = position.title;
    document.getElementById('sellMaxAmount').textContent = formatCurrency(position.current_value);
    document.getElementById('sellAmount').value = '';
    document.getElementById('sellAmount').max = position.current_value;
    showModal('partialSellModal');
}

async function executeSell() {
    if (!currentSellPosition) return;

    const amount = parseFloat(document.getElementById('sellAmount').value);

    if (!amount || amount <= 0) {
        showNotification('Please enter a valid amount', 'error');
        return;
    }

    if (amount > currentSellPosition.current_value) {
        showNotification('Amount exceeds position value', 'error');
        return;
    }

    // Calculate shares to sell
    const sharesToSell = amount / currentSellPosition.currentPrice;

    try {
        const response = await fetch('/api/position/close', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                token_id: currentSellPosition.asset,
                amount: sharesToSell,
                dry_run: document.getElementById('dryRunToggle').checked
            })
        });

        const data = await response.json();

        if (data.success) {
            showNotification(data.message, 'success');
            closeModal('partialSellModal');
            setTimeout(() => {
                loadPositions();
                loadPortfolioStats();
            }, 2000);
        } else {
            showNotification(data.error || 'Failed to sell position', 'error');
        }
    } catch (error) {
        showNotification('Error selling position: ' + error.message, 'error');
    }
}

async function closeFullPosition(position) {
    if (!confirm(`Close entire position in "${position.title}"?`)) {
        return;
    }

    try {
        const response = await fetch('/api/position/close', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                token_id: position.asset,
                amount: position.size,
                dry_run: document.getElementById('dryRunToggle').checked
            })
        });

        const data = await response.json();

        if (data.success) {
            showNotification(data.message, 'success');
            setTimeout(() => {
                loadPositions();
                loadPortfolioStats();
            }, 2000);
        } else {
            showNotification(data.error || 'Failed to close position', 'error');
        }
    } catch (error) {
        showNotification('Error closing position: ' + error.message, 'error');
    }
}

function showPanicSellModal() {
    showModal('panicSellModal');
}

async function executePanicSell() {
    try {
        const response = await fetch('/api/panic-sell', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                dry_run: document.getElementById('dryRunToggle').checked
            })
        });

        const data = await response.json();

        if (data.success) {
            showNotification(data.message, 'success');
            closeModal('panicSellModal');
            setTimeout(() => {
                loadPositions();
                loadPortfolioStats();
            }, 2000);
        } else {
            showNotification(data.error || 'Failed to execute panic sell', 'error');
        }
    } catch (error) {
        showNotification('Error executing panic sell: ' + error.message, 'error');
    }
}

// ============================================================================
// WITHDRAWAL FUNCTIONS
// ============================================================================

function showAddWithdrawalModal() {
    document.getElementById('withdrawalAmount').value = '';
    document.getElementById('withdrawalNote').value = '';
    showModal('addWithdrawalModal');
}

async function addWithdrawal() {
    const amount = parseFloat(document.getElementById('withdrawalAmount').value);
    const note = document.getElementById('withdrawalNote').value.trim();

    if (!amount || amount <= 0) {
        showNotification('Please enter a valid amount', 'error');
        return;
    }

    try {
        const response = await fetch('/api/withdrawals', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                amount: amount,
                note: note
            })
        });

        const data = await response.json();

        if (data.success) {
            showNotification('Withdrawal recorded', 'success');
            closeModal('addWithdrawalModal');
            loadWithdrawals();
            loadPortfolioStats();
        } else {
            showNotification(data.error || 'Failed to record withdrawal', 'error');
        }
    } catch (error) {
        showNotification('Error recording withdrawal: ' + error.message, 'error');
    }
}

function showSearchWithdrawalsModal() {
    showModal('searchWithdrawalsModal');
    document.getElementById('searchResults').innerHTML = '';
}

async function searchWithdrawals() {
    const startDate = document.getElementById('searchStartDate').value;
    const endDate = document.getElementById('searchEndDate').value;

    if (!startDate || !endDate) {
        showNotification('Please select both start and end dates', 'error');
        return;
    }

    try {
        const response = await fetch(`/api/withdrawals/search?start_date=${startDate}&end_date=${endDate}`);
        const data = await response.json();

        const resultsContainer = document.getElementById('searchResults');

        if (data.withdrawals.length === 0) {
            resultsContainer.innerHTML = `
                <div class="empty-state">
                    <p>No withdrawals found in this date range</p>
                </div>
            `;
            return;
        }

        resultsContainer.innerHTML = `
            <div style="background: #edf2f7; padding: 16px; border-radius: 8px; margin-bottom: 12px;">
                <div style="font-weight: 600; color: #2d3748; margin-bottom: 8px;">
                    Search Results
                </div>
                <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; font-size: 14px;">
                    <div>
                        <span style="color: #718096;">Total Withdrawals:</span>
                        <strong>${data.count}</strong>
                    </div>
                    <div>
                        <span style="color: #718096;">Total Amount:</span>
                        <strong>${formatCurrency(data.total)}</strong>
                    </div>
                </div>
            </div>
            ${data.withdrawals.map(w => `
                <div class="position-card">
                    <div style="display: flex; justify-content: space-between;">
                        <div>
                            <div style="font-weight: 600;">${formatCurrency(w.amount)}</div>
                            <div style="font-size: 12px; color: #718096; margin-top: 4px;">
                                ${w.date} ${w.note ? `• ${escapeHtml(w.note)}` : ''}
                            </div>
                        </div>
                    </div>
                </div>
            `).join('')}
        `;

    } catch (error) {
        showNotification('Error searching withdrawals: ' + error.message, 'error');
    }
}

// ============================================================================
// EXPORT FUNCTIONS
// ============================================================================

async function exportPositions() {
    try {
        showNotification('Preparing Excel export...', 'info');

        const response = await fetch('/api/export/positions');

        if (!response.ok) {
            throw new Error('Export failed');
        }

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `polymarket_positions_${new Date().toISOString().split('T')[0]}.xlsx`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);

        showNotification('Positions exported successfully!', 'success');
    } catch (error) {
        showNotification('Error exporting positions: ' + error.message, 'error');
    }
}

async function exportHistory() {
    try {
        showNotification('Preparing Excel export...', 'info');

        const response = await fetch('/api/export/history');

        if (!response.ok) {
            throw new Error('Export failed');
        }

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `polymarket_history_${new Date().toISOString().split('T')[0]}.xlsx`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);

        showNotification('History exported successfully!', 'success');
    } catch (error) {
        showNotification('Error exporting history: ' + error.message, 'error');
    }
}

async function exportFullReport() {
    try {
        showNotification('Preparing comprehensive report...', 'info');

        const response = await fetch('/api/export/full');

        if (!response.ok) {
            throw new Error('Export failed');
        }

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `polymarket_full_report_${new Date().toISOString().split('T')[0]}.xlsx`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);

        showNotification('Full report exported successfully!', 'success');
    } catch (error) {
        showNotification('Error exporting report: ' + error.message, 'error');
    }
}

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

function showModal(modalId) {
    document.getElementById(modalId).style.display = 'block';
}

function closeModal(modalId) {
    document.getElementById(modalId).style.display = 'none';
}

// Close modal when clicking outside
window.onclick = function (event) {
    if (event.target.classList.contains('modal')) {
        event.target.style.display = 'none';
    }
}

function formatCurrency(amount) {
    return '$' + amount.toFixed(2);
}

function formatTimestamp(timestamp) {
    if (!timestamp) return 'Never';
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now - date;

    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);

    if (minutes < 1) return 'Just now';
    if (minutes < 60) return `${minutes}m ago`;
    if (hours < 24) return `${hours}h ago`;
    if (days < 7) return `${days}d ago`;

    return date.toLocaleDateString();
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

async function copyToClipboard(text) {
    try {
        await navigator.clipboard.writeText(text);
        showNotification('Address copied to clipboard', 'success');
    } catch (err) {
        showNotification('Failed to copy: ' + err.message, 'error');
    }
}

function showNotification(message, type = 'info') {
    // Simple notification system
    const notification = document.createElement('div');
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 16px 24px;
        border-radius: 8px;
        font-weight: 600;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        z-index: 10000;
        animation: slideIn 0.3s ease-out;
    `;

    const colors = {
        success: { bg: '#c6f6d5', text: '#22543d' },
        error: { bg: '#fed7d7', text: '#742a2a' },
        info: { bg: '#bee3f8', text: '#2c5282' },
        warning: { bg: '#feebc8', text: '#7c2d12' }
    };

    const color = colors[type] || colors.info;
    notification.style.background = color.bg;
    notification.style.color = color.text;
    notification.textContent = message;

    document.body.appendChild(notification);

    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease-out';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// Add animations
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(100%);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);
