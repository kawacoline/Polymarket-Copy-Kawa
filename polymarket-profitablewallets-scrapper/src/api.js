/**
 * Polymarket Data API wrapper
 * All endpoints are public — no authentication required for reads.
 */

const crypto = require('crypto');

const BASE_URL = 'https://data-api.polymarket.com';
const CLOB_URL = 'https://clob.polymarket.com';

const CATEGORIES = ['OVERALL', 'POLITICS', 'SPORTS', 'CRYPTO', 'CULTURE'];
const TIME_PERIODS = ['WEEK', 'MONTH', 'ALL'];

/**
 * Generate Polymarket CLOB L1 Auth Headers
 */
function getClobAuthHeaders(method, requestPath, body = '') {
  const timestamp = Math.floor(Date.now() / 1000).toString();
  const message = timestamp + method + requestPath + body;

  const secret = process.env.POLYMARKET_API_SECRET;
  const apiKey = process.env.POLYMARKET_API_KEY;
  const passphrase = process.env.POLYMARKET_PASSPHRASE;

  if (!secret || !apiKey || !passphrase) return {}; // Not authenticated

  const signature = crypto
    .createHmac('sha256', Buffer.from(secret, 'base64'))
    .update(message)
    .digest('base64');

  return {
    'POLY_ADDRESS': process.env.POLYMARKET_WALLET_ADDRESS || '',
    'POLY_API_KEY': apiKey,
    'POLY_PASSPHRASE': passphrase,
    'POLY_TIMESTAMP': timestamp,
    'POLY_SIGNATURE': signature,
    'Accept': 'application/json'
  };
}

/**
 * Generic fetch with retry + rate-limit backoff
 */
async function apiFetch(path, params = {}, retries = 3) {
  const url = new URL(path, BASE_URL);
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null) url.searchParams.set(k, v);
  }

  for (let attempt = 1; attempt <= retries; attempt++) {
    try {
      const res = await fetch(url.toString(), {
        headers: { 'Accept': 'application/json' },
      });

      if (res.status === 429) {
        const wait = Math.pow(2, attempt) * 1000;
        console.warn(`  ⏳ Rate-limited, retrying in ${wait / 1000}s...`);
        await sleep(wait);
        continue;
      }

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${res.statusText} — ${url.pathname}`);
      }

      return await res.json();
    } catch (err) {
      if (attempt === retries) throw err;
      const wait = Math.pow(2, attempt) * 500;
      console.warn(`  ⚠️  Attempt ${attempt} failed: ${err.message}. Retrying in ${wait / 1000}s...`);
      await sleep(wait);
    }
  }
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Fetch the leaderboard for a given category / time period
 */
async function fetchLeaderboard(category = 'OVERALL', timePeriod = 'ALL', orderBy = 'PNL', limit = 100, offset = 0) {
  return apiFetch('/v1/leaderboard', { category, timePeriod, orderBy, limit, offset });
}

/**
 * Fetch current open positions for a wallet address
 */
async function fetchPositions(address, limit = 500) {
  return apiFetch('/positions', { user: address, limit, sizeThreshold: 0.01 });
}

/**
 * Fetch recent trading activity for a wallet address
 */
async function fetchActivity(address, limit = 200) {
  return apiFetch('/activity', { user: address, limit });
}

/**
 * Fetch top active markets by volume from Gamma API
 */
async function fetchActiveMarkets(limit = 50) {
  const url = `https://gamma-api.polymarket.com/events?closed=false&active=true&limit=${limit}&order=volume&ascending=false`;
  try {
    const res = await fetch(url, { headers: { 'Accept': 'application/json' } });
    if (!res.ok) throw new Error(`Gamma API HTTP ${res.status}`);
    const events = await res.json();

    // Extract inner markets, sort by volume, take top N
    let markets = [];
    for (const event of events) {
      if (event.markets && Array.isArray(event.markets)) {
        markets.push(...event.markets);
      }
    }

    markets.sort((a, b) => (parseFloat(b.volume) || 0) - (parseFloat(a.volume) || 0));
    return markets.slice(0, limit);
  } catch (err) {
    console.warn(`  ⚠️  Failed to fetch active markets: ${err.message}`);
    return [];
  }
}

/**
 * Deep Wallet Discovery via Paginated Leaderboard
 * Polymarket's UI limits the leaderboard to 100, but the API accepts undocumented offsets.
 * By randomly picking deep offsets (up to Rank ~50,000), we can effortlessly scrape 
 * the entire active userbase without running into Graph deprecations or L2 CLOB auth.
 */
async function fetchDeepWallets(limit = 100) {
  // Sort randomly by Volume or PNL to find hidden active whales
  const orderings = ['vol', 'PNL'];
  const randomOrder = orderings[Math.floor(Math.random() * orderings.length)];

  // We are uncapping the limits entirely. We will randomly jump anywhere up to 1,000,000!
  const maxRank = 1000000;
  const randomOffset = Math.floor(Math.random() * maxRank);

  console.log(`\n🔎 Deep Discovery: Paging Rank ${randomOffset} [${randomOrder}] for completely unmapped whales...`);

  try {
    const data = await fetchLeaderboard('OVERALL', 'ALL', randomOrder, limit, randomOffset);
    const deepWallets = [];
    for (const entry of data) {
      if (entry.proxyWallet) {
        deepWallets.push({
          address: entry.proxyWallet.toLowerCase(),
          userName: entry.userName || 'Deep_Discovery',
          pnl: parseFloat(entry.pnl) || 0,
          volume: parseFloat(entry.vol) || 0,
          rank: parseInt(entry.rank) || 9999
        });
      }
    }
    return deepWallets;
  } catch (err) {
    console.warn(`  ⚠️  Failed to fetch deep wallets: ${err.message}`);
    return [];
  }
}

/**
 * Fetch Lifetime PNL and Volume for a specific wallet
 * Useful for unranked wallets discovered in the live feed.
 */
async function fetchWalletStats(address) {
  try {
    // V2: Use Data API leaderboard endpoint (lb-api.polymarket.com is deprecated)
    const data = await apiFetch('/v1/leaderboard', {
      user: address,
      timePeriod: 'ALL',
      orderBy: 'PNL',
      limit: 1
    });
    if (data && data.length > 0) {
      return {
        pnl: parseFloat(data[0].pnl) || 0,
        volume: parseFloat(data[0].vol) || 0,
      };
    }
    return { pnl: 0, volume: 0 };
  } catch (err) {
    return { pnl: 0, volume: 0 };
  }
}

/**
 * Global Live Activity Discovery
 * Fetches recent trades from the platform's most active markets.
 * This guarantees the discovery of completely brand new, unranked wallets
 * that are trading right this minute.
 */
async function fetchLiveTraders(marketsToCheck = 20, tradesPerMarket = 50) {
  console.log(`\n🌊 Live Discovery: Scanning the ${marketsToCheck} most active global markets for new traders...`);
  try {
    // 1. Get Top Events
    const eventsRes = await fetch(`https://gamma-api.polymarket.com/events?closed=false&active=true&limit=${marketsToCheck}&order=volume&ascending=false`, { headers: { 'Accept': 'application/json' } });
    if (!eventsRes.ok) throw new Error(`Gamma events failed: ${eventsRes.status}`);
    const events = await eventsRes.json();

    // Sort by volume
    events.sort((a, b) => (parseFloat(b.volume) || 0) - (parseFloat(a.volume) || 0));
    const topEvents = events.slice(0, marketsToCheck);

    const liveWallets = new Map();

    // 2. Fetch recent trades for each event (Batched to prevent ECONNRESET on 5000+ markets)
    const batchSize = 50;
    let processed = 0;

    for (let i = 0; i < topEvents.length; i += batchSize) {
      const batch = topEvents.slice(i, i + batchSize);

      await Promise.all(batch.map(async (ev) => {
        try {
          const tradeRes = await fetch(`https://data-api.polymarket.com/trades?eventId=${ev.id}&limit=${tradesPerMarket}&filterType=CASH`);
          if (!tradeRes.ok) return;
          const trades = await tradeRes.json();

          for (const t of trades) {
            if (t.proxyWallet) {
              const addr = t.proxyWallet.toLowerCase();
              if (!liveWallets.has(addr)) {
                liveWallets.set(addr, {
                  address: addr,
                  userName: 'Live_Trader',
                  pnl: 0,
                  volume: 0,
                  rank: 9999,
                  tags: ['LIVE_FEED']
                });
              }
            }
          }
        } catch (e) {
          // silently ignore individual market fetch errors
        }
      }));

      processed += batch.length;
      process.stdout.write(`  [${processed}/${topEvents.length}] global markets scanned...\r`);
    }
    console.log();

    const results = Array.from(liveWallets.values());
    console.log(`   ↳ Found ${results.length} active wallets swimming in the live feed!`);
    return results;

  } catch (err) {
    console.warn(`  ⚠️  Failed live discovery: ${err.message}`);
    return [];
  }
}

module.exports = {
  fetchLeaderboard,
  fetchPositions,
  fetchActivity,
  fetchActiveMarkets,
  fetchDeepWallets,
  fetchLiveTraders,
  fetchWalletStats,
  CATEGORIES,
  TIME_PERIODS,
  sleep,
};
