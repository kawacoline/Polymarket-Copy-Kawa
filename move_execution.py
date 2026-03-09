import re

with open("templates/index.html", "r", encoding="utf-8") as f:
    html = f.read()

# 1. Update accounts grid
html = html.replace('id="accountsList" class="accounts-grid"', 'id="accountsList" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6"')

# Find the header
header_match = re.search(r'(<header class="glass-header sticky top-0 z-50[^>]+>.*?</header>)', html, re.DOTALL)
if header_match:
    header_html = header_match.group(1)

    # Find the Execution Controls block
    exec_match = re.search(r'<!-- Execution Controls -->\s*<div class="glass-panel rounded-xl p-6 relative overflow-hidden">\s*<div class="text-xs font-bold[^>]+>ENGINE EXECUTION</div>(.*?)</div>\s*<!-- Export Actions -->', html, re.DOTALL)
    if exec_match:
        # Create a new sticky bar for the engine controls
        advanced_controls = """
        <!-- Engine Controls (Pinned) -->
        <div class="glass-header w-full px-6 py-3 sticky top-[73px] z-40 flex items-center justify-between gap-4 border-b border-white/5 backdrop-blur-xl bg-background/90 shadow-sm transition-all">
            <div class="flex items-center gap-4">
                <div class="text-xs font-bold text-muted-foreground uppercase tracking-widest hidden md:block">ENGINE EXECUTION</div>
                <div class="w-px h-4 bg-white/10 hidden md:block"></div>
                
                <button id="startBtn" class="inline-flex items-center justify-center rounded-md text-xs font-medium transition-colors h-8 px-4 bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30 border border-emerald-500/50 shadow shadow-emerald-500/20 mr-2" onclick="startBot()">
                    <span class="mr-2">▶</span> START
                </button>
                <button id="stopBtn" class="inline-flex items-center justify-center rounded-md text-xs font-medium transition-colors h-8 px-4 border border-input bg-transparent shadow-sm hover:bg-accent hover:text-accent-foreground" onclick="stopBot()" disabled>
                    <span class="mr-2">⏸</span> PAUSE
                </button>
                <button id="panicSellBtn" class="inline-flex items-center justify-center rounded-md text-xs font-medium transition-colors h-8 px-4 bg-destructive text-destructive-foreground shadow hover:bg-destructive/90 ml-2" onclick="showModal('panicSellModal')">
                    <span class="mr-2">🚨</span> PANIC
                </button>
            </div>
            
            <div class="flex items-center gap-4">
                <div class="flex items-center gap-2">
                    <span id="statusIndicator" class="dot stopped"></span>
                    <span id="statusText" class="text-xs font-semibold tracking-wide">OFFLINE</span>
                </div>
                <div class="w-px h-4 bg-white/10"></div>
                <div class="flex items-center gap-2 text-xs">
                    <span style="color: var(--text-dim);">DRY RUN:</span>
                    <label class="toggle-switch transform scale-75 origin-left" style="margin:0;">
                        <input type="checkbox" id="dryRunToggle" onchange="toggleDryRun()" checked>
                        <span class="slider"></span>
                    </label>
                </div>
                <div class="w-px h-4 bg-white/10 hidden sm:block"></div>
                <button class="inline-flex items-center justify-center rounded-md text-xs font-medium transition-colors h-8 px-3 border border-input bg-transparent shadow-sm hover:bg-accent hover:text-accent-foreground hidden sm:inline-flex" onclick="refreshAll()">
                    🔄
                </button>
            </div>
        </div>
        """

        # Append advanced controls right after the header
        html = html.replace(header_html, header_html + advanced_controls)

        # Remove the old execution box
        html = re.sub(r'<!-- Execution Controls -->\s*<div class="glass-panel rounded-xl p-6 relative overflow-hidden">.*?</div>\s*<!-- Export Actions -->', r'<!-- Export Actions -->', html, flags=re.DOTALL)
        
        # In the grid, Export Actions is alone now. It might look stretched or weird. 
        # But let's let the user see it, or move Export Actions somewhere else if needed.
        # Actually Export Actions and "REPORTS" is taking up a whole 1/3 of the space now.
        # We can just leave it as grid-cols-1, or remove the grid if it's the only one left.
        # The grid is: <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        # Let's change the grid to be just normal or smaller width for export.
        pass

with open("templates/index.html", "w", encoding="utf-8") as f:
    f.write(html)

print("Updated execution controls and accounts grid.")
