const { fetchLeaderboard, fetchActivity } = require('./src/api');

async function test() {
    try {
        console.log("Fetching leaderboard...");
        const lb = await fetchLeaderboard('OVERALL', 'ALL', 'PNL', 10);
        if (!lb || lb.length === 0) {
            console.log("No leaderboard data.");
            return;
        }

        const topWallet = lb[0].proxyWallet;
        console.log("Top wallet:", topWallet);

        console.log("Fetching activity...");
        const activity = await fetchActivity(topWallet, 10);

        console.log("Activity length:", activity.length);
        if (activity.length > 0) {
            console.log("Keys in activity item:", Object.keys(activity[0]));
            console.log("Maker:", activity[0].maker_address);
            console.log("Taker:", activity[0].taker_address);
            console.log("First item:", JSON.stringify(activity[0], null, 2));
        }
    } catch (e) {
        console.error("Error:", e);
    }
}
test();
