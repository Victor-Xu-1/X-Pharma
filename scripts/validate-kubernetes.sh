#!/usr/bin/env bash
set -euo pipefail

umask 077

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
versions_path="$root/deploy/kubernetes/platform/versions.env"
cluster_name=""
keep_cluster=0
uv_path="uv"
output_path=""
asset_mirror_prefix=""
asset_cache="${XDG_CACHE_HOME:-$HOME/.cache}/pharma-intelligence/kubernetes-assets"
started_epoch=$(date +%s)
clamav_tag_created=0
clamav_tag=""

usage() {
  cat <<'EOF'
Usage: validate-kubernetes.sh [options]

Validate production Kubernetes resources and ClamAV failover in a disposable kind cluster.

Options:
  --cluster-name NAME  Use a specific, currently nonexistent kind cluster name.
  --keep-cluster       Keep the cluster and validation workspace after success.
  --uv-path PATH       uv executable to use (default: uv).
  --asset-mirror-prefix PREFIX  Prefix immutable upstream URLs with an HTTPS transport mirror.
  --asset-cache DIR    SHA-256 verified content cache for immutable validation assets.
  --output FILE        Write an atomic machine-readable validation report.
  -h, --help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --cluster-name)
      [[ $# -ge 2 ]] || { echo "--cluster-name requires a value" >&2; exit 2; }
      cluster_name=$2
      shift 2
      ;;
    --keep-cluster)
      keep_cluster=1
      shift
      ;;
    --uv-path)
      [[ $# -ge 2 ]] || { echo "--uv-path requires a value" >&2; exit 2; }
      uv_path=$2
      shift 2
      ;;
    --asset-mirror-prefix)
      [[ $# -ge 2 ]] || { echo "--asset-mirror-prefix requires a value" >&2; exit 2; }
      asset_mirror_prefix=$2
      shift 2
      ;;
    --asset-cache)
      [[ $# -ge 2 ]] || { echo "--asset-cache requires a value" >&2; exit 2; }
      asset_cache=$2
      shift 2
      ;;
    --output)
      [[ $# -ge 2 ]] || { echo "--output requires a value" >&2; exit 2; }
      output_path=$2
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "$cluster_name" ]]; then
  cluster_name="pharma-schema-$(date -u +%Y%m%d%H%M%S)-$$"
fi
[[ "$cluster_name" =~ ^[a-z0-9]([-a-z0-9]*[a-z0-9])?$ && ${#cluster_name} -le 63 ]] || {
  echo "invalid kind cluster name: $cluster_name" >&2
  exit 2
}

if [[ -n "$asset_mirror_prefix" ]]; then
  case "$asset_mirror_prefix" in
    https://*/) ;;
    *)
      echo "asset mirror prefix must be an HTTPS URL ending in /" >&2
      exit 2
      ;;
  esac
  if [[ "$asset_mirror_prefix" =~ [[:space:]] ]]; then
    echo "asset mirror prefix cannot contain whitespace" >&2
    exit 2
  fi
fi

download_url() {
  local original=$1
  printf '%s%s' "$asset_mirror_prefix" "$original"
}

for command in docker kubectl curl sha256sum python3 mktemp awk grep timeout realpath dirname basename cp mv flock; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "required command is unavailable: $command" >&2
    exit 1
  }
done
command -v "$uv_path" >/dev/null 2>&1 || {
  echo "uv executable is unavailable: $uv_path" >&2
  exit 1
}
"$uv_path" run --project "$root" python "$root/scripts/validate_yaml.py" "$root/deploy/kubernetes"
proxy_contract=$(sed -n 's/^  MCP_TRUSTED_PROXY_CIDRS: //p' "$root/deploy/kubernetes/base/config-map.yaml")
if [[ "$proxy_contract" != "REPLACE_WITH_EXACT_TRUSTED_PROXY_CIDRS" ]]; then
  echo "Kubernetes base must retain the fail-closed trusted-proxy sentinel for target overlays" >&2
  exit 1
fi
docker version --format '{{.Server.Version}}' >/dev/null

mkdir -p "$asset_cache"
asset_cache=$(realpath "$asset_cache")
[[ "$asset_cache" != "/" ]] || {
  echo "asset cache cannot be the filesystem root" >&2
  exit 2
}
chmod 700 "$asset_cache"
exec 8>"$asset_cache/.cache.lock"
flock 8

declare -A versions=()
while IFS= read -r raw_line || [[ -n "$raw_line" ]]; do
  line=${raw_line%%#*}
  [[ -n "$line" ]] || continue
  if [[ ! "$line" =~ ^([A-Z][A-Z0-9_]*)=([A-Za-z0-9._/@:-]+)$ ]]; then
    echo "invalid platform version declaration: $raw_line" >&2
    exit 1
  fi
  versions["${BASH_REMATCH[1]}"]="${BASH_REMATCH[2]}"
done < "$versions_path"
for required in KIND_VERSION KIND_LINUX_AMD64_SHA256 KUBERNETES_VALIDATION_VERSION KIND_NODE_IMAGE ENVOY_GATEWAY_VERSION ENVOY_GATEWAY_INSTALL_SHA256 EXTERNAL_SECRETS_VERSION EXTERNAL_SECRETS_CRDS_SHA256 OTEL_OPERATOR_VERSION OTEL_OPERATOR_MANIFEST_SHA256; do
  [[ -n "${versions[$required]:-}" ]] || {
    echo "missing $required in $versions_path" >&2
    exit 1
  }
done
node_image=${versions[KIND_NODE_IMAGE]}
[[ "${node_image%@sha256:*}" == "kindest/node:v${versions[KUBERNETES_VALIDATION_VERSION]}" && "$node_image" =~ @sha256:[0-9a-f]{64}$ ]] || {
  echo "KIND_NODE_IMAGE must pin the validation Kubernetes version by digest" >&2
  exit 1
}

work=$(mktemp -d -t pharma-kubernetes.XXXXXX)
kind_path="$work/kind"
kubeconfig="$work/kubeconfig"
kind_config="$work/kind-config.yaml"
created=0
cleanup() {
  status=$?
  trap - EXIT INT TERM
  if [[ $created -eq 1 && $keep_cluster -ne 1 ]]; then
    KIND_EXPERIMENTAL_PROVIDER=docker timeout --foreground --signal=TERM --kill-after=10s 60s "$kind_path" delete cluster --name "$cluster_name" >/dev/null 2>&1 || true
  fi
  if [[ $clamav_tag_created -eq 1 && -n "$clamav_tag" ]]; then
    docker image rm --force "$clamav_tag" >/dev/null 2>&1 || true
  fi
  if [[ $keep_cluster -eq 1 && $created -eq 1 ]]; then
    printf 'retained_cluster=%s\n' "$cluster_name"
    printf 'retained_kubeconfig=%s\n' "$kubeconfig"
    printf 'retained_workspace=%s\n' "$work"
    printf 'retained_after_exit_status=%s\n' "$status"
  else
    case "$work" in
      /tmp/pharma-kubernetes.*) rm -rf -- "$work" ;;
      *) echo "refusing to remove unexpected validation workspace: $work" >&2 ;;
    esac
  fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

curl_args=(--fail --silent --show-error --location --connect-timeout 15 --max-time 180 --retry 3 --retry-all-errors --retry-max-time 720)
cache_hits=0
cache_misses=0

verify_asset() {
  local path=$1
  local expected=$2
  local label=$3
  local actual
  [[ "$expected" =~ ^[0-9a-f]{64}$ ]] || {
    echo "invalid pinned checksum for $label" >&2
    return 1
  }
  [[ -f "$path" && ! -L "$path" ]] || {
    echo "$label is not a regular cached asset" >&2
    return 1
  }
  actual=$(sha256sum "$path" | awk '{print $1}')
  [[ "$actual" == "$expected" ]] || {
    echo "$label failed pinned SHA-256 verification" >&2
    return 1
  }
}

materialize_cached_asset() {
  local expected=$1
  local destination=$2
  local label=$3
  local cached="$asset_cache/sha256-$expected"
  if [[ ! -e "$cached" && ! -L "$cached" ]]; then
    return 1
  fi
  if ! verify_asset "$cached" "$expected" "$label cache entry"; then
    case "$cached" in
      "$asset_cache"/sha256-*) rm -f -- "$cached" ;;
      *) echo "refusing to remove unexpected cache path: $cached" >&2; return 1 ;;
    esac
    return 1
  fi
  cp -- "$cached" "$destination"
  cache_hits=$((cache_hits + 1))
}

download_asset() {
  local url=$1
  local expected=$2
  local destination=$3
  local label=$4
  local cached="$asset_cache/sha256-$expected"
  local staging
  if materialize_cached_asset "$expected" "$destination" "$label"; then
    return 0
  fi
  staging=$(mktemp "$asset_cache/.download.XXXXXX")
  if ! curl "${curl_args[@]}" --continue-at - "$url" --output "$staging"; then
    rm -f -- "$staging"
    return 1
  fi
  if ! verify_asset "$staging" "$expected" "$label download"; then
    rm -f -- "$staging"
    return 1
  fi
  chmod 600 "$staging"
  mv -- "$staging" "$cached"
  cp -- "$cached" "$destination"
  cache_misses=$((cache_misses + 1))
}

printf '[kubernetes] resolving kind v%s\n' "${versions[KIND_VERSION]}"

kind_version=${versions[KIND_VERSION]}
kind_origin="https://github.com/kubernetes-sigs/kind/releases/download/v$kind_version/kind-linux-amd64"
kind_url=$(download_url "$kind_origin")
expected_hash=${versions[KIND_LINUX_AMD64_SHA256]}
if ! materialize_cached_asset "$expected_hash" "$kind_path" "kind binary"; then
  curl "${curl_args[@]}" "$(download_url "$kind_origin.sha256sum")" --output "$kind_path.sha256sum"
  read -r published_hash _ < "$kind_path.sha256sum"
  [[ "$published_hash" =~ ^[0-9a-fA-F]{64}$ ]] || {
    echo "kind checksum response is invalid" >&2
    exit 1
  }
  [[ "${published_hash,,}" == "$expected_hash" ]] || {
    echo "published kind checksum differs from the pinned contract" >&2
    exit 1
  }
  download_asset "$kind_url" "$expected_hash" "$kind_path" "kind binary"
fi
chmod 700 "$kind_path"

if timeout --foreground --signal=TERM --kill-after=5s 30s "$kind_path" get clusters | grep -Fxq "$cluster_name"; then
  echo "refusing to modify an existing kind cluster: $cluster_name" >&2
  exit 1
fi

printf '[kubernetes] resolving pinned platform CRDs\n'
envoy_url=$(download_url "https://github.com/envoyproxy/gateway/releases/download/v${versions[ENVOY_GATEWAY_VERSION]}/install.yaml")
external_secrets_url=$(download_url "https://raw.githubusercontent.com/external-secrets/external-secrets/v${versions[EXTERNAL_SECRETS_VERSION]}/deploy/crds/bundle.yaml")
otel_url=$(download_url "https://github.com/open-telemetry/opentelemetry-operator/releases/download/v${versions[OTEL_OPERATOR_VERSION]}/opentelemetry-operator.yaml")
download_asset "$envoy_url" "${versions[ENVOY_GATEWAY_INSTALL_SHA256]}" "$work/envoy-gateway.yaml" "Envoy Gateway manifest"
download_asset "$external_secrets_url" "${versions[EXTERNAL_SECRETS_CRDS_SHA256]}" "$work/external-secrets-crds.yaml" "External Secrets CRDs"
download_asset "$otel_url" "${versions[OTEL_OPERATOR_MANIFEST_SHA256]}" "$work/otel-operator.yaml" "OpenTelemetry Operator manifest"
flock -u 8

"$uv_path" run python - "$work" "$root" <<'PY'
from pathlib import Path
import sys

import yaml

root = Path(sys.argv[1])
repository = Path(sys.argv[2])
for source, target in (
    ("envoy-gateway.yaml", "envoy-crds.yaml"),
    ("otel-operator.yaml", "otel-crds.yaml"),
):
    documents = [
        item
        for item in yaml.safe_load_all((root / source).read_text(encoding="utf-8"))
        if isinstance(item, dict) and item.get("kind") == "CustomResourceDefinition"
    ]
    if not documents:
        raise SystemExit(f"no CRDs found in {source}")
    rendered = "---\n".join(yaml.safe_dump(item, sort_keys=False) for item in documents)
    (root / target).write_text(rendered, encoding="utf-8")

for source, target, kind, name in (
    ("disruption-budgets.yaml", "clamav-pdb.yaml", "PodDisruptionBudget", "pharma-clamav"),
    ("autoscaling.yaml", "clamav-hpa.yaml", "HorizontalPodAutoscaler", "pharma-clamav"),
):
    documents = [
        item
        for item in yaml.safe_load_all(
            (repository / "deploy" / "kubernetes" / "base" / source).read_text(encoding="utf-8")
        )
        if isinstance(item, dict) and item.get("kind") == kind and item.get("metadata", {}).get("name") == name
    ]
    if len(documents) != 1:
        raise SystemExit(f"expected one {kind}/{name} in {source}")
    (root / target).write_text(yaml.safe_dump(documents[0], sort_keys=False), encoding="utf-8")
PY

python3 - "$kind_config" <<'PY'
from pathlib import Path
import sys

import yaml

document = {
    "apiVersion": "kind.x-k8s.io/v1alpha4",
    "kind": "Cluster",
    "nodes": [
        {"role": "control-plane"},
        {"role": "worker"},
        {"role": "worker"},
    ],
}
Path(sys.argv[1]).write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
PY

printf '[kubernetes] creating disposable kind cluster %s\n' "$cluster_name"
KIND_EXPERIMENTAL_PROVIDER=docker timeout --foreground --signal=TERM --kill-after=15s 300s \
  "$kind_path" create cluster \
  --name "$cluster_name" \
  --config "$kind_config" \
  --image "$node_image" \
  --kubeconfig "$kubeconfig" \
  --wait 180s
created=1
export KUBECONFIG="$kubeconfig"

node_inventory=$(kubectl get nodes -o json | python3 -c '
import json, sys
items = json.load(sys.stdin)["items"]
control = []
workers = []
for item in items:
    name = item["metadata"]["name"]
    labels = item["metadata"].get("labels", {})
    if "node-role.kubernetes.io/control-plane" in labels:
        control.append(name)
    else:
        workers.append(name)
print("{}|{}".format(len(control), ",".join(sorted(workers))))
')
kind_control_plane_count=${node_inventory%%|*}
kind_worker_csv=${node_inventory#*|}
IFS=',' read -r -a kind_worker_nodes <<< "$kind_worker_csv"
kind_worker_count=${#kind_worker_nodes[@]}
[[ "$kind_control_plane_count" == "1" && "$kind_worker_count" == "2" ]] || {
  echo "kind validation requires exactly one control-plane and two worker nodes" >&2
  exit 1
}
kubectl label node "${kind_worker_nodes[0]}" topology.kubernetes.io/zone=kind-zone-a --overwrite >/dev/null
kubectl label node "${kind_worker_nodes[1]}" topology.kubernetes.io/zone=kind-zone-b --overwrite >/dev/null

server_version=$(kubectl version -o json | python3 -c 'import json,sys; print(json.load(sys.stdin)["serverVersion"]["gitVersion"])')
case "$server_version" in
  "v${versions[KUBERNETES_VALIDATION_VERSION]}"*) ;;
  *)
    echo "unexpected Kubernetes API server version: $server_version" >&2
    exit 1
    ;;
esac

printf '[kubernetes] validating production resources with server-side dry-run\n'
kubectl apply --server-side --force-conflicts -f "$work/envoy-crds.yaml" >/dev/null
kubectl apply --server-side --force-conflicts -f "$work/external-secrets-crds.yaml" >/dev/null
kubectl apply --server-side --force-conflicts -f "$work/otel-crds.yaml" >/dev/null
kubectl wait --for=condition=Established --all customresourcedefinition --timeout=120s >/dev/null
kubectl apply -f "$root/deploy/kubernetes/base/namespace.yaml" >/dev/null
kubectl apply --server-side --dry-run=server \
  -f "$root/deploy/kubernetes/platform/envoy-gateway-class.yaml" >/dev/null
kubectl kustomize "$root/deploy/kubernetes/base" \
  | kubectl apply --server-side --dry-run=server -f - >/dev/null

printf '[kubernetes] validating live ClamAV persistence and single-pod failover\n'
clamav_image=$("$uv_path" run python - "$root/deploy/kubernetes/base/clamav.yaml" <<'PY'
from pathlib import Path
import re
import sys

import yaml

documents = list(yaml.safe_load_all(Path(sys.argv[1]).read_text(encoding="utf-8")))
workloads = [item for item in documents if isinstance(item, dict) and item.get("kind") == "StatefulSet"]
if len(workloads) != 1:
    raise SystemExit("expected exactly one ClamAV StatefulSet")
image = workloads[0]["spec"]["template"]["spec"]["containers"][0]["image"]
if re.fullmatch(r"clamav/clamav:1\.4@sha256:[0-9a-f]{64}", image) is None:
    raise SystemExit("ClamAV image is not pinned by the approved digest contract")
print(image)
PY
)
if ! docker image inspect "$clamav_image" >/dev/null 2>&1; then
  timeout --foreground --signal=TERM --kill-after=15s 600s docker pull "$clamav_image" >/dev/null
fi
clamav_tag=${clamav_image%@sha256:*}
if ! docker image inspect "$clamav_tag" >/dev/null 2>&1; then
  docker tag "$clamav_image" "$clamav_tag"
  clamav_tag_created=1
fi
KIND_EXPERIMENTAL_PROVIDER=docker timeout --foreground --signal=TERM --kill-after=30s 300s \
  "$kind_path" load docker-image --name "$cluster_name" "$clamav_tag" >/dev/null
"$uv_path" run python - \
  "$root/deploy/kubernetes/base/clamav.yaml" "$work/clamav-live.yaml" "$clamav_tag" <<'PY'
from pathlib import Path
import sys

import yaml

source = Path(sys.argv[1])
destination = Path(sys.argv[2])
local_image = sys.argv[3]
documents = list(yaml.safe_load_all(source.read_text(encoding="utf-8")))
workloads = [item for item in documents if isinstance(item, dict) and item.get("kind") == "StatefulSet"]
if len(workloads) != 1:
    raise SystemExit("expected exactly one ClamAV StatefulSet")
pod_spec = workloads[0]["spec"]["template"]["spec"]
for container in [*pod_spec.get("initContainers", []), *pod_spec["containers"]]:
    container["image"] = local_image
    container["imagePullPolicy"] = "Never"
payload = "---\n".join(yaml.safe_dump(item, sort_keys=False) for item in documents if item is not None)
destination.write_text(payload, encoding="utf-8")
PY

kubectl get storageclass standard -o json > "$work/standard-storage-class.json"
python3 - "$work/standard-storage-class.json" "$work/clamav-storage-class.json" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

source = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
document = {
    "apiVersion": "storage.k8s.io/v1",
    "kind": "StorageClass",
    "metadata": {"name": "replace-with-rwo-storage-class"},
    "provisioner": source["provisioner"],
    "reclaimPolicy": source.get("reclaimPolicy", "Delete"),
    "volumeBindingMode": source.get("volumeBindingMode", "WaitForFirstConsumer"),
    "allowVolumeExpansion": source.get("allowVolumeExpansion", False),
    "parameters": source.get("parameters", {}),
}
Path(sys.argv[2]).write_text(json.dumps(document, sort_keys=True) + "\n", encoding="utf-8")
PY
kubectl apply -f "$work/clamav-storage-class.json" >/dev/null
kubectl -n pharma-intelligence apply -f "$work/clamav-live.yaml" >/dev/null
kubectl -n pharma-intelligence apply -f "$work/clamav-pdb.yaml" >/dev/null
kubectl -n pharma-intelligence apply -f "$work/clamav-hpa.yaml" >/dev/null
kubectl -n pharma-intelligence rollout status statefulset/pharma-clamav --timeout=15m >/dev/null

clamav_ready_before=$(kubectl -n pharma-intelligence get statefulset pharma-clamav -o jsonpath='{.status.readyReplicas}')
[[ "$clamav_ready_before" == "2" ]] || {
  echo "ClamAV StatefulSet did not reach two ready replicas" >&2
  exit 1
}
clamav_pvc_before=$(kubectl -n pharma-intelligence get pvc -l app.kubernetes.io/name=pharma-clamav -o json | python3 -c '
import json, sys
items = json.load(sys.stdin)["items"]
if len(items) != 2:
    raise SystemExit("expected two ClamAV PVCs")
print(",".join("{}:{}".format(item["metadata"]["name"], item["metadata"]["uid"]) for item in sorted(items, key=lambda item: item["metadata"]["name"])))
')
for pod in pharma-clamav-0 pharma-clamav-1; do
  kubectl -n pharma-intelligence exec "$pod" -- clamdscan \
    --config-file=/etc/clamav/clamd.conf --ping=1 >/dev/null
  kubectl -n pharma-intelligence exec "$pod" -- /bin/sh -ec \
    "find /var/lib/clamav -maxdepth 1 -type f \\( -name '*.cvd' -o -name '*.cld' \\) -mmin -2160 -print -quit | grep -q ."
done
kubectl -n pharma-intelligence exec pharma-clamav-0 -- /bin/sh -ec \
  'printf "%s" "pharma-clamav-persistence-v1" > /var/lib/clamav/.ha-marker'

clean_result=$(kubectl -n pharma-intelligence exec pharma-clamav-1 -- /bin/sh -ec \
  'printf "%s" "governed-clean-sample" > /tmp/clean.txt; clamdscan --config-file=/etc/clamav/clamd.conf /tmp/clean.txt')
grep -Fq 'Infected files: 0' <<<"$clean_result" || {
  echo "ClamAV clean sample validation failed" >&2
  exit 1
}
set +e
eicar_result=$(kubectl -n pharma-intelligence exec pharma-clamav-1 -- /bin/sh -ec \
  'printf "%s" "X5O!P%@AP[4\\PZX54(P^)7CC)7}\$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!\$H+H*" > /tmp/eicar.com; clamdscan --config-file=/etc/clamav/clamd.conf /tmp/eicar.com' 2>&1)
eicar_status=$?
set -e
[[ $eicar_status -eq 1 ]] && grep -Fq 'FOUND' <<<"$eicar_result" || {
  echo "ClamAV EICAR validation failed" >&2
  exit 1
}

ready_endpoint_count() {
  kubectl -n pharma-intelligence get endpointslice \
    -l kubernetes.io/service-name=pharma-clamav -o json | python3 -c '
import json, sys
count = 0
for item in json.load(sys.stdin)["items"]:
    for endpoint in item.get("endpoints", []):
        if endpoint.get("conditions", {}).get("ready") is True:
            count += len(endpoint.get("addresses", []))
print(count)
'
}

clamav_endpoints_before=$(ready_endpoint_count)
[[ "$clamav_endpoints_before" == "2" ]] || {
  echo "ClamAV Service did not expose two ready endpoints" >&2
  exit 1
}
clamav_placement() {
  python3 - \
    <(kubectl -n pharma-intelligence get pod -l app.kubernetes.io/name=pharma-clamav -o json) \
    <(kubectl get node -o json) <<'PY'
import json
import sys
from pathlib import Path

pods = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))["items"]
nodes = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))["items"]
if len(pods) != 2:
    raise SystemExit("expected exactly two ClamAV pods for placement validation")
zone_by_node = {
    item["metadata"]["name"]: item["metadata"].get("labels", {}).get("topology.kubernetes.io/zone", "")
    for item in nodes
}
pod_nodes = sorted({item["spec"].get("nodeName", "") for item in pods})
if "" in pod_nodes:
    raise SystemExit("ClamAV pod placement is incomplete")
pod_zones = sorted({zone_by_node.get(node, "") for node in pod_nodes})
if "" in pod_zones:
    raise SystemExit("ClamAV pod is not assigned to a declared validation zone")
print(f"{','.join(pod_nodes)}|{','.join(pod_zones)}|{len(pod_nodes)}|{len(pod_zones)}")
PY
}
IFS='|' read -r clamav_nodes_before clamav_zones_before clamav_distinct_nodes_before clamav_distinct_zones_before \
  <<< "$(clamav_placement)"
[[ "$clamav_distinct_nodes_before" == "2" && "$clamav_distinct_zones_before" == "2" ]] || {
  echo "ClamAV replicas were not distributed across two workers and two zones" >&2
  exit 1
}
clamav_old_pod_uid=$(kubectl -n pharma-intelligence get pod pharma-clamav-0 -o jsonpath='{.metadata.uid}')
kubectl -n pharma-intelligence delete pod pharma-clamav-0 --wait=false >/dev/null
clamav_minimum_ready_endpoints=2
clamav_replacement_uid=""
clamav_deadline=$(( $(date +%s) + 900 ))
while (( $(date +%s) < clamav_deadline )); do
  current_endpoints=$(ready_endpoint_count)
  if (( current_endpoints < clamav_minimum_ready_endpoints )); then
    clamav_minimum_ready_endpoints=$current_endpoints
  fi
  (( clamav_minimum_ready_endpoints >= 1 )) || {
    echo "ClamAV Service lost every ready endpoint during pod replacement" >&2
    exit 1
  }
  clamav_replacement_uid=$(kubectl -n pharma-intelligence get pod pharma-clamav-0 -o jsonpath='{.metadata.uid}' 2>/dev/null || true)
  clamav_replacement_ready=$(kubectl -n pharma-intelligence get pod pharma-clamav-0 -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || true)
  if [[ -n "$clamav_replacement_uid" && "$clamav_replacement_uid" != "$clamav_old_pod_uid" && "$clamav_replacement_ready" == "True" ]]; then
    break
  fi
  sleep 2
done
[[ -n "$clamav_replacement_uid" && "$clamav_replacement_uid" != "$clamav_old_pod_uid" && "${clamav_replacement_ready:-}" == "True" ]] || {
  echo "ClamAV replacement pod did not become ready" >&2
  exit 1
}
clamav_pvc_after=$(kubectl -n pharma-intelligence get pvc -l app.kubernetes.io/name=pharma-clamav -o json | python3 -c '
import json, sys
items = json.load(sys.stdin)["items"]
print(",".join("{}:{}".format(item["metadata"]["name"], item["metadata"]["uid"]) for item in sorted(items, key=lambda item: item["metadata"]["name"])))
')
[[ "$clamav_pvc_after" == "$clamav_pvc_before" ]] || {
  echo "ClamAV PVC identity changed during pod replacement" >&2
  exit 1
}
marker=$(kubectl -n pharma-intelligence exec pharma-clamav-0 -- cat /var/lib/clamav/.ha-marker)
[[ "$marker" == "pharma-clamav-persistence-v1" ]] || {
  echo "ClamAV persistent signature volume marker was lost" >&2
  exit 1
}
kubectl -n pharma-intelligence exec pharma-clamav-0 -- rm -f /var/lib/clamav/.ha-marker
clamav_ready_after=$(kubectl -n pharma-intelligence get statefulset pharma-clamav -o jsonpath='{.status.readyReplicas}')
clamav_endpoints_after=$(ready_endpoint_count)
[[ "$clamav_ready_after" == "2" && "$clamav_endpoints_after" == "2" ]] || {
  echo "ClamAV StatefulSet did not recover full readiness" >&2
  exit 1
}
IFS='|' read -r clamav_nodes_after clamav_zones_after clamav_distinct_nodes_after clamav_distinct_zones_after \
  <<< "$(clamav_placement)"
[[ "$clamav_distinct_nodes_after" == "2" && "$clamav_distinct_zones_after" == "2" ]] || {
  echo "ClamAV replacement did not recover cross-node and cross-zone placement" >&2
  exit 1
}
[[ "$clamav_nodes_after" == "$clamav_nodes_before" && "$clamav_zones_after" == "$clamav_zones_before" ]] || {
  echo "ClamAV placement identity changed after persistent-volume recovery" >&2
  exit 1
}

cluster_cleanup=retained
if [[ $keep_cluster -ne 1 ]]; then
  printf '[kubernetes] deleting disposable kind cluster %s\n' "$cluster_name"
  if ! KIND_EXPERIMENTAL_PROVIDER=docker timeout --foreground --signal=TERM --kill-after=10s 60s \
    "$kind_path" delete cluster --name "$cluster_name" >/dev/null; then
    echo "disposable kind cluster cleanup failed: $cluster_name" >&2
    exit 1
  fi
  created=0
  cluster_cleanup=passed
fi
duration_seconds=$(( $(date +%s) - started_epoch ))
download_transport=sha256-verified-content-cache
if [[ $cache_misses -gt 0 ]]; then
  download_transport=sha256-verified-https+content-cache
  if [[ -n "$asset_mirror_prefix" ]]; then
    download_transport=sha256-verified-https-mirror+content-cache
  fi
fi

if [[ -n "$output_path" ]]; then
  output_parent=$(dirname -- "$output_path")
  output_name=$(basename -- "$output_path")
  [[ "$output_name" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] || {
    echo "invalid output filename: $output_name" >&2
    exit 2
  }
  mkdir -p "$output_parent"
  output_parent=$(realpath "$output_parent")
  output_path="$output_parent/$output_name"
  [[ ! -e "$output_path" ]] || {
    echo "refusing to overwrite Kubernetes evidence: $output_path" >&2
    exit 1
  }
  python3 - \
    "$output_path" "$cluster_name" "$kind_version" "$server_version" "$node_image" \
    "$kind_control_plane_count" "$kind_worker_count" \
    "$duration_seconds" "$cluster_cleanup" \
    "$download_transport" "$cache_hits" "$cache_misses" \
    "$clamav_image" "$clamav_ready_before" "$clamav_ready_after" \
    "$clamav_endpoints_before" "$clamav_endpoints_after" "$clamav_minimum_ready_endpoints" \
    "$clamav_distinct_nodes_before" "$clamav_distinct_nodes_after" \
    "$clamav_distinct_zones_before" "$clamav_distinct_zones_after" \
    "$clamav_pvc_before" \
    "${versions[ENVOY_GATEWAY_VERSION]}" "${versions[ENVOY_GATEWAY_INSTALL_SHA256]}" \
    "${versions[EXTERNAL_SECRETS_VERSION]}" "${versions[EXTERNAL_SECRETS_CRDS_SHA256]}" \
    "${versions[OTEL_OPERATOR_VERSION]}" "${versions[OTEL_OPERATOR_MANIFEST_SHA256]}" <<'PY'
from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

(
    output,
    cluster,
    kind_version,
    server_version,
    node_image,
    control_plane_nodes,
    worker_nodes,
    duration,
    cleanup,
    download_transport,
    cache_hits,
    cache_misses,
    clamav_image,
    clamav_ready_before,
    clamav_ready_after,
    clamav_endpoints_before,
    clamav_endpoints_after,
    clamav_minimum_ready_endpoints,
    clamav_distinct_nodes_before,
    clamav_distinct_nodes_after,
    clamav_distinct_zones_before,
    clamav_distinct_zones_after,
    clamav_pvcs,
    envoy_version,
    envoy_hash,
    external_secrets_version,
    external_secrets_hash,
    otel_version,
    otel_hash,
) = sys.argv[1:]
path = Path(output)
if path.exists():
    raise SystemExit(f"refusing to overwrite Kubernetes evidence: {path}")
document = {
    "schema": "pharma.local-kubernetes-validation.v3",
    "schema_version": 3,
    "generated_at": datetime.now(UTC).isoformat(),
    "status": "passed",
    "environment": "local-isolated-kind",
    "production_claim": False,
    "credentials_recorded": False,
    "controlled_cluster": True,
    "cluster": cluster,
    "kind_version": kind_version,
    "kubernetes_server_version": server_version,
    "kind_node_image": node_image,
    "cluster_topology": {
        "control_plane_nodes": int(control_plane_nodes),
        "worker_nodes": int(worker_nodes),
        "worker_zones": 2,
    },
    "server_side_dry_run": "passed",
    "clamav_ha": {
        "image": clamav_image,
        "live_image_reference": clamav_image.split("@", 1)[0],
        "live_image_pull_policy": "Never",
        "source_image_digest_verified": True,
        "workload": "StatefulSet",
        "replicas_requested": 2,
        "ready_replicas_before": int(clamav_ready_before),
        "ready_replicas_after": int(clamav_ready_after),
        "ready_endpoints_before": int(clamav_endpoints_before),
        "ready_endpoints_after": int(clamav_endpoints_after),
        "minimum_ready_endpoints_during_replacement": int(clamav_minimum_ready_endpoints),
        "distinct_nodes_before": int(clamav_distinct_nodes_before),
        "distinct_nodes_after": int(clamav_distinct_nodes_after),
        "distinct_zones_before": int(clamav_distinct_zones_before),
        "distinct_zones_after": int(clamav_distinct_zones_after),
        "placement_identity_preserved": True,
        "distinct_pvcs": len(clamav_pvcs.split(",")),
        "pvc_identity_preserved": True,
        "persistent_marker_preserved": True,
        "signature_freshness": "passed",
        "clean_scan": "passed",
        "eicar_blocked": True,
        "replacement_pod_uid_changed": True,
    },
    "production_crd_sets": 3,
    "cluster_cleanup": cleanup,
    "duration_seconds": int(duration),
    "download_transport": download_transport,
    "asset_cache": {
        "content_addressed": True,
        "hits": int(cache_hits),
        "misses": int(cache_misses),
    },
    "downloads": {
        "envoy_gateway": {"version": envoy_version, "sha256": envoy_hash},
        "external_secrets": {
            "version": external_secrets_version,
            "sha256": external_secrets_hash,
        },
        "opentelemetry_operator": {"version": otel_version, "sha256": otel_hash},
    },
}
payload = (json.dumps(document, indent=2, sort_keys=True) + "\n").encode()
temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
try:
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.link(temporary, path, follow_symlinks=False)
    except FileExistsError as exc:
        raise SystemExit(f"refusing to overwrite Kubernetes evidence: {path}") from exc
    directory_fd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
finally:
    temporary.unlink(missing_ok=True)
PY
  printf 'validation_report=%s\n' "$output_path"
fi

printf 'validation_status=passed\n'
printf 'kind_version=%s\n' "$kind_version"
printf 'kubernetes_server_version=%s\n' "$server_version"
printf 'kind_node_image=%s\n' "$node_image"
