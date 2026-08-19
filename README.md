# skills

Cursor Agent skills.

## tsr-investigator

Investigate a Red Hat **Technical Supportability Review with AI** (TSRwithAI) PDF against an extracted OpenShift must-gather. Companion **review** of existing TSR findings: one finding at a time, confirm against primary data, optional export. Not incident response.

The agent-facing `SKILL.md` is currently in Japanese. Python scripts are English.

On first use the skill briefs the human (what it does, how to talk to it, example phrases), then sets `briefing_done` in `tsr-config.yaml`. It does not start findings until that briefing is done.

Do **not** commit customer PDFs, must-gather trees, `tsr-config.yaml`, `tsr-investigation.yaml`, or `tsr-inventory.yaml`. Those stay in the investigation project.

### Install

Copy or clone this directory into Cursor skills:

- Personal: `~/.cursor/skills/tsr-investigator/`
- Project: `<repo>/.cursor/skills/tsr-investigator/`

### Layout

```
tsr-investigator/
  SKILL.md
  references/tool-setup.md
  references/must-gather-map.md
  references/kt-analysis.md   # IS / IS-NOT (per finding)
  references/timeline.md      # optional timeline reconstruction
  references/decision-materials.md  # decision brief after fact judgment
  scripts/setup.py
  scripts/seed.py         # PDF → YAML (deterministic, no LLM)
  scripts/inventory.py    # must-gather → tsr-inventory.yaml (catalog only)
  scripts/mg_inventory.py
  scripts/export.py       # YAML → xlsx/csv/md (optional, on request)
  scripts/lib.py
```
