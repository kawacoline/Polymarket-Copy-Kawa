import re

with open('templates/polymarket_design_rip_formatted.html', 'r', encoding='utf-8') as f:
    rip_html = f.read()

with open('templates/index.html', 'r', encoding='utf-8') as f:
    index_html = f.read()

# Extract <style>...</style> from rip_html
style_match = re.search(r'<style>.*?</style>', rip_html, re.DOTALL)
if style_match:
    new_style = style_match.group(0)
else:
    print("Could not find style in rip_html")
    exit(1)

# Extract <header class="glass-header ...">...</header> from rip_html
header_match = re.search(r'<header class="glass-header .*?</header>', rip_html, re.DOTALL)
if header_match:
    new_header = header_match.group(0)
    # The header in rip has some hardcoded values, but we can keep them for now.
    # It also has "Nexus PolyWatch", we should probably change it back to COMMAND CENTER
    new_header = new_header.replace('Nexus PolyWatch', '⚡ COMMAND CENTER')
    new_header = new_header.replace('Polymarket Bot Intelligence', 'Polymarket Multi-Account Copy Trade Engine')
else:
    print("Could not find header in rip_html")
    exit(1)

# Replace <style>...</style> in index_html
index_html = re.sub(r'<style>.*?</style>', new_style, index_html, flags=re.DOTALL)

# Replace <header class="page-header">...</header> in index_html
# Wait, let's be more specific with the old header
old_header_pattern = r'<header class="page-header">.*?</header>'
index_html = re.sub(old_header_pattern, new_header, index_html, flags=re.DOTALL)

# Let's also replace the main container class if needed, but index.html uses `<div class="container">`.
# rip uses `<div class="min-h-screen bg-[#0A0D14] ...">` and `<main class="px-4 ...">`
# Let's just focus on replacing the style and header for now to see how it looks.

with open('templates/index.html', 'w', encoding='utf-8') as f:
    f.write(index_html)

print("Successfully updated index.html with new CSS and Header.")
