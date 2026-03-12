#!/usr/bin/env node

/**
 * Single Wallet Analyzer CLI
 * Bridge for the Python backend to fetch fresh stats for a specific wallet.
 */

require('dotenv').config();
const { analyzeWallet } = require('./analyzer');
const { fetchWalletStats } = require('./api');

async function main() {
    const address = process.argv[2];
    if (!address) {
        console.error(JSON.stringify({ error: "No address provided" }));
        process.exit(1);
    }

    try {
        const addr = address.toLowerCase();
        
        // 1. Fetch basic stats (PnL/Volume)
        const stats = await fetchWalletStats(addr);
        
        // 2. Run deep analysis (WinRate, Activity, Tags)
        const result = await analyzeWallet({
            address: addr,
            userName: 'Enriched_Account',
            ...stats
        });

        // 3. Output as JSON for Python to consume
        console.log(JSON.stringify(result, null, 2));
    } catch (err) {
        console.error(JSON.stringify({ 
            error: err.message,
            stack: err.stack 
        }));
        process.exit(1);
    }
}

main();
