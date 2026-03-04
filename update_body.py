import re

file_path = "templates/index.html"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Replace .container
content = content.replace('<div class="container">', '<div class="max-w-[1800px] mx-auto px-4 sm:px-6 lg:px-8 py-6">')

# Replace .stats-grid
content = content.replace('<div class="stats-grid">', '<div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4 mb-8">')

# Replace .glass-card -> glass-panel rounded-xl p-6 relative overflow-hidden
content = re.sub(r'class="([^"]*)glass-card([^"]*)"', r'class="\1glass-panel rounded-xl p-6 relative overflow-hidden\2"', content)

# Replace .stat-label -> text-sm font-semibold text-muted-foreground uppercase tracking-wider
content = re.sub(r'class="([^"]*)stat-label([^"]*)"', r'class="\1text-sm font-semibold text-muted-foreground uppercase tracking-wider\2"', content)

# Replace .stat-value -> text-3xl font-display font-bold tabular-nums text-foreground
content = re.sub(r'class="([^"]*)stat-value([^"]*)"', r'class="\1text-3xl font-display font-bold tabular-nums text-foreground\2"', content)

# Replace .control-panel -> grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8
content = content.replace('<div class="control-panel">', '<div class="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">')

# Replace .section-title -> text-xs font-bold text-muted-foreground uppercase tracking-widest mb-4 flex items-center justify-between
content = re.sub(r'class="([^"]*)section-title([^"]*)"', r'class="\1text-xs font-bold text-muted-foreground uppercase tracking-widest mb-4 flex items-center justify-between\2"', content)

# Replace .action-group -> flex flex-col sm:flex-row gap-3
content = re.sub(r'class="([^"]*)action-group([^"]*)"', r'class="\1flex flex-col sm:flex-row flex-wrap gap-3\2"', content)

# Replace buttons
content = content.replace('class="btn btn-primary"', 'class="inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 disabled:pointer-events-none disabled:opacity-50 h-9 px-4 py-2 bg-primary text-primary-foreground shadow hover:bg-primary/90"')
content = content.replace('class="btn btn-secondary"', 'class="inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 disabled:pointer-events-none disabled:opacity-50 h-9 px-4 py-2 border border-input bg-transparent shadow-sm hover:bg-accent hover:text-accent-foreground"')
content = content.replace('class="btn btn-danger"', 'class="inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 disabled:pointer-events-none disabled:opacity-50 h-9 px-4 py-2 bg-destructive text-destructive-foreground shadow-sm hover:bg-destructive/90"')

# Button sm variants
content = content.replace('class="btn btn-secondary btn-sm"', 'class="inline-flex items-center justify-center rounded-md text-xs font-medium transition-colors border border-input bg-transparent shadow-sm hover:bg-accent hover:text-accent-foreground h-8 px-3"')
content = content.replace('class="btn btn-primary btn-sm"', 'class="inline-flex items-center justify-center rounded-md text-xs font-medium transition-colors bg-primary text-primary-foreground shadow hover:bg-primary/90 h-8 px-3"')

# Status module
content = content.replace('<div class="status-module"', '<div class="flex flex-col gap-3 p-4 rounded-lg bg-black/20 border border-white/5"')

# Status pills
content = re.sub(r'class="([^"]*)status-pill([^"]*)"', r'class="\1flex items-center justify-between text-sm\2"', content)

# Loading spinners
content = re.sub(r'class="([^"]*)loading-spinner([^"]*)"', r'class="\1flex flex-col items-center justify-center py-12 text-muted-foreground space-y-4\2"', content)

# Text inputs
content = re.sub(r'class="([^"]*)form-input([^"]*)"', r'class="\1flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50\2"', content)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Updated body structure of index.html with Tailwind CSS classes")
