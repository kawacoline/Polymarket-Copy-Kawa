#!/usr/bin/env node

/**
 * Polymarket Profitable Wallets Scraper
 * CLI entry point — scrape once or watch on a cron schedule.
 */

require('dotenv').config();

const { program } = require('commander');
const path = require('path');
const fs = require('fs');

const { scrapeLeaderboards } = require('./leaderboard');
const { fetchDeepWallets, fetchLiveTraders, fetchWalletStats, sleep } = require('./api');
const { analyzeWallets } = require('./analyzer');
const { filterWallets, scoreWallets } = require('./filter');
const { exportWallets, printSummary } = require('./exporter');

// ── Config from .env ──
const config = {
    leaderboardLimit: parseInt(process.env.LEADERBOARD_LIMIT) || 100,
    minPnl: parseFloat(process.env.MIN_PNL) || 10000,
    minVolume: parseFloat(process.env.MIN_VOLUME) || 50000,
    maxInactiveDays: parseInt(process.env.MAX_INACTIVE_DAYS) || 7,
    maxActivePositions: parseInt(process.env.MAX_ACTIVE_POSITIONS) || 50,
    minAvgTradeSize: parseFloat(process.env.MIN_AVG_TRADE_SIZE) || 100,
    maxTradesPerDay: parseFloat(process.env.MAX_TRADES_PER_DAY) || 5,
    continuousDelaySec: parseInt(process.env.CONTINUOUS_DELAY_SEC) || 60,
    rejectedTtlDays: parseInt(process.env.REJECTED_TTL_DAYS) || 7,
    outputPath: process.env.OUTPUT_PATH || './output/profitable_wallets.json',
    rejectedPath: process.env.REJECTED_PATH || './output/rejected_wallets.json',
};

/**
 * Run a single full scrape cycle
 */
async function runScrape(options = {}) {
    const limit = options.limit || config.leaderboardLimit;
    const outputPath = path.resolve(options.output || config.outputPath);

    console.log('\n' + '═'.repeat(60));
    console.log('  🚀 POLYMARKET PROFITABLE WALLETS SCRAPER');
    console.log('═'.repeat(60));
    console.log(`  Started at: ${new Date().toISOString()}`);
    console.log(`  Leaderboard limit: ${limit}`);
    console.log(`  Min PNL: $${config.minPnl.toLocaleString()}`);
    console.log(`  Min Volume: $${config.minVolume.toLocaleString()}`);
    console.log(`  Max Inactive: ${config.maxInactiveDays} days`);
    console.log(`  Max Active Positions: ${config.maxActivePositions}`);
    console.log(`  Min Avg Trade Size: $${config.minAvgTradeSize}`);
    console.log(`  Max Trades Per Day: ${config.maxTradesPerDay}`);
    console.log(`  Output: ${outputPath}`);
    console.log('═'.repeat(60));

    const startTime = Date.now();
    const stats = {
        time: new Date().toISOString(),
        found: 0, // Changed from totalFound
        skippedBad: 0,
        analyzed: 0,
        passed: 0,
        newlyRejected: 0,
        elapsedSeconds: 0
    };

    try {
        // 1. Scrape leaderboards
        const walletMap = await scrapeLeaderboards(limit);

        // 1.5 Deep Discovery: Grab highly active traders bypassing leaderboards
        console.log('\n🔎 Extracting a random deep slice up to Rank 1,000,000...');
        const deepWallets = await fetchDeepWallets(1000); // Fetch 1000 deep wallets

        for (const w of deepWallets) {
            if (!walletMap.has(w.address)) {
                walletMap.set(w.address, {
                    address: w.address,
                    userName: w.userName,
                    pnl: w.pnl,
                    volume: w.volume,
                    tags: ['DEEP'],
                    leaderboardRank: w.rank,
                });
            }
        }

        // 1.8 Global Live Discovery: Grab everyone currently trading on the top 5000 events
        const liveWallets = await fetchLiveTraders(5000, 1000); // Top 5000 events, last 1000 trades each
        for (const w of liveWallets) {
            if (!walletMap.has(w.address)) {
                walletMap.set(w.address, w);
            } else {
                // Merge LIVE_FEED tag if it's already in the pool
                walletMap.get(w.address).tags.push('LIVE_FEED');
            }
        }

        stats.found = walletMap.size; // Updated from totalFound

        // 1.5 Load existing wallets to accumulate
        try {
            if (fs.existsSync(outputPath)) {
                const existingData = JSON.parse(fs.readFileSync(outputPath, 'utf8'));
                if (existingData.wallets && Array.isArray(existingData.wallets)) {
                    for (const w of existingData.wallets) {
                        if (walletMap.has(w.address)) {
                            // Merge tags if it IS on the leaderboard currently
                            const current = walletMap.get(w.address);
                            const combinedTags = new Set([...current.tags, ...(Array.isArray(w.tags) ? w.tags : [])]);
                            current.tags = Array.from(combinedTags);
                        } else {
                            // Add it to the scrape pool for re-analysis even if it fell off the leaderboard
                            // Their old pnl/volume will be preserved, but new activity will be fetched
                            walletMap.set(w.address, {
                                ...w,
                                tags: Array.isArray(w.tags) ? w.tags : ['OVERALL'],
                            });
                        }
                    }
                    console.log(`\n💾 Injected ${existingData.wallets.length} previously approved wallets into the pool for fresh analysis.`);
                }
            }
        } catch (e) {
            console.log(`\n⚠️  Could not load existing wallets: ${e.message}\n`);
        }

        // 1.8 Load rejected wallets caching
        let rejectedCache = new Map();
        try {
            if (fs.existsSync(config.rejectedPath)) {
                const existingRejected = JSON.parse(fs.readFileSync(config.rejectedPath, 'utf8'));
                const now = Date.now();
                const ttlMs = config.rejectedTtlDays * 24 * 60 * 60 * 1000;

                let expiredCount = 0;
                for (const [addr, data] of Object.entries(existingRejected)) {
                    if (now - data.timestamp < ttlMs) {
                        rejectedCache.set(addr, data);
                    } else {
                        expiredCount++;
                    }
                }
                console.log(`🚫 Loaded ${rejectedCache.size} known rejected wallets (skipped ${expiredCount} expired entries).`);

                // Remove rejected wallets from the current scrape pool so we don't process them again
                let skippedCount = 0;
                for (const addr of rejectedCache.keys()) {
                    if (walletMap.has(addr)) {
                        walletMap.delete(addr);
                        skippedCount++;
                    }
                }
                if (skippedCount > 0) {
                    console.log(`⏭️  Skipping ${skippedCount} wallets already known to be bad.\n`);
                    stats.skippedBad = skippedCount;
                }
            }
        } catch (e) {
            console.log(`\n⚠️  Could not load rejected wallets cache: ${e.message}\n`);
        }

        let newlyPassed = [];
        let newlyRejected = [];

        // 1.9 Pre-filter: Fetch missing PNL/Volume for unindexed wallets (like LIVE_FEED)
        // This prevents us from doing expensive position/activity lookups on people with $10 PNL
        const unindexedWallets = Array.from(walletMap.values()).filter(w =>
            w.pnl === 0 && w.volume === 0 && w.tags.includes('LIVE_FEED')
        );

        if (unindexedWallets.length > 0) {
            console.log(`\n🔎 Pre-filtering ${unindexedWallets.length} new live traders for minimum PNL/Volume...`);
            let checked = 0;
            const batchSize = 10;
            for (let i = 0; i < unindexedWallets.length; i += batchSize) {
                const batch = unindexedWallets.slice(i, i + batchSize);
                await Promise.all(batch.map(async (w) => {
                    const stats = await fetchWalletStats(w.address);
                    w.pnl = stats.pnl;
                    w.volume = stats.volume;

                    if (w.pnl < config.minPnl || w.volume < config.minVolume) {
                        // They don't meet criteria, remove them from walletMap immediately AND add to newlyRejected
                        walletMap.delete(w.address);
                        w._rejectReason = w.pnl < config.minPnl ? `PNL < $${config.minPnl}` : `Volume < $${config.minVolume}`;
                        newlyRejected.push(w);
                    }
                }));
                checked += batch.length;
                process.stdout.write(`  [${checked}/${unindexedWallets.length}] live traders checked...\r`);
                await sleep(200); // Small pause between batches
            }
            console.log();
        }

        // 2. Analyze the REMAINING new wallets (positions + activity)
        stats.analyzed = walletMap.size;

        if (walletMap.size > 0) {
            const analyzed = await analyzeWallets(walletMap);

            // 3. Filter by thresholds
            const filterResults = filterWallets(analyzed, {
                minPnl: config.minPnl,
                minVolume: config.minVolume,
                maxInactiveDays: config.maxInactiveDays,
                maxActivePositions: config.maxActivePositions,
                minAvgTradeSize: config.minAvgTradeSize,
                maxTradesPerDay: config.maxTradesPerDay,
            });
            // We combine the pre-rejected with the post-rejected!
            newlyPassed = filterResults.passed;
            newlyRejected = newlyRejected.concat(filterResults.rejected);
        } else {
            console.log(`\n🔍 No new wallets to analyze.\n`);
        }

        stats.passed = newlyPassed.length;
        stats.newlyRejected = newlyRejected.length;

        // 3.5 Update rejected cache with newly rejected wallets
        const now = Date.now();
        for (const w of newlyRejected) {
            rejectedCache.set(w.address, {
                timestamp: now,
                reason: w._rejectReason || 'Unknown',
                pnl: w.pnl || 0
            });
        }

        fs.mkdirSync(path.dirname(config.rejectedPath), { recursive: true });
        fs.writeFileSync(config.rejectedPath, JSON.stringify(Object.fromEntries(rejectedCache), null, 2));
        if (newlyRejected.length > 0) {
            console.log(`💾 Saved ${rejectedCache.size} rejected wallets to cache.\n`);
        }

        // 4. Score and rank
        const scored = scoreWallets(newlyPassed);

        // 5. Export
        exportWallets(scored, outputPath);

        // 6. Print summary
        printSummary(scored);

        const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
        console.log(`⏱️  Completed in ${elapsed}s\n`);

        stats.elapsedSeconds = elapsed;

        // 7. Write to summary.log
        const logLine = `[${stats.time}] Cycle complete in ${stats.elapsedSeconds}s | Found: ${stats.found} | Skipped(Bad): ${stats.skippedBad} | Analyzed: ${stats.analyzed} | Passed: ${stats.passed} | Rejected: ${stats.newlyRejected} | Total Good Output: ${scored.length}\n`;
        const logPath = path.resolve(path.dirname(config.outputPath), 'summary.log');
        fs.appendFileSync(logPath, logLine);

        return scored;
    } catch (err) {
        console.error(`\n💥 Scrape failed: ${err.message}\n`);
        throw err;
    }
}

// ── CLI Commands ──

program
    .name('polymarket-scraper')
    .description('Scrape the most profitable wallets from Polymarket')
    .version('1.0.0');

program
    .command('scrape')
    .description('Run a single scrape cycle')
    .option('-l, --limit <n>', 'Wallets per leaderboard category', parseInt)
    .option('-o, --output <path>', 'Output JSON path')
    .action(async (opts) => {
        try {
            await runScrape(opts);
        } catch (e) {
            console.error(e);
            process.exit(1);
        }
    });

program
    .command('continuous')
    .description('Continuous 24/7 scraping in real time (stops on Ctrl+C)')
    .option('-l, --limit <n>', 'Wallets per leaderboard category', parseInt)
    .option('-o, --output <path>', 'Output JSON path')
    .option('-d, --delay <seconds>', 'Delay between runs in seconds', parseInt)
    .action(async (opts) => {
        const delay = opts.delay || config.continuousDelaySec;

        console.log(`\n👁️  Continuous mode — running 24/7 with ${delay}s delay between cycles.`);
        console.log('   Press Ctrl+C to stop.\n');

        while (true) {
            try {
                await runScrape(opts);
            } catch (err) {
                console.error(`Scrape cycle failed. Retrying in ${delay}s...`);
            }

            console.log(`\n⏳ Waiting ${delay} seconds before next cycle...`);
            await new Promise(resolve => setTimeout(resolve, delay * 1000));
        }
    });

program.parse();
