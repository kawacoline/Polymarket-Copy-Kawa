/**
 * Smart Filtering Engine
 * Filters and scores wallets based on configurable thresholds,
 * then produces a ranked list.
 */

/**
 * Filter wallets by minimum thresholds
 */
function filterWallets(wallets, options = {}) {
    const {
        minPnl = 10000,
        minVolume = 50000,
        maxInactiveDays = 7,
        maxActivePositions = 50,
        minAvgTradeSize = 100,
        maxTradesPerDay = 5,
    } = options;

    console.log(`\n🎯 Filtering wallets: minPNL=$${minPnl.toLocaleString()}, minVol=$${minVolume.toLocaleString()}, maxInactive=${maxInactiveDays}d, maxActivePos=${maxActivePositions}, minAvgTrade=$${minAvgTradeSize}, maxTrades/Day=${maxTradesPerDay}\n`);

    const before = wallets.length;

    const passed = [];
    const rejected = [];

    for (const w of wallets) {
        if (w.error) {
            w._rejectReason = 'API Error';
            rejected.push(w);
            continue;
        }
        if (w.pnl < minPnl) {
            w._rejectReason = `PNL < $${minPnl}`;
            rejected.push(w);
            continue;
        }
        if (w.volume < minVolume) {
            w._rejectReason = `Volume < $${minVolume}`;
            rejected.push(w);
            continue;
        }
        if (w.daysSinceLastTrade > maxInactiveDays) {
            w._rejectReason = `Inactive > ${maxInactiveDays}d`;
            rejected.push(w);
            continue;
        }
        if (w.activePositions > maxActivePositions) {
            w._rejectReason = `Positions > ${maxActivePositions}`;
            rejected.push(w);
            continue;
        }
        if ((w.avgTradeSize || 0) < minAvgTradeSize) {
            w._rejectReason = `Avg Trade < $${minAvgTradeSize}`;
            rejected.push(w);
            continue;
        }
        if ((w.tradesPerDay || 0) > maxTradesPerDay) {
            w._rejectReason = `Trades/Day > ${maxTradesPerDay}`;
            rejected.push(w);
            continue;
        }
        // --- Behavioral Tagging ---
        // Clean up previously appended behavioral tags so they don't duplicate on re-analysis
        w.tags = w.tags || [];
        w.tags = w.tags.filter(t => !['HIGH_VOL', 'MED_VOL', 'SMALL_VOL', 'HFT', 'ACTIVE', 'HUMAN'].includes(t));

        // Volume Tiers
        if (w.volume >= 1000000) {
            w.tags.push('HIGH_VOL');
        } else if (w.volume >= 250000) {
            w.tags.push('MED_VOL');
        } else {
            w.tags.push('SMALL_VOL');
        }

        // Trading Style (Frequency)
        // Ensure tradesPerDay defaults to 0 if undefined
        const tpd = w.tradesPerDay || 0;
        if (tpd > 10) {
            w.tags.push('HFT');
        } else if (tpd >= 2) {
            w.tags.push('ACTIVE');
        } else {
            w.tags.push('HUMAN');
        }

        passed.push(w);
    }

    console.log(`  📉 Filtered ${before} → ${passed.length} wallets (${rejected.length} rejected)\n`);
    return { passed, rejected };
}

/**
 * Compute a composite score for each wallet.
 *
 * Score = weighted combination of:
 *   - PNL rank         (40%) — raw profitability
 *   - Win rate          (25%) — consistency
 *   - Recency           (20%) — how recently they traded
 *   - Volume            (15%) — conviction / capital
 */
function scoreWallets(wallets) {
    if (wallets.length === 0) return [];

    // Normalize each metric to 0-100 range
    const maxPnl = Math.max(...wallets.map(w => w.pnl));
    const maxVol = Math.max(...wallets.map(w => w.volume));
    const maxWinRate = Math.max(...wallets.map(w => w.winRate), 0.01);
    const maxClosed = Math.max(...wallets.map(w => w.totalClosedPositions), 1);

    const scored = wallets.map(w => {
        const pnlScore = maxPnl > 0 ? (w.pnl / maxPnl) * 100 : 0;
        const winRateScore = maxWinRate > 0 ? (w.winRate / maxWinRate) * 100 : 0;
        const volScore = maxVol > 0 ? (w.volume / maxVol) * 100 : 0;
        const closedCountScore = (w.totalClosedPositions / maxClosed) * 100;

        // Recency: 100 if traded today, decays over 30 days
        const recencyScore = w.daysSinceLastTrade <= 0
            ? 100
            : Math.max(0, 100 - (w.daysSinceLastTrade / 30) * 100);

        // WEIGHTS:
        // Closed Positions  (40%)
        // PNL               (30%)
        // Win Rate          (15%)
        // Recency           (10%)
        // Volume            (5%)
        const score =
            closedCountScore * 0.40 +
            pnlScore * 0.30 +
            winRateScore * 0.15 +
            recencyScore * 0.10 +
            volScore * 0.05;

        return {
            ...w,
            score: Math.round(score * 100) / 100,
            _breakdown: {
                closed: Math.round(closedCountScore * 100) / 100,
                pnl: Math.round(pnlScore * 100) / 100,
                winRate: Math.round(winRateScore * 100) / 100,
                recency: Math.round(recencyScore * 100) / 100,
                volume: Math.round(volScore * 100) / 100,
            },
        };
    });

    // Sort by score descending
    scored.sort((a, b) => b.score - a.score);

    // Assign final rank
    scored.forEach((w, i) => (w.rank = i + 1));

    return scored;
}

module.exports = { filterWallets, scoreWallets };
