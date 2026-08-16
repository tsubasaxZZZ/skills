# 解析ツールの準備

スキルはプロジェクトルートの `tsr-config.yaml` を読む。
このファイルが無ければ、まず `setup.py detect` のあと初回2問（omc / export 形式）を行い `setup.py write` する。

config があるセッションでは、ここに書いた「毎回確認」は `tools.*` に従う。
`omc: skip` なら omc のインストールも `omc use` も提案しない。

## 検出

```bash
python3 $SKILL/scripts/setup.py detect
```

または:

```bash
command -v omc yq jq pdftotext
```

omc が無くても grep / jq で調査できる。無理に勧めない。

| ツール | 役割 | 必須か |
|--------|------|--------|
| omc | must-gather を `oc` と同じ感覚で問い合わせる | 推奨（config で skip 可） |
| yq | YAML からフィールドを抜く | 任意 |
| jq | JSON（omc 出力および `$PG/metrics/*.json`） | あると便利 |
| pdftotext | seed.py が PDF を読むために必要 | seed 時に必要 |

## omc のインストール（固定）

Linux / macOS、および Windows 上の Git Bash / WSL。
**`$PATH` が通ったディレクトリに移動してから**実行する。`sudo` は使わない。

合意が取れたら、次をそのまま使う。

```bash
curl -sL "https://github.com/gmeghnag/omc/releases/latest/download/omc_$(uname)_$(uname -m).tar.gz" | tar xzf - omc && chmod +x ./omc

omc -h
```

Windows ネイティブ（cmd / PowerShell）ではこの手順は走らない。bash が無ければ `tools.omc: skip`。

## omc の初期化

config の `paths.must_gather` を起点にする。プラグインディレクトリを `use` する。
omc は一度に一つしか見られない。切り替えたら Default / PG のどちらを見ているか伝える。

```bash
MG=<paths.must_gather>
OCP=$(ls -d "$MG"/quay-io-openshift-release-dev-* | head -1)
PG=$(ls -d "$MG"/quay-io-pg-next-pg-must-gather-* | head -1)

omc use "$OCP"
omc get clusterversion
```

PG の `$PG/metrics/*.json` は omc 対象外。jq で読む。

## PDF と一次ソース

所見の切り出しは `seed.py`（pdftotext、`-layout` なし）。人が表を見るときだけ `pdftotext -layout` を別ファイルに出してよい。

一次ソースは `paths.investigation`（既定 `tsr-investigation.yaml`）。Markdown ログは使わない。
must-gather のカタログは `paths.inventory`（既定 `tsr-inventory.yaml`）。`seed.py` のあと `inventory.py` を一度走らせる。
IS/IS-NOT 表や年表は YAML に埋め込まない。作業ファイルは `.tsr-work/`。

## export

ユーザーが指示したときだけ `scripts/export.py`。xlsx には openpyxl が要る。
`pip install --user` は使わない。uv があれば uv、なければ `python3 -m venv .venv`。

合意後:

```bash
python3 $SKILL/scripts/setup.py ensure-xlsx
```

中身は概ね次と同等。

```bash
# uv があるとき
uv venv .venv
uv pip install --python .venv/bin/python openpyxl

# uv が無いとき
python3 -m venv .venv
.venv/bin/python -m pip install openpyxl
```

Windows では venv の Python は `.venv/Scripts/python.exe`。
export.py は `.venv` に openpyxl があれば、その interpreter で再実行する。

## OS 差

| | Linux | macOS | Windows |
|--|--------|--------|---------|
| このスキルの作業 | Python スクリプト（pathlib） | 同左 | 同左 |
| omc 導入 | 上記 curl 固定手順 | 同左 | Git Bash / WSL なら同左。それ以外は skip |
| poppler | poppler-utils | brew poppler | pdftotext.exe を PATH へ |
