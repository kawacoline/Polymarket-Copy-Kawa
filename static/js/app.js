// Global state
let currentSellPosition = null;
let currentWalletView = 'grid-5';
window.allAccounts = [];
window.accountStats = {};
window.expandedNames = window.expandedNames || {};

function toggleWalletName(address) {
    window.expandedNames[address] = !window.expandedNames[address];
    renderAccounts();
}

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
        if (badge) badge.textContent = `${enabledCount} of ${trackedCount} Accounts Active`;

        // Update header stats
        const walletsStat = document.getElementById('header-stat-wallets');
        if (walletsStat) {
            walletsStat.textContent = (status.wallets_found || 0).toLocaleString();
        }

        const dbStat = document.getElementById('header-stat-db');
        if (dbStat) {
            dbStat.textContent = (status.db_records || 0).toLocaleString();
        }

        const eventsStat = document.getElementById('header-stat-events');
        if (eventsStat) {
            eventsStat.textContent = (status.events_session || 0).toLocaleString();
        }

        const lastTradeStat = document.getElementById('header-stat-last-trade');
        if (lastTradeStat) {
            if (status.last_trade_time) {
                lastTradeStat.textContent = formatTimestamp(status.last_trade_time * 1000).toLowerCase();
            } else {
                lastTradeStat.textContent = '--';
            }
        }

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
                <div class="flex flex-col items-center justify-center p-8 text-center text-muted-foreground bg-white/5 rounded-xl border border-white/5">
                    <div class="text-4xl mb-4 opacity-50">📭</div>
                    <p>No open positions</p>
                </div>
            `;
            return;
        }

        container.innerHTML = `
            <table class="w-full text-sm text-left whitespace-nowrap">
                <thead>
                    <tr class="group hover:bg-white/5 transition-colors">
                        <th class="px-4 py-3 font-semibold text-muted-foreground border-b border-border/50" class="px-4 py-3 font-semibold text-muted-foreground border-b border-border/50">Market</th>
                        <th class="px-4 py-3 font-semibold text-muted-foreground border-b border-border/50" class="px-4 py-3 font-semibold text-muted-foreground border-b border-border/50">Outcome</th>
                        <th class="px-4 py-3 font-semibold text-muted-foreground border-b border-border/50" class="px-4 py-3 font-semibold text-muted-foreground border-b border-border/50">Cost</th>
                        <th class="px-4 py-3 font-semibold text-muted-foreground border-b border-border/50" class="px-4 py-3 font-semibold text-muted-foreground border-b border-border/50">Value</th>
                        <th class="px-4 py-3 font-semibold text-muted-foreground border-b border-border/50" class="px-4 py-3 font-semibold text-muted-foreground border-b border-border/50">P&L</th>
                        <th class="px-4 py-3 font-semibold text-muted-foreground border-b border-border/50" style="text-align: right;">Actions</th>
                    </tr>
                </thead>
                <tbody>
                    ${positions.map(pos => `
                        <tr class="group hover:bg-white/5 transition-colors">
                            <td class="px-4 py-3 border-b border-white/5 group-hover:bg-white/5 transition-colors" class="px-4 py-3 border-b border-white/5 group-hover:bg-white/5 transition-colors">
                                <div style="font-weight: 600; color: #fff; max-width: 250px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="${escapeHtml(pos.title || 'Unknown Market')}">
                                    ${escapeHtml(pos.title || 'Unknown Market')}
                                </div>
                            </td>
                            <td class="px-4 py-3 border-b border-white/5 group-hover:bg-white/5 transition-colors" class="px-4 py-3 border-b border-white/5 group-hover:bg-white/5 transition-colors">
                                <div style="font-weight: 500;">${escapeHtml(pos.outcome || 'Unknown')}</div>
                                <div style="font-size: 11px; color: var(--text-dim);">${pos.size.toFixed(2)} sh</div>
                            </td>
                            <td class="px-4 py-3 border-b border-white/5 group-hover:bg-white/5 transition-colors" class="px-4 py-3 border-b border-white/5 group-hover:bg-white/5 transition-colors">${formatCurrency(pos.cost_basis)}</td>
                            <td class="px-4 py-3 border-b border-white/5 group-hover:bg-white/5 transition-colors" class="px-4 py-3 border-b border-white/5 group-hover:bg-white/5 transition-colors">
                                <div style="font-weight: 600;">${formatCurrency(pos.current_value)}</div>
                            </td>
                            <td class="px-4 py-3 border-b border-white/5 group-hover:bg-white/5 transition-colors" class="px-4 py-3 border-b border-white/5 group-hover:bg-white/5 transition-colors">
                                <div class="${pos.pnl >= 0 ? 'positive' : 'negative'}">
                                    ${formatCurrency(pos.pnl)}
                                </div>
                                <div class="${pos.pnl >= 0 ? 'positive' : 'negative'}" style="font-size: 11px;">
                                    ${pos.pnl_percent >= 0 ? '+' : ''}${pos.pnl_percent.toFixed(2)}%
                                </div>
                            </td>
                            <td class="px-4 py-3 border-b border-white/5 group-hover:bg-white/5 transition-colors" style="text-align: right;">
                                <div style="display: flex; gap: 8px; justify-content: flex-end;">
                                    <button class="inline-flex items-center justify-center rounded-md text-xs font-medium transition-colors border border-input bg-transparent shadow-sm hover:bg-accent hover:text-accent-foreground h-8 px-3" style="padding: 6px 12px; font-size: 11px;" onclick='showPartialSellModal(${JSON.stringify(pos)})'>
                                        Sell
                                    </button>
                                    <button class="inline-flex items-center justify-center rounded-md text-xs font-medium transition-colors bg-destructive text-destructive-foreground shadow-sm hover:bg-destructive/90 h-8 px-3" style="padding: 6px 12px; font-size: 11px;" onclick='closeFullPosition(${JSON.stringify(pos)})'>
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
            <div class="flex flex-col items-center justify-center p-8 text-center text-muted-foreground bg-white/5 rounded-xl border border-white/5">
                <p style="color: #f56565;">Error loading positions</p>
            </div>
        `;
    }
}

async function loadAccounts() {
    try {
        const response = await fetch('/api/accounts');
        window.allAccounts = await response.json();

        // Load status to get per-account stats
        const statusResponse = await fetch('/api/status');
        const status = await statusResponse.json();
        window.accountStats = status.stats?.accounts || {};

        renderAccounts();
    } catch (error) {
        console.error('Error loading accounts:', error);
        document.getElementById('accountsList').innerHTML = `
            <div class="flex flex-col items-center justify-center p-8 text-center text-muted-foreground bg-white/5 rounded-xl border border-white/5">
                <p style="color: #f56565;">Error loading accounts</p>
            </div>
        `;
    }
}

function filterWallets() {
    renderAccounts();
}

function setWalletView(viewClass) {
    currentWalletView = viewClass;

    // Update button states
    document.querySelectorAll('.view-btn').forEach(btn => {
        if (btn.dataset.view === viewClass) {
            btn.classList.remove('hover:bg-white/10', 'text-muted-foreground');
            btn.classList.add('bg-white/10', 'text-foreground');
        } else {
            btn.classList.add('hover:bg-white/10', 'text-muted-foreground');
            btn.classList.remove('bg-white/10', 'text-foreground');
        }
    });

    renderAccounts();
}

function renderAccounts() {
    const container = document.getElementById('accountsList');
    const badge = document.getElementById('walletCountBadge');
    const searchInput = document.getElementById('walletSearchInput');
    const searchTerm = searchInput ? searchInput.value.toLowerCase() : '';

    // Filter
    const filteredAccounts = window.allAccounts.filter(account => {
        const nameMatch = (account.name || '').toLowerCase().includes(searchTerm);
        const addrMatch = (account.address || '').toLowerCase().includes(searchTerm);
        const tagMatch = (account.tags || []).some(t => t.toLowerCase().includes(searchTerm));
        return nameMatch || addrMatch || tagMatch;
    });

    if (badge) badge.textContent = `(${filteredAccounts.length} targets)`;

    if (filteredAccounts.length === 0) {
        container.className = "grid grid-cols-1";
        container.innerHTML = `
            <div class="flex flex-col items-center justify-center p-8 text-center text-muted-foreground bg-white/5 rounded-xl border border-white/5">
                <div class="text-4xl mb-4 opacity-50">👥</div>
                <p>${searchTerm ? 'No accounts match your search.' : 'No accounts configured. Add an account to start tracking trades.'}</p>
            </div>
        `;
        return;
    }

    // Apply grid class based on currentWalletView
    let gridClass = "grid gap-4 ";
    if (currentWalletView === 'grid-3') gridClass += "grid-cols-1 md:grid-cols-2 lg:grid-cols-3";
    else if (currentWalletView === 'grid-compact') gridClass = "flex flex-col gap-2";
    else gridClass += "grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6"; // Default/grid-5

    container.className = gridClass;

    const accountStats = window.accountStats;

    container.innerHTML = filteredAccounts.map(account => {
        const stats = accountStats[account.address] || {};
        const enabled = account.enabled !== false;
        const fullName = account.name || 'Unknown';
        const isExpanded = window.expandedNames[account.address];
        const needsTruncation = fullName.length > 10;
        const displayName = (!needsTruncation || isExpanded) ? fullName : fullName.substring(0, 8) + '...';

        return `
            <div class="glass-panel rounded-xl p-5 h-full flex flex-col justify-between border border-white/10 transition-all hover:border-white/20 ${!enabled ? 'disabled' : ''}">
                <div class="flex items-start justify-between mb-4 pb-4 border-b border-white/10">
                    <div class="flex-1 min-w-0 pr-4">
                        <div class="font-display font-semibold text-lg text-foreground flex items-start gap-2" title="${escapeHtml(fullName)}">
                            <span class="${isExpanded ? 'break-words' : 'truncate'} block">${escapeHtml(displayName)}</span>
                            ${needsTruncation ? `
                                <button class="shrink-0 p-1 hover:bg-white/10 rounded-md text-muted-foreground transition-colors mt-0.5" onclick="toggleWalletName('${account.address}')" title="${isExpanded ? 'Show Less' : 'Show Full Name'}">
                                    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                        ${isExpanded ? '<polyline points="18 15 12 9 6 15"/>' : '<polyline points="6 9 12 15 18 9"/>'}
                                    </svg>
                                </button>
                            ` : ''}
                            ${!enabled ? '<span class="inline-flex shrink-0 items-center justify-center rounded-full border border-destructive/50 bg-destructive/10 px-2 py-0.5 text-[10px] font-semibold text-destructive uppercase tracking-wider mt-0.5">Disabled</span>' : ''}
                        </div>
                        <div class="font-mono text-sm text-muted-foreground flex items-center gap-2 mt-1 truncate" title="${account.address}">
                            <span>${account.address.substring(0, 6)}...${account.address.substring(account.address.length - 4)}</span>
                            <span style="cursor: pointer; opacity: 0.7;" onclick="copyToClipboard('${account.address}')" title="Copy Address">📋</span>
                        </div>
                        ${(account.pnl !== undefined || account.winRate !== undefined) ? `
                            <div class="flex flex-wrap items-center gap-2 mt-4">
                                <div class="flex items-center gap-1.5 text-sm bg-black/20 px-2 py-1 rounded-md border border-white/5 whitespace-nowrap">
                                    <span class="text-muted-foreground">PnL:</span>
                                    <span class="font-medium ${account.pnl >= 0 ? 'positive' : 'negative'}">$${Math.abs(account.pnl || 0).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}</span>
                                </div>
                                <div class="flex items-center gap-1.5 text-sm bg-black/20 px-2 py-1 rounded-md border border-white/5 whitespace-nowrap">
                                    <span class="text-muted-foreground">WinRate:</span>
                                    <span class="font-medium text-white">${((account.winRate || 0) * 100).toFixed(0)}%</span>
                                </div>
                                <div class="flex items-center gap-1.5 text-sm bg-black/20 px-2 py-1 rounded-md border border-white/5 whitespace-nowrap">
                                    <span class="text-muted-foreground">Rank:</span>
                                    <span class="font-medium text-white">#${account.rank || '?'}</span>
                                </div>
                            </div>
                        ` : ''}
                        ${(account.tags && account.tags.length > 0) ? `
                            <div class="flex flex-wrap gap-2 mt-3">
                                ${account.tags.map(tag => `<span class="inline-flex items-center rounded-md border border-white/10 bg-white/5 px-2 py-1 text-xs font-medium text-foreground whitespace-nowrap">${escapeHtml(tag)}</span>`).join('')}
                            </div>
                        ` : ''}
                    </div>
                    <div class="flex flex-col items-end gap-3 shrink-0">
                        <label class="toggle-switch">
                            <input type="checkbox" ${enabled ? 'checked' : ''} 
                                onchange="toggleAccount('${account.address}', this.checked)">
                            <span class="slider"></span>
                        </label>
                        <button class="inline-flex items-center justify-center rounded-md h-8 w-8 transition-colors text-muted-foreground hover:bg-destructive hover:text-destructive-foreground shadow-sm" onclick="removeAccount('${account.address}')" title="Remove Target">
                            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/><line x1="10" x2="10" y1="11" y2="17"/><line x1="14" x2="14" y1="11" y2="17"/></svg>
                        </button>
                    </div>
                </div>
                <div class="flex flex-wrap gap-x-4 gap-y-3 mt-auto pt-2 text-xs">
                    <div class="flex flex-col gap-1 min-w-[80px]">
                        <div class="font-medium text-muted-foreground uppercase tracking-wider">Copied</div>
                        <div class="font-mono">${stats.trades_copied || 0}</div>
                    </div>
                    <div class="flex flex-col gap-1 min-w-[100px]">
                        <div class="font-medium text-muted-foreground uppercase tracking-wider">Last Check</div>
                        <div class="font-mono text-[11px]">${stats.last_check ? formatTimestamp(stats.last_check) : 'Never'}</div>
                    </div>
                    ${account.bet_amount_override ? `
                        <div class="flex flex-col gap-1 min-w-[100px]">
                            <div class="font-medium text-muted-foreground uppercase tracking-wider">Bet Override</div>
                            <div class="font-mono">${formatCurrency(account.bet_amount_override)}</div>
                        </div>
                    ` : ''}
                    ${stats.last_trade ? `
                        <div class="flex flex-col gap-1 w-full mt-1 border-t border-white/5 pt-2">
                            <div class="font-medium text-muted-foreground uppercase tracking-wider">Last Trade Context</div>
                            <div class="text-[11px] text-foreground/80 line-clamp-2">${escapeHtml(stats.last_trade.title || 'Unknown')}</div>
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
    }).join('');

}

async function loadWithdrawals() {
    try {
        const response = await fetch('/api/withdrawals');
        const withdrawals = await response.json();

        const container = document.getElementById('withdrawalsList');

        if (withdrawals.length === 0) {
            container.innerHTML = `
                <div class="flex flex-col items-center justify-center p-8 text-center text-muted-foreground bg-white/5 rounded-xl border border-white/5">
                    <div class="text-4xl mb-4 opacity-50">💸</div>
                    <p>No withdrawals recorded</p>
                </div>
            `;
            return;
        }

        // Sort by date descending
        withdrawals.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));

        container.innerHTML = withdrawals.slice(0, 10).map(w => `
            <div class="flex flex-col p-4 rounded-lg bg-black/20 border border-white/5 mb-2 hover:bg-white/5 transition-colors gap-2">
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
                <div class="flex flex-col items-center justify-center p-8 text-center text-muted-foreground bg-white/5 rounded-xl border border-white/5">
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
                <div class="flex flex-col p-4 rounded-lg bg-black/20 border border-white/5 mb-2 hover:bg-white/5 transition-colors gap-2">
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
    const el = document.getElementById(modalId);
    el.classList.remove('hidden');
    el.classList.add('flex');
}

function closeModal(modalId) {
    const el = document.getElementById(modalId);
    el.classList.add('hidden');
    el.classList.remove('flex');
}

// Close modal when clicking outside
window.onclick = function (event) {
    if (event.target.classList.contains('modal')) {
        event.target.classList.add('hidden');
        event.target.classList.remove('flex');
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
