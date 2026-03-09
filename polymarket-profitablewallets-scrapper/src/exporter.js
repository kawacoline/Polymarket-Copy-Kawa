/**
 * Exporter
 * Writes the final ranked wallet list to a JSON file
 * for the copy bot to consume.
 */

const fs = require('fs');
const path = require('path');

/**
 * Export scored wallets to a JSON file.
 */
function exportWallets(wallets, outputPath) {
    const dir = path.dirname(outputPath);
    if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
    }

    const payload = {
        scrapedAt: new Date().toISOString(),
        walletsCount: wallets.length,
        wallets: wallets.map(w => ({
            rank: w.rank,
            address: w.address,
            userName: w.userName,
            pnl: w.pnl,
            unrealizedPnl: w.unrealizedPnl,
            volume: w.volume,
            winRate: w.winRate,
            avgTradeSize: w.avgTradeSize,
            tradesPerDay: w.tradesPerDay,
            activePositions: w.activePositions,
            totalTrades: w.totalTrades,
            avgTradeSize: w.avgTradeSize,
            lastTradeAt: w.lastTradeAt,
            daysSinceLastTrade: w.daysSinceLastTrade,
            score: w.score,
            scoreBreakdown: w._breakdown,
            totalClosedPositions: w.totalClosedPositions,
            bestCategory: w.bestCategory,
            tags: w.tags,
            profileUrl: `https://polymarket.com/profile/${w.address}`
        })),
    };

    fs.writeFileSync(outputPath, JSON.stringify(payload, null, 2), 'utf-8');

    console.log(`\n💾 Exported ${wallets.length} wallets → ${outputPath}`);
    console.log(`   File size: ${(fs.statSync(outputPath).size / 1024).toFixed(1)} KB\n`);

    return payload;
}

/**
 * Print a summary table to the console
 */
function printSummary(wallets, topN = 15) {
    const top = wallets.slice(0, topN);

    console.log(`\n${'═'.repeat(110)}`);
    console.log(`  TOP ${topN} PROFITABLE WALLETS`);
    console.log(`${'═'.repeat(130)}`);
    console.log(
        '  #  │ Score │ Username         │ Tags                           │ PNL ($)          │ Unrlzd ($) │ AvgTrade │ Trades/Day │ Closed │ Actv │ Last Trade'
    );
    console.log(`${'─'.repeat(150)}`);

    for (const w of top) {
        const rank = String(w.rank).padStart(3);
        const score = String(w.score.toFixed(1)).padStart(5);
        const name = (w.userName || w.address.slice(0, 10)).padEnd(16).slice(0, 16);
        const tags = w.tags.join(', ').padEnd(30).slice(0, 30);
        const pnl = w.pnl.toLocaleString('en-US', { maximumFractionDigits: 0 }).padStart(16);
        const unrlzd = w.unrealizedPnl.toLocaleString('en-US', { maximumFractionDigits: 0 }).padStart(10);
        const avg = `$${Math.round(w.avgTradeSize)}`.padStart(8);
        const freq = String(w.tradesPerDay.toFixed(1)).padStart(10);
        const wr = `${(w.winRate * 100).toFixed(1)}%`.padStart(7);
        const closed = String(w.totalClosedPositions).padStart(6);
        const active = String(w.activePositions).padStart(4);
        const lastTrade = w.daysSinceLastTrade < 999
            ? `${w.daysSinceLastTrade.toFixed(0)}d ago`
            : 'N/A';

        console.log(
            ` ${rank} │ ${score} │ ${name} │ ${tags} │ ${pnl} │ ${unrlzd} │ ${avg} │ ${freq} │ ${closed} │ ${active} │ ${lastTrade}`
        );
    }

    console.log(`${'═'.repeat(110)}\n`);
}

module.exports = { exportWallets, printSummary };
