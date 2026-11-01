import os

with open("/tmp/landscape-dark-additions.css", "r", encoding="utf-8") as f:
    additions = f.read()

for p in [
    "/opt/canonical/landscape/canonical/landscape/static/skin/hokan/widgets.css",
    "/opt/canonical/landscape/canonical/landscape/static/skin/hokan/backward.css",
    "/opt/canonical/landscape/canonical/landscape/static/skin/manx/base.css"
]:
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            c = f.read()
        if "/* 6. Pill Select: All / None" not in c:
            with open(p, "a", encoding="utf-8") as f:
                f.write("\n\n" + additions)
            print(f"APPENDED_TO: {p}")
        else:
            print(f"ALREADY_IN: {p}")
