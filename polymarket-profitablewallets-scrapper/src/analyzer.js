/**
 * Wallet Analyzer
 * Fetches positions + activity for each wallet and computes derived metrics.
 */

const { fetchPositions, fetchActivity, sleep } = require('./api');

/**
 * Heuristic to calculate win rate based on buy/sell price difference
 * for active traders who don't hold to redemption.
 */
function calculateProfitWinRate(activity) {
    const trades = activity.filter(a => a.type === 'TRADE');
    if (trades.length === 0) return { winRate: 0, totalClosed: 0 };

    // Group by market+outcome to find buy/sell pairs
    const marketGroups = {};
    for (const t of trades) {
        const key = `${t.slug}_${t.outcome}`;
        if (!marketGroups[key]) marketGroups[key] = [];
        marketGroups[key].push(t);
    }

    let wins = 0;
    let totalClosed = 0;

    for (const key in marketGroups) {
        const marketTrades = marketGroups[key].sort((a, b) => a.timestamp - b.timestamp);

        // Simplified Logic: If last trade in this market was a SELL, 
        // compare its price to the first BUY in the sequence.
        const buys = marketTrades.filter(t => t.side === 'BUY');
        const sells = marketTrades.filter(t => t.side === 'SELL');

        if (buys.length > 0 && sells.length > 0) {
            const avgBuyPrice = buys.reduce((sum, t) => sum + (parseFloat(t.price) || 0), 0) / buys.length;
            const lastSellPrice = parseFloat(sells[sells.length - 1].price) || 0;

            if (lastSellPrice > avgBuyPrice) {
                wins++;
            }
            totalClosed++;
        }
    }

    // Add Redemptions to the mix (they are definitely wins)
    const redeems = activity.filter(a => a.type === 'REDEEM');
    wins += redeems.length;
    totalClosed += redeems.length;

    const winRate = totalClosed > 0 ? wins / totalClosed : 0;
    return { winRate, totalClosed };
}

/**
 * Analyze a single wallet: fetch positions + activity, compute stats.
 */
async function analyzeWallet(wallet) {
    const addr = wallet.address;

    let positions = [];
    let activity = [];

    try {
        const [posRes, actRes] = await Promise.all([
            fetchPositions(addr).catch(err => {
                console.warn(`    ⚠️  Could not fetch positions for ${addr}: ${err.message}`);
                return [];
            }),
            fetchActivity(addr).catch(err => {
                console.warn(`    ⚠️  Could not fetch activity for ${addr}: ${err.message}`);
                return [];
            })
        ]);
        positions = posRes;
        activity = actRes;
    } catch (err) {
        console.warn(`    ⚠️  Error during wallet fetch for ${addr}: ${err.message}`);
    }

    // ── Derive metrics ──

    // Active positions
    const activePositions = Array.isArray(positions) ? positions.length : 0;

    // Trades, Sells, and Redeems
    const trades = activity.filter(a => a.type === 'TRADE');
    const sells = trades.filter(t => t.side === 'SELL');
    const redeems = activity.filter(a => a.type === 'REDEEM');

    const totalTrades = trades.length;
    const totalRedeems = redeems.length;
    const totalSells = sells.length;

    // Win rate approximation
    const { winRate, totalClosed } = calculateProfitWinRate(activity);

    // Detect high-performance active traders (Low redemptions but high trade activity)
    const isActiveWhale = (wallet.pnl > 5000 && totalTrades > 20);

    // Auto-tagging
    if (!wallet.tags) wallet.tags = [];
    if (isActiveWhale && !wallet.tags.includes('ACTIVE_WHALE')) {
        wallet.tags.push('ACTIVE_WHALE');
    }

    // Average trade size (USDC)
    const tradeSizes = trades.map(t => parseFloat(t.usdcSize) || 0).filter(s => s > 0);
    const avgTradeSize = tradeSizes.length > 0
        ? tradeSizes.reduce((a, b) => a + b, 0) / tradeSizes.length
        : 0;

    // Last trade timestamp
    const allTimestamps = activity
        .map(a => a.timestamp)
        .filter(Boolean)
        .sort((a, b) => b - a);

    const lastTradeTimestamp = allTimestamps.length > 0 ? allTimestamps[0] : null;
    const lastTradeAt = lastTradeTimestamp
        ? new Date(lastTradeTimestamp * 1000).toISOString()
        : null;

    // Days since last trade
    const daysSinceLastTrade = lastTradeTimestamp
        ? (Date.now() / 1000 - lastTradeTimestamp) / 86400
        : Infinity;

    // Active Lifespan & Trades Per Day
    const firstTradeTimestamp = allTimestamps.length > 0 ? allTimestamps[allTimestamps.length - 1] : null;
    const activeLifespanDays = firstTradeTimestamp && lastTradeTimestamp
        ? Math.max((lastTradeTimestamp - firstTradeTimestamp) / 86400, 1) // Minimum 1 day to avoid Infinity
        : 1;
    const tradesPerDay = totalTrades / activeLifespanDays;

    // Unrealized PNL (Sum of current open position cashPnl)
    const unrealizedPnl = Array.isArray(positions)
        ? positions.reduce((sum, p) => sum + (parseFloat(p.cashPnl) || 0), 0)
        : 0;

    // Current positions detail (simplified for export)
    const positionsSummary = Array.isArray(positions)
        ? positions.map(p => ({
            market: p.title || p.slug || 'Unknown',
            outcome: p.outcome || '',
            size: parseFloat(p.size) || 0,
            avgPrice: parseFloat(p.avgPrice) || 0,
            curPrice: parseFloat(p.curPrice) || 0,
            pnl: parseFloat(p.cashPnl) || 0,
        }))
        : [];

    // Recent trades (last 10)
    const recentTrades = trades.slice(0, 10).map(t => ({
        market: t.title || t.slug || 'Unknown',
        outcome: t.outcome || '',
        side: t.side || '',
        size: parseFloat(t.usdcSize) || 0,
        price: parseFloat(t.price) || 0,
        timestamp: t.timestamp ? new Date(t.timestamp * 1000).toISOString() : null,
    }));

    return {
        ...wallet,
        activePositions,
        unrealizedPnl: Math.round(unrealizedPnl * 100) / 100,
        totalTrades,
        totalRedeems,
        totalClosedPositions: totalClosed,
        winRate: Math.round(winRate * 10000) / 10000,
        avgTradeSize: Math.round(avgTradeSize * 100) / 100,
        tradesPerDay: Math.round(tradesPerDay * 100) / 100,
        lastTradeAt,
        daysSinceLastTrade: Math.round(daysSinceLastTrade * 10) / 10,
        positions: positionsSummary,
        recentTrades,
        isActiveWhale,
    };
}

/**
 * Analyze multiple wallets with progress logging
 */
async function analyzeWallets(walletMap, concurrency = 1) {
    const wallets = Array.from(walletMap.values());
    console.log(`\n🔍 Analyzing ${wallets.length} wallets (positions + activity)...\n`);

    const results = [];

    const BATCH_SIZE = parseInt(process.env.CONCURRENCY) || 20;

    for (let i = 0; i < wallets.length; i += BATCH_SIZE) {
        const batch = wallets.slice(i, i + BATCH_SIZE);

        const batchPromises = batch.map(async (w) => {
            try {
                return await analyzeWallet(w);
            } catch (err) {
                return { ...w, error: err.message };
            }
        });

        const batchResults = await Promise.all(batchPromises);
        results.push(...batchResults);

        process.stdout.write(`\r  [${Math.min(i + BATCH_SIZE, wallets.length)}/${wallets.length}] wallets analyzed...`);

        // Small rate-limit delay between batches
        if (i + BATCH_SIZE < wallets.length) await sleep(200);
    }

    console.log(`\n✅ Analyzed ${results.length} wallets\n`);
    return results;
}

module.exports = { analyzeWallet, analyzeWallets };
