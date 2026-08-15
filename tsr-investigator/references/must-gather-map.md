# must-gather の歩き方

「どこに何があるか」の地図。所見ごとの検証手順ではない。
検証方法はユーザーと一緒にその場で組み立てる。

パスの正は `tsr-config.yaml` の `paths.must_gather`。無ければプロジェクト内の `must-gather.local.*` を `ls` で確認する。

## このディレクトリの起点

```bash
MG=<paths.must_gather>   # typically must-gather.local.<id>
OCP=$(ls -d "$MG"/quay-io-openshift-release-dev-* | head -1)          # MG-Default
PG=$(ls -d "$MG"/quay-io-pg-next-pg-must-gather-* | head -1)          # MG-PG
```

TSR が MG-Default と MG-PG の両方を挙げていれば、「無い」と判定する前に `$OCP` と `$PG` の両方を探す。

Data Quality Notice に欠落 gather が書いてあれば、その gather にしか無い情報は判定不能。
ただし Default/PG に同名 namespace や CR があれば、欠落 gather がなくても検証できる。

## ディレクトリ構造

トップは `must-gather.local.*/<plugin>/`。プラグイン配下の形は典型的には次。
**namespace によって `core/` が無い**こともある（例: `$OCP/namespaces/openshift-etcd/` は
`pods/` と ns YAML が中心）。パスは断定せず、先に `ls` する。

```
$OCP/   # 標準 OpenShift must-gather
├── cluster-scoped-resources/
│   ├── core/nodes/                 ノード YAML (capacity, allocatable, labels, taints)
│   ├── config.openshift.io/        clusterversion, infrastructure, network など
│   ├── operator.openshift.io/
│   └── machineconfiguration.openshift.io/
├── namespaces/<ns>/
│   ├── core/                       ある場合: pods.yaml, events.yaml
│   ├── pods/<pod>/<container>/<container>/logs/  current.log, previous.log, rotated/
│   └── <api-group>/
├── nodes/<node>/                   dmesg, <node>_logs_kubelet.gz, lscpu など
├── host_service_logs/masters/      kubelet_service.log, crio_service.log（masters まとめて）
├── etcd_info/                      endpoint_health/status, member_list, alarm_list
└── monitoring/                     prometheus, alertmanager

$PG/    # pg-must-gather（TSR 用。メトリクスと workload 視点）
├── cluster-scoped-resources/       controlplane_tuning/, commands/ など
├── namespaces/                     Default より少ない。無い ≠ クラスタに無い
├── nodes/                          nfs_*.txt など PG 独自ファイルも含む
├── metrics/
│   ├── etcd/                       wal fsync / commit / peer RTT / firing alerts の JSON
│   ├── prometheus_instant/
│   ├── prometheus_range/
│   ├── node_pressure/
│   └── volumes/
└── workload-scoped-resources/
    ├── commands/                   pods_wide など
    └── workload_events/            warning / critical イベント
```

存在しないディレクトリがあること自体が情報になる。
たとえば `$OCP/namespaces/openshift-cnv/` がなければ、`$PG/namespaces/openshift-cnv/` も見る。
両方無ければ「未インストール」か「収集対象外」かを、Data Quality Notice と合わせて切り分ける。
後者なら判定不能であり、前者と混同してはいけない。

`storage.k8s.io` など API グループのディレクトリは gather によって無いことがある。
StorageClass を探すときは `$OCP` 全体を検索し、無ければその旨を書いて判定する。

## omc でできること / できないこと

できること（`omc use "$OCP"` または `"$PG"` のうえで）: `oc` の読み取り系の大半。

```bash
omc get nodes -o wide
omc get pods -A | grep -v Running
omc describe node master-0
omc get co
omc get events -A --sort-by='.lastTimestamp'
omc logs <pod> -c <container> -n <ns>
omc logs <pod> -c <container> -n <ns> --previous
omc prom rules -s firing          # 今 use している側の収集分。PG の metrics JSON とは別物
omc etcd health                   # サブコマンドの有無はバージョン依存
omc get pods -A -o json | jq '...'
```

できないこと:

- 収集時点より後の情報、live なクラスタへの接続
- **一度に Default と PG を同時に見ること**
- **`$PG/metrics/**/*.json` の PromQL ダンプ**（omc ではなく jq で読む）

must-gather はスナップショットである。「今どうなっているか」は答えられない。
レポートの Data collected 日時を意識し、ユーザーが別タイムゾーンで話しているときは変換して伝える。

omc が期待通りに動かない場合は生ファイルを読む。両方使ってよい。

## 情報の在り処

所見の種類ごとに、まず当たるべき場所。ここはヒントであり手順書ではない。

**ノードのリソース関連** (overcommit, systemReserved, memory 使用率)

- `$OCP/cluster-scoped-resources/core/nodes/<node>.yaml` の `status.capacity` と `status.allocatable`
- allocatable と capacity の差分から reserved の実効値が読める
- KubeletConfig: `$OCP/cluster-scoped-resources/machineconfiguration.openshift.io/kubeletconfigs/`
  および `$PG/cluster-scoped-resources/controlplane_tuning/kubeletconfigs.yaml`
- pod ごとの requests/limits は `omc get pods -A -o json`（use 中のプラグイン分）から集計する
- 使用率の時系列寄りの数値: `$PG/metrics/node_pressure/`

**etcd 関連**

- ログ: `$OCP/namespaces/openshift-etcd/pods/etcd-<node>/etcd/etcd/logs/current.log`
- `grep -c` で件数を数えてからパターンを絞る。全文を読もうとしない
- メンバー情報: `$OCP/etcd_info/`
- **分位点（wal fsync / backend commit / peer RTT）は `$PG/metrics/etcd/` の JSON で突合できる。**
  標準 must-gather だけでは再現できない、が MG-PG があるケースの正解ではない。
  例: `etcd_disk_wal_fsync_duration_seconds_bucket_99.json` の value を PDF の数値と突き合わせる
- firing: `$PG/metrics/etcd/etcd_firing_alerts.json`

**Pod の状態と再起動**

- `omc get pods -A -o wide` の RESTARTS 列（Default を use）
- `$PG/workload-scoped-resources/commands/pods_wide`
- 再起動理由は `omc describe pod` の Last State、または `previous.log`
- イベント: `$PG/workload-scoped-resources/workload_events/`

**アラート**

- Default: `omc prom rules -s firing` または `$OCP/monitoring/`
- PG: `$PG/metrics/**/` の `*_firing_alerts.json`、`$PG/namespaces/openshift-monitoring/monitoring_config/`
- 二者は別ソース。片方空でも他方を当たる

**オペレータの異常** (CSV, subscription, degraded)

- `omc get co`
- OLM: `namespaces/openshift-operator-lifecycle-manager/` と各 ns の `operators.coreos.com/`
- CSV の status.message にインストール失敗の理由が書かれていることが多い

**仮想化**

- namespace は `$OCP/namespaces/openshift-cnv` と `$PG/namespaces/openshift-cnv` の両方
- kubevirt 系メトリクス: `$PG/metrics/prometheus_instant/kubevirt_*.json` と `prometheus_range/`
- CNV 専用 gather が欠けていても、上記があれば「完全に検証不能」とは限らない

**ネットワークとストレージ**

- StorageClass は `storage.k8s.io` ディレクトリがこの Default に無いので検索する
- PV/PVC、CSI ドライバの pod ログ
- NFS: `$PG/nodes/nfs_*.txt`、FailedMount 系は `$PG/.../workload_events/events/critical/`
- kubelet のマウント失敗: `$OCP/host_service_logs/masters/kubelet_service.log`（大きいので絞る）
  および `$OCP/nodes/<node>/<node>_logs_kubelet.gz`

**ノード OS レベルの事象** (kubelet 再起動、DiskPressure、kernel stall)

- masters まとめ: `$OCP/host_service_logs/masters/kubelet_service.log`, `crio_service.log`
- ノード別: `$OCP/nodes/<node>/dmesg`, `*_logs_kubelet.gz`
- ノードの `status.conditions`

## 調査時の実務的な注意

- **ログは必ず絞ってから読む**。`grep -c` で件数、`grep -m 5` で先頭数件、それから前後。
  `host_service_logs/masters/kubelet_service.log` は数十 MB ある。
- **時刻を揃える**。must-gather 内のログは UTC。レポートの Data collected も UTC。
- **パスは引用符で囲む**。plugin ディレクトリ名に sha256 が含まれる。
- **見つからなかったときは、探した場所を明示する**。
  「`$OCP/namespaces/openshift-cnv/` も `$PG/namespaces/openshift-cnv/` も無い」のように書く。
- **レポートの数値をそのまま検索語にしない**。レポートの件数は集計値であってログ中の文字列ではない。
  カウントは自分で取り直す。
- **PG の JSON** は Prom の instant/range 形式。jq で `data.result[].metric` と `value` を抜く。
  大きなファイルをプロンプトに丸投げしない。
