# 時系列の再構成

TSR レポートは所見に時間軸を持たない。だから「A が B の原因」を判定できず、遅延も再起動も並列に置かれる。
must-gather には時刻が散在している。1本の年表にすると、レポートが原理的に出せない前後関係が見えることがある。

**毎回やるものではない。** 次のいずれかのとき、ユーザーへ提案する。

- 複数の所見の因果関係を判定したい（どちらが先か）
- ある障害の引き金となった変更を特定したい
- IS / IS-NOT の WHEN 側面が埋まらない（`references/kt-analysis.md`）

全所見の年表を自動では作らない。seed / inventory / export は触らない。

## パスの正

時刻ソースの実在は `tsr-inventory.yaml` と `references/must-gather-map.md` を先に見る。
下の表はヒントであり、ディレクトリ名を固定しない。`core/` が無い namespace がある。`host_service_logs` の形も gather で違う。
config の `tools.omc` が `skip` なら omc を提案しない。

PG の `metrics/`（とくに `prometheus_range/` や etcd の JSON）はこのスキルの gather では時系列の本丸になり得る。omc では読めない。jq で、大きなファイルは丸投げしない。

## 時刻情報の在り処

| ソース | 得られる時刻 | 備考 |
|--------|----------------|------|
| `namespaces/*/core/events.yaml`（ある場合） | firstTimestamp / lastTimestamp | 既定で数時間しか残らない。無い = 起きていない、ではない |
| PG `workload-scoped-resources/workload_events/` | warning / critical | Default の events とは別ソース |
| pod の `status.containerStatuses[].lastState.terminated.finishedAt` | 直前の再起動時刻と理由 | `lastState` は1世代だけ |
| pod の `status.containerStatuses[].state.running.startedAt` | 現在の稼働開始 | 上との差が再起動間隔 |
| node の `status.conditions[].lastTransitionTime` | MemoryPressure / DiskPressure / Ready | |
| `host_service_logs/` の kubelet / crio | 起動・再起動、eviction | 形は map を見る。大きいので絞る |
| MachineConfig / MCP の status | 設定変更の適用時刻 | 「変更が引き金か」の検証 |
| ClusterVersion の history | アップグレードの実施時刻 | 同上 |
| etcd や各 pod のログ行頭 | エラーの発生時刻 | 件数だけでなく分布 |
| CSV / Subscription の conditions | オペレータの状態遷移 | |
| PG `metrics/` の JSON | instant / range のサンプル時刻 | inventory の `metrics_dirs` を見る |

## 進め方

### 1. 時間窓を決める

全期間を並べると読めない。基準はレポートの Data collected（UTC）。そこから遡って数時間から数日。ユーザーと合意してから収集する。
窓を決めずに全ログをなめない。

### 2. 収集する

各ソースから (時刻, 対象, 事象) の3つ組で抜く。抽出はその場で組み立て、合意したコマンドだけ実行する。

抜き出しは調査 YAML とは別の作業ファイルにしてよい。プロジェクトの `.tsr-work/` に置く（一次ソースではない）。

### 3. 統合して並べる

**時刻はすべて UTC に揃える。** ソースによって RFC3339、journal、epoch が混ざる。ユーザーへ出すときは JST 併記してよい。

```
時刻 (UTC) | 対象 | 事象 | ソース
```

### 4. 解釈する

- **先行関係** — 原因は結果より前。逆順ならその向きの因果は否定できる。数少ない強い棄却材料。
- **同時多発** — 同一時刻に複数が落ちるなら、共通基盤（ホスト、ストレージ、ネットワーク）を疑う。
- **周期性** — 一定間隔なら cron、リース、プローブ、GC を疑う。

### 5. 相関に飛びつかない

時間的に近接しているだけでは因果の根拠にならない。
先行関係が確認できても、「因果と矛盾しない」であって証明ではない。

「A の後に B が起きている。因果があるとすれば A → B の向きであり、逆はない」
という書き方にとどめ、断定しない。
所見の `status` は、症状の確認と原因仮説の棄却を混ぜない。

## 制約（年表を出すときは必ず添える）

- **イベントは短期間で消える。** events に無い = 起きていない、ではない。
- **再起動履歴は直前の1回分しかない。** RESTARTS が数百でも、残っている時刻は1世代。
- **採取時点より後はわからない。** 年表の右端は Data collected。
- **ログのローテーションで古い行が失われている**ことがある。左端が「そこから始まった」とは限らない。

空白を根拠に何かを主張しない。証拠が無いことと、事象が無いことを混同しない。

## やってはいけないこと

- 毎回の所見で年表を作る。
- 窓を決めずにログを全件読む。
- 年表を `tsr-investigation.yaml` に埋め込む。
- 空白を「起きていない」の証拠にする。
- 近接だけで因果を断定する。
