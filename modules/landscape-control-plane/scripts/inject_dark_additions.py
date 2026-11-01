import sys

page_pt_path = "/opt/canonical/landscape/canonical/landscape/ui/skin/hokan/page.pt"
additions_path = "/tmp/landscape-dark-additions.css"

with open(page_pt_path, "r", encoding="utf-8") as f:
    content = f.read()

with open(additions_path, "r", encoding="utf-8") as f:
    additions = f.read()

if "/* 6. Pill Select: All / None" not in content:
    content = content.replace("/* Botoes Globais */", additions + "\n/* Botoes Globais */")
    with open(page_pt_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("INJECT_SUCCESS")
else:
    print("ALREADY_INJECTED")
