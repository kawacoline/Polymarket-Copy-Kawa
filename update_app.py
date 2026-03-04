import re

file_path = "static/js/app.js"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Replace empty-state components
content = content.replace('class="empty-state"', 'class="flex flex-col items-center justify-center p-8 text-center text-muted-foreground bg-white/5 rounded-xl border border-white/5"')
content = content.replace('class="empty-state-icon"', 'class="text-4xl mb-4 opacity-50"')

# Replace table components
content = content.replace('class="data-table"', 'class="w-full text-sm text-left whitespace-nowrap"')
content = content.replace('<th>', '<th class="px-4 py-3 font-semibold text-muted-foreground border-b border-border/50">')
content = content.replace('<th ', '<th class="px-4 py-3 font-semibold text-muted-foreground border-b border-border/50" ')

content = content.replace('<td>', '<td class="px-4 py-3 border-b border-white/5 group-hover:bg-white/5 transition-colors">')
content = content.replace('<td ', '<td class="px-4 py-3 border-b border-white/5 group-hover:bg-white/5 transition-colors" ')

content = content.replace('<tr>', '<tr class="group hover:bg-white/5 transition-colors">')

# Replace buttons in app.js
content = content.replace('class="btn btn-secondary btn-sm"', 'class="inline-flex items-center justify-center rounded-md text-xs font-medium transition-colors border border-input bg-transparent shadow-sm hover:bg-accent hover:text-accent-foreground h-8 px-3"')
content = content.replace('class="btn btn-primary btn-sm"', 'class="inline-flex items-center justify-center rounded-md text-xs font-medium transition-colors bg-primary text-primary-foreground shadow hover:bg-primary/90 h-8 px-3"')
content = content.replace('class="btn btn-danger btn-sm"', 'class="inline-flex items-center justify-center rounded-md text-xs font-medium transition-colors bg-destructive text-destructive-foreground shadow-sm hover:bg-destructive/90 h-8 px-3"')

# Replace account card components
content = re.sub(r'class="account-card([^"]*)"', r'class="glass-panel rounded-xl p-5 mb-4 border border-white/10 transition-all hover:border-white/20\1"', content)
content = content.replace('class="account-header"', 'class="flex items-start justify-between mb-4 pb-4 border-b border-white/10"')
content = content.replace('class="account-info"', 'class="flex-1 min-w-0 pr-4"')
content = content.replace('class="account-name"', 'class="font-display font-semibold text-lg text-foreground flex items-center gap-2 truncate"')
content = content.replace('class="techno-badge"', 'class="inline-flex shrink-0 items-center justify-center rounded-full border border-destructive/50 bg-destructive/10 px-2 py-0.5 text-[10px] font-semibold text-destructive uppercase tracking-wider"')
content = content.replace('class="account-addr"', 'class="font-mono text-sm text-muted-foreground flex items-center gap-2 mt-1 truncate"')
content = content.replace('class="account-stats"', 'class="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4"')
content = content.replace('class="stat-group"', 'class="flex items-center gap-1.5 text-sm bg-black/20 px-2 py-1 rounded-md border border-white/5"')
content = content.replace('class="account-tags"', 'class="flex flex-wrap gap-2 mt-3"')
content = content.replace('class="account-tag"', 'class="inline-flex items-center rounded-md border border-white/10 bg-white/5 px-2 py-1 text-xs font-medium text-foreground"')
content = content.replace('class="account-actions"', 'class="flex flex-col items-end gap-3 shrink-0"')

content = content.replace('class="detail-item"', 'class="flex flex-col gap-1"')
content = content.replace('class="detail-label"', 'class="text-xs font-medium text-muted-foreground uppercase tracking-wider"')

# Position card (for withdrawals list etc)
content = content.replace('class="position-card"', 'class="flex flex-col p-4 rounded-lg bg-black/20 border border-white/5 mb-2 hover:bg-white/5 transition-colors gap-2"')

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Updated app.js with Tailwind CSS classes")
