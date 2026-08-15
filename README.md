# skills

Cursor Agent skills.

## tsr-investigator

Investigate a Red Hat **Technical Supportability Review with AI** (TSRwithAI) PDF against an extracted OpenShift must-gather. Companion workflow: one finding at a time, confirm against primary data, optional export to xlsx/csv/md.

The agent-facing `SKILL.md` is currently in Japanese. Python scripts are English.

Do **not** commit customer PDFs, must-gather trees, `tsr-config.yaml`, or `tsr-investigation.yaml`. Those stay in the investigation project.

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
  scripts/setup.py
  scripts/seed.py      # PDF → YAML (deterministic, no LLM)
  scripts/export.py    # YAML → xlsx/csv/md (optional, on request)
  scripts/lib.py
```
