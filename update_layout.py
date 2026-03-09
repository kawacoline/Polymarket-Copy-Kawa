import re

with open("templates/index.html", "r", encoding="utf-8") as f:
    html = f.read()

# 1. Update accounts grid (Whale Tracking section)
html = re.sub(r'id="accountsList" class="grid grid-cols-[^"]+"', 'id="accountsList" class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6 gap-4"', html)

# 2. Update Stats Grid (squares)
html = html.replace('<div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4 mb-8">', '<div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4 mb-8">')
# To make them square-ish, we add `aspect-square flex flex-col justify-center items-center text-center`
html = html.replace('class="glass-panel rounded-xl p-6 relative overflow-hidden stat-card"', 'class="glass-panel rounded-xl p-6 relative overflow-hidden stat-card flex flex-col justify-center items-center text-center aspect-auto min-h-[140px] md:aspect-square"')

# 3. Re-structure the Header to include Engine Execution
# Find the exact current header range to remove the top header and the secondary header
header_extract = re.search(r'(<!-- Dashboard Header -->\s*<header class="glass-header sticky top-0.*?</div>\s*</header>)\s*<!-- Engine Controls \(Pinned\) -->\s*<div class="glass-header w-full px-6 py-3.*?</div>', html, re.DOTALL)

if header_extract:
    old_full_header = header_extract.group(0)
    
    new_header = """<!-- Dashboard Header -->
        <header class="glass-header sticky top-0 z-50 w-full px-6 py-4 flex flex-col 2xl:flex-row 2xl:items-center justify-between gap-4">
            <div class="flex items-center justify-between 2xl:justify-start gap-4 shrink-0 w-full 2xl:w-auto">
                <div class="flex items-center gap-3 shrink-0">
                    <div class="relative flex h-8 w-8 items-center justify-center rounded-lg bg-primary/20 text-primary">
                        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-activity h-4 w-4"><path d="M22 12h-2.48a2 2 0 0 0-1.93 1.46l-2.35 8.36a.25.25 0 0 1-.48 0L9.24 2.18a.25.25 0 0 0-.48 0l-2.35 8.36A2 2 0 0 1 4.49 12H2"></path></svg>
                        <div class="absolute -top-1 -right-1 h-3 w-3 rounded-full border-2 border-background bg-primary animate-pulse"></div>
                    </div>
                    <div>
                        <h1 class="text-xl font-bold font-display text-gradient">⚡ COMMAND CENTER</h1>
                        <p class="text-xs text-muted-foreground font-mono">Polymarket Multi-Account Copy Trade Engine</p>
                    </div>
                </div>
            </div>

            <div class="flex items-center gap-3 flex-wrap justify-center border-y border-white/5 py-3 2xl:border-0 2xl:py-0 shrink-0 w-full 2xl:w-auto overflow-x-auto">
                <button id="startBtn" class="shrink-0 inline-flex items-center justify-center rounded-md text-xs font-medium transition-colors h-8 px-4 bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30 border border-emerald-500/50 shadow shadow-emerald-500/20" onclick="startBot()">
                    <span class="mr-2">▶</span> START
                </button>
                <button id="stopBtn" class="shrink-0 inline-flex items-center justify-center rounded-md text-xs font-medium transition-colors h-8 px-4 border border-input bg-transparent shadow-sm hover:bg-accent hover:text-accent-foreground" onclick="stopBot()" disabled>
                    <span class="mr-2">⏸</span> PAUSE
                </button>
                <button id="panicSellBtn" class="shrink-0 inline-flex items-center justify-center rounded-md text-xs font-medium transition-colors h-8 px-4 bg-destructive text-destructive-foreground shadow hover:bg-destructive/90" onclick="showModal('panicSellModal')">
                    <span class="mr-2">🚨</span> PANIC
                </button>

                <div class="w-px h-6 bg-white/10 hidden sm:block mx-1"></div>

                <div class="shrink-0 flex items-center gap-2">
                    <span id="statusIndicator" class="dot stopped"></span>
                    <span id="statusText" class="text-xs font-semibold tracking-wide">OFFLINE</span>
                </div>
                <div class="w-px h-6 bg-white/10 hidden sm:block mx-1"></div>
                <div class="shrink-0 flex items-center gap-2 text-xs">
                    <span style="color: var(--text-dim);">DRY RUN:</span>
                    <label class="toggle-switch transform scale-75 origin-left" style="margin:0;">
                        <input type="checkbox" id="dryRunToggle" onchange="toggleDryRun()" checked>
                        <span class="slider"></span>
                    </label>
                </div>
                <div class="w-px h-6 bg-white/10 hidden sm:block mx-1"></div>
                <button class="shrink-0 inline-flex items-center justify-center rounded-md text-xs font-medium transition-colors h-8 px-3 border border-input bg-transparent shadow-sm hover:bg-accent hover:text-accent-foreground" onclick="refreshAll()">
                    🔄 REFRESH
                </button>
            </div>

            <div class="flex items-center gap-4 flex-wrap justify-center 2xl:justify-end shrink-0 w-full 2xl:w-auto">
                <div class="flex items-center gap-2" data-testid="status-ws-connection">
                    <div class="flex h-7 w-7 items-center justify-center rounded-full bg-white/5 border border-white/5"><svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-wifi h-4 w-4 text-primary"><path d="M12 20h.01"></path><path d="M2 8.82a15 15 0 0 1 20 0"></path><path d="M5 12.859a10 10 0 0 1 14 0"></path><path d="M8.5 16.429a5 5 0 0 1 7 0"></path></svg></div>
                    <div class="flex flex-col"><span class="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">Feed</span><span class="text-sm font-mono font-medium text-foreground"><span class="text-primary font-medium">LIVE</span></span></div>
                </div>
                <div class="w-px h-8 bg-white/10 hidden sm:block"></div>
                <div class="flex items-center gap-2" data-testid="status-events-processed">
                    <div class="flex h-7 w-7 items-center justify-center rounded-full bg-white/5 border border-white/5"><svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-activity h-4 w-4 text-warning"><path d="M22 12h-2.48a2 2 0 0 0-1.93 1.46l-2.35 8.36a.25.25 0 0 1-.48 0L9.24 2.18a.25.25 0 0 0-.48 0l-2.35 8.36A2 2 0 0 1 4.49 12H2"></path></svg></div>
                    <div class="flex flex-col"><span class="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">Events (session)</span><span class="text-sm font-mono font-medium text-foreground">57,452</span></div>
                </div>
                <div class="w-px h-8 bg-white/10 hidden sm:block"></div>
                <div class="flex items-center gap-2" data-testid="status-wallets-discovered">
                    <div class="flex h-7 w-7 items-center justify-center rounded-full bg-white/5 border border-white/5"><svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-server h-4 w-4 text-info"><rect width="20" height="8" x="2" y="2" rx="2" ry="2"></rect><rect width="20" height="8" x="2" y="14" rx="2" ry="2"></rect><line x1="6" x2="6.01" y1="6" y2="6"></line><line x1="6" x2="6.01" y1="18" y2="18"></line></svg></div>
                    <div class="flex flex-col"><span class="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">Wallets Found</span><span class="text-sm font-mono font-medium text-foreground">47,014</span></div>
                </div>
                <div class="w-px h-8 bg-white/10 hidden lg:block"></div>
                <div class="flex items-center gap-2" data-testid="status-db-records">
                    <div class="flex h-7 w-7 items-center justify-center rounded-full bg-white/5 border border-white/5"><svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-database h-4 w-4 text-muted-foreground"><ellipse cx="12" cy="5" rx="9" ry="3"></ellipse><path d="M3 5V19A9 3 0 0 0 21 19V5"></path><path d="M3 12A9 3 0 0 0 21 12"></path></svg></div>
                    <div class="flex flex-col"><span class="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">DB Records</span><span class="text-sm font-mono font-medium text-foreground">270,734</span></div>
                </div>
                <div class="w-px h-8 bg-white/10 hidden lg:block"></div>
                <div class="flex items-center gap-2" data-testid="status-last-trade">
                    <div class="flex h-7 w-7 items-center justify-center rounded-full bg-white/5 border border-white/5"><svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-clock h-4 w-4 text-muted-foreground"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg></div>
                    <div class="flex flex-col"><span class="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">Last Trade</span><span class="text-sm font-mono font-medium text-foreground">3 minutes ago</span></div>
                </div>
            </div>
        </header>"""

    html = html.replace(old_full_header, new_header)
else:
    print("Header match failed.")

with open("templates/index.html", "w", encoding="utf-8") as f:
    f.write(html)

print("Updated grid layouts successfully.")
