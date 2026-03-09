/**
 * Leaderboard Scraper
 * Pulls top wallets across multiple categories & time periods,
 * deduplicates, and returns a unified list.
 */

const { fetchLeaderboard, CATEGORIES, TIME_PERIODS, sleep } = require('./api');

/**
 * Scrape leaderboards across all category × timePeriod combos.
 * Returns a Map<address, walletInfo> with deduplicated entries,
 * keeping the best PNL record for each wallet.
 */
async function scrapeLeaderboards(limit = 100) {
    const walletMap = new Map();
    const combos = [];

    for (const cat of CATEGORIES) {
        for (const tp of TIME_PERIODS) {
            combos.push({ category: cat, timePeriod: tp });
        }
    }

    console.log(`\n🏆 Scraping ${combos.length} leaderboard combinations (limit=${limit} each)...\n`);

    const BATCH_SIZE = parseInt(process.env.CONCURRENCY) || 20;

    for (let i = 0; i < combos.length; i += BATCH_SIZE) {
        const batch = combos.slice(i, i + BATCH_SIZE);

        await Promise.all(batch.map(async (combo, idx) => {
            const { category, timePeriod } = combo;
            const label = `  [${i + idx + 1}/${combos.length}] ${category} / ${timePeriod}`;

            try {
                const data = await fetchLeaderboard(category, timePeriod, 'PNL', limit);
                let newCount = 0;

                for (const entry of data) {
                    const addr = entry.proxyWallet?.toLowerCase();
                    if (!addr) continue;

                    const pnl = parseFloat(entry.pnl) || 0;
                    const vol = parseFloat(entry.vol) || 0;

                    const existing = walletMap.get(addr);
                    if (!existing) {
                        walletMap.set(addr, {
                            address: addr,
                            userName: entry.userName || '',
                            pnl,
                            volume: vol,
                            tags: new Set([category]),
                            leaderboardRank: parseInt(entry.rank) || 999,
                        });
                        newCount++;
                    } else {
                        // Keep best PNL/volume but accumulate tags
                        if (pnl > existing.pnl) {
                            existing.pnl = pnl;
                            existing.volume = vol;
                            existing.leaderboardRank = Math.min(existing.leaderboardRank, parseInt(entry.rank) || 999);
                        }
                        existing.tags.add(category);
                    }
                }

                console.log(`${label} → ${data.length} entries (${newCount} new wallets)`);
            } catch (err) {
                console.error(`${label} → ❌ ${err.message}`);
            }
        }));

        // Small delay between batches to be nice to the API
        if (i + BATCH_SIZE < combos.length) await sleep(300);
    }

    // Convert Sets to Arrays before returning
    walletMap.forEach(w => w.tags = Array.from(w.tags));
    console.log(`\n📊 Total unique wallets found: ${walletMap.size}\n`);
    return walletMap;
}

module.exports = { scrapeLeaderboards };
