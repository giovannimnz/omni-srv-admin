import os

section_10 = """
/* 10. Activity & System Progress Bars (.bar-body, .bar-body-status) */
.bar-body,
#activity-detail .bar-body,
#activities-table .bar-body,
.activity-detail-table .bar-body,
.bar-body-status {
  background: #101720 !important;
  background-color: #101720 !important;
  border: 1px solid #2a3746 !important;
  border-radius: 4px !important;
  box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.6) !important;
}

#activity-detail .bar-body-status {
  background: #101720 !important;
  background-color: #101720 !important;
  border: 1px solid #2a3746 !important;
  border-radius: 4px !important;
  overflow: hidden !important;
}

.bar-body .good,
.bar-body .good > .bar-body-block,
.bar-body-block.good {
  background-color: #16a34a !important;
}

.bar-body .warning,
.bar-body .warning > .bar-body-block,
.bar-body-block.warning {
  background-color: #d97706 !important;
}

.bar-body .bad,
.bar-body .bad > .bar-body-block,
.bar-body-block.bad {
  background-color: #dc2626 !important;
}

.bar-body-block.activity-status-queued,
.bar-body-block.activity-status-delivered,
.bar-body-block.activity-status-in-progress,
.bar-body-block.activity-status-succeeded {
  background-color: #2563eb !important;
}

.bar-body-block.activity-status-undelivered {
  background-color: #1e293b !important;
}

#activity-detail table,
.activity-detail-table {
  background-color: transparent !important;
}
"""

page_pt = "/opt/canonical/landscape/canonical/landscape/ui/skin/hokan/page.pt"
if os.path.exists(page_pt):
    with open(page_pt, "r", encoding="utf-8") as f:
        c = f.read()
    if "/* 10. Activity & System Progress Bars" not in c:
        c = c.replace("/* Botoes Globais */", section_10.strip() + "\n\n/* Botoes Globais */")
        with open(page_pt, "w", encoding="utf-8") as f:
            f.write(c)
        print("APPLIED_TO_PAGE_PT")
    else:
        print("ALREADY_IN_PAGE_PT")

for p in [
    "/opt/canonical/landscape/canonical/landscape/static/skin/hokan/widgets.css",
    "/opt/canonical/landscape/canonical/landscape/static/skin/hokan/backward.css"
]:
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            c = f.read()
        if "/* 10. Activity & System Progress Bars" not in c:
            with open(p, "a", encoding="utf-8") as f:
                f.write("\n\n" + section_10.strip() + "\n")
            print(f"APPLIED_TO_{p}")
        else:
            print(f"ALREADY_IN_{p}")
