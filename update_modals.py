import re

file_path = "templates/index.html"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace('class="modal"', 'class="modal fixed inset-0 z-[100] hidden items-center justify-center bg-black/80 backdrop-blur-sm"')
content = content.replace('class="modal-content"', 'class="modal-content w-full max-w-md rounded-2xl border border-white/10 bg-card p-6 shadow-2xl transition-all duration-300 transform scale-100 mx-4 relative"')
content = re.sub(r'class="([^"]*)modal-title([^"]*)"', r'class="\1modal-title text-xl font-display font-bold text-foreground\2"', content)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Updated modals in index.html to use Tailwind CSS classes")
