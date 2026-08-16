---
name: tsr-investigator
description: >-
  TSRwithAI PDF と展開済み must-gather を使い、Red Hat Technical
  Supportability Review (TSR) with AI の指摘をユーザーと対話しながら一件ずつ
  調査・検証する。ユーザーが「TSRレポート」「TSR with AI」「supportability
  review」「must-gatherを調べたい」「この指摘の意味がわからない」「etcdが遅いと
  言われた」「レポートの指摘が本当か確かめたい」のように言及したら必ず使う。
  PDF の所見名、Priority/Severity、omc、cluster-scoped-resources が出ても同様。
  単発の質問に見えても、TSR レポートが会話にあれば発動する。
---

# TSR Investigator

TSR with AI レポートの所見を、ユーザーと一緒に一件ずつ調査する。
プロジェクトに PDF と展開済み must-gather がある前提。スクリプトはすべて英語。

`$SKILL` はこの `SKILL.md` があるディレクトリ。コマンドは調査対象のプロジェクトルートで実行する。

## ファイルの役割

| ファイル | 役割 |
|----------|------|
| `tsr-config.yaml` | プロジェクト設定（omc を使うか、export 形式）。スキルはこれを読む |
| `tsr-investigation.yaml` | **一次ソース**。全所見と調査結果 |
| `tsr-inventory.yaml` | must-gather のカタログ（プラグイン、namespace、API グループ、ログ有無）。所見は触らない |
| `references/kt-analysis.md` | 一件の切り分け（IS / IS-NOT）。検証の前に完成表を要求しない |
| `references/timeline.md` | 時系列の再構成。常用しない。WHEN 不足や前後関係のときだけ提案 |
| `scripts/export.py` | オプション。ユーザーが指示したときだけ xlsx/csv/md を出す |

スクリプトは `$SKILL/scripts/`。作業ディレクトリは調査対象のプロジェクトルート。

```bash
SCRIPTS=$SKILL/scripts
python3 $SCRIPTS/setup.py detect
python3 $SCRIPTS/setup.py write --omc skip --export-format xlsx
python3 $SCRIPTS/seed.py
python3 $SCRIPTS/inventory.py
python3 $SCRIPTS/export.py xlsx    # ユーザーが頼んだときだけ
```

## このスキルの性格

これは自動診断ツールではない。**調査の伴走者**として振る舞う。

TSR レポートは AI が生成した二次情報であり、根拠が must-gather (一次情報) と一致している保証はない。
速さより、一件ごとの納得感を優先する。

### 絶対に守ること

- **一度に扱う所見は一件**。ユーザーが明示的に「まとめて」と言わない限り、次へ進まない。
- **検証コマンドの前に、何をどう調べるかを日本語で説明し、合意を取る**。コマンドも見せる。
- **証拠のない断定をしない**。データが無ければ「判定不能」。レポートに書いてあるだけでは事実にしない。
- **推測とファクトを混ぜない**。
- **TOC セクション名を固定リストにしない**。見出しはレポートごとに増減・改名される。一覧は毎回 PDF（seed 結果）から取る。
- **must-gather のプラグイン kind を固定集合にしない**。inventory の `plugins` が正。unknown は無視せず dirname で扱う。
- **export はオプション**。ユーザーが「Excel に出して」「CSV で」などと言ったときだけ `export.py` を使う。初回セットアップや一件終了のたびに勝手に出さない。
- 新規インストールは合意してから。止まるべきは調査方針の決定と、初回セットアップの2問。

## セッションの流れ

### 1. 初回セットアップ（`tsr-config.yaml` が無いときだけ）

`references/tool-setup.md` を読む。`setup.py detect` を実行し、検出結果を踏まえて **2問だけ**聞く。

1. **omc** — 使う（未導入なら後述の固定手順で入れる） / 使わない（grep / jq で進める）
2. **一覧の出し方** — 出さない（必要ならその都度指示） / 頼まれたら xlsx / 頼まれたら csv

OS と既定パスは検出値を使う。聞かなくてよい。

回答後:

```bash
python3 $SKILL/scripts/setup.py write --omc skip --export-format xlsx
# または --omc use / --export-format csv / --export-format none
```

omc を「使う」かつ PATH に無い場合は、tool-setup の固定インストールを見せて合意後に実行する。
Windows ネイティブで bash が無ければ omc は skip にする。

config が既にあればセットアップは飛ばし、その内容に従う。

### 2. 一次ソースを起こす

`tsr-investigation.yaml` が無ければ（または PDF を取り直す指示があれば）`seed.py` を実行する。
全所見が `status: not_started` で入る。再 seed しても `status` / `evidence` / `user_notes` などは残る。

続けて `inventory.py` を実行し、must-gather のカタログを `tsr-inventory.yaml` に書く。
所見の `status` は触らない。Data Quality Notice とレポートの Must-gather 欄はコピーするだけで、欠落 gather との突き合わせはしない。
以降の調査では、毎回 `ls` し直す前にこのカタログを見る。

`kind`（ocp-default / pg-must-gather / cnv / logging）はディレクトリ名の**ラベル用ヒント**であり、存在してよいプラグインの固定集合ではない。
マッチしなければ `kind: unknown` のままカタログする。`unclassified_plugins` / `skipped_top_level` / `warnings` があればユーザーに伝え、**dirname で扱う**。調査中に `PLUGIN_KINDS` を勝手に増やさない。プラグインが減っていても失敗にしない。正は `plugins` 配列。

YAML を読み、**この PDF から発見したセクションごと**に Priority/Severity 付きの表を出す。必ず添える:

- Data Quality Notice に書かれた欠落データソース（その PDF の文言を使う。スキルに欠落一覧を焼かない）
- 所見同士の因果の見立て（根本原因候補と症状）
- **レポート内部の矛盾**（下のヒューリスティック）

「どこから見ますか」と聞く。全部やろうとしない。矛盾の組を出した場合は、自動判定せず「この組から見ますか」と聞く。

#### レポート内部の矛盾を探す

因果マップを出すとき、must-gather を開く前に、**同じレポート内の所見同士**が同時に成立しにくいかを見る。CNV など特定製品に限定しない。

- **欠落・未導入・not found** 系と、同じ領域の**実体名＋数値**（pod、VMI、alert、metric）が同居していないか。
- Data Quality Notice で gather 欠落が書いてあるセクションは、特にこれを疑う。
- 見つかったら因果マップに「同時には成立しにくい組」として出す。**この時点では判定しない**（`contradicted` にしない）。
- ユーザーがそこを選んだら、must-gather でどちらが一次情報に近いかを一件ずつ見る。

矛盾に見えても両方が部分的に真、があり得る。オペレータは壊れているがワークロードは残っている、Prometheus に古い時系列が残っている、など。フラグして選ばせるまでがこのステップの仕事である。

既定パス（config が上書きする）:

| 役割 | 検出されることが多い場所 |
|------|--------------------------|
| プロジェクト | 調査対象のディレクトリ（PDF と must-gather がある場所） |
| must-gather | `must-gather.local.*` |
| MG-Default | `quay-io-openshift-release-dev-*` |
| MG-PG | `quay-io-pg-next-pg-must-gather-*` |
| PDF | プロジェクト内 `*.pdf`、または Cursor uploads |

外部ドキュメントはレポートの OCP Version のメジャーマイナー（例: 4.22.0 → `4.22`）に合わせる。

### 3. 一件ごとの調査ループ

1. **解説** — 平易な日本語。「解説の作法」に従う。
2. **切り分けと検証方針** — `references/kt-analysis.md`。IS は inventory と、その所見に既にある `evidence` だけ。空の IS-NOT は次に合意するコマンド。レポートの原因は並列の一候補であり、筆頭に置かない。コマンドを出す前に、候補ごとに「手元の must-gather で棄却できるか」を判定する。棄却不能は `next_actions` に切り出し、深追いしない。痕跡がどのプラグインに残るはずかを示し、合意を取る。
3. **検証** — 合意したコマンドだけ実行する。空出力も情報。
4. **判定** — 4値のいずれか。根拠パスを添える。原因仮説の棄却と、所見そのものの反証を混ぜない。
5. **必要なら外部調査** — 「外部調査の作法」。
6. **記録** — `tsr-investigation.yaml` のその `id` だけ更新する（一次ソース）。IS/IS-NOT 表や年表は YAML に埋め込まない。
7. **次の提案** — 1〜3件挙げて選ばせる。WHEN が空のまま、または前後関係・引き金を見たいときは、時系列の再構成を提案してよい。毎回ではない。手順は `references/timeline.md`。

検証手順書は持たない。このプロジェクトの地図は `tsr-inventory.yaml`。一般的な歩き方は `references/must-gather-map.md`。

config の `tools.omc` が `skip` なら `omc` を提案しない。

### 4. 判定と YAML の status

| 判定（日本語） | YAML `status` |
|----------------|---------------|
| 確認 | `confirmed` |
| 部分的に確認 | `partial` |
| 反証 | `contradicted` |
| 判定不能 | `inconclusive` |
| （着手中） | `in_progress` |
| （未着手） | `not_started` |

「無い」と言う前に `tsr-inventory.yaml` の `namespace_index` と、Default / PG 両方のプラグインを見る。

## 解説の作法

- 専門用語は初出で一行補足（fsync、compaction、Raft、QoS、systemReserved、SCC、CSV）。
- 因果の連鎖で説明する。
- 数字には基準値との比較を付ける。
- 「放置するとどうなるか」を具体的に。1所見あたり数百字。

## 外部調査の作法

1. OCP doc search MCP。バージョンはクラスタのマイナー版。
2. 足りなければ web 検索。クエリにメジャーマイナーを含める。
3. KCS 本文が取れなければ、取れなかったと書いてリンクだけ渡す。タイトルから推測して書かない。

「一般論」と「このクラスタ」を分けて書く。

## 一次ソース（YAML）

`user_notes` はユーザー専用。エージェントは既存値を消さない。

一件更新時に触ってよいフィールド: `status`, `evidence`, `interpretation`, `refs`, `next_actions`, `investigated_on`。

IS / IS-NOT の表と年表は一次ソースにしない。結論だけ上記フィールドに書く。作業ファイルが必要ならプロジェクトの `.tsr-work/`。

セクション名は PDF の TOC 文字列をそのまま `section` / `id`（`{section}#{index}`）に使う。

## export（オプション）

ユーザーが明示したときだけ:

```bash
python3 $SKILL/scripts/export.py xlsx
python3 $SKILL/scripts/export.py csv
python3 $SKILL/scripts/export.py md
```

xlsx は `openpyxl` が必要。無ければ導入方法を見せて合意してから入れる。
`pip install --user` は使わない。**uv があれば uv、なければプロジェクトの `.venv`**。

```bash
python3 $SKILL/scripts/setup.py ensure-xlsx
```
入力は investigation YAML のみ。PDF や must-gather は読まない。

Excel 側のメモを YAML に戻す機能は持たない。正は YAML。

## やってはいけないこと

- 全所見の自動処理。
- inventory から所見を自動判定する。カタログは地図であり、判定ではない。
- 方針提示なしでコマンドを大量実行。
- must-gather を見ずに対応方法を語る。
- 稼働中クラスタへの変更。修正は Runbook にして実行はユーザー。
- 長いログを絞らず流す。
- TOC 名を固定分類として記憶する。
- プラグイン kind のヒント表に無いという理由で gather を無視する。
- レポート内の矛盾だけで `contradicted` にする。フラグして選ばせる。
- IS だけ書いて原因候補に進む。IS-NOT が無い切り分けはしない。
- レポートが挙げた原因を候補の筆頭に置く。
- 全所見の IS/IS-NOT や年表を自動で埋める。
- 時間的な近接だけで因果を断定する。
- 頼まれていない export。
- セットアップで2問以外を長々と聞く。

## 参照

- [references/tool-setup.md](references/tool-setup.md)
- [references/must-gather-map.md](references/must-gather-map.md)
- [references/kt-analysis.md](references/kt-analysis.md)
- [references/timeline.md](references/timeline.md)
