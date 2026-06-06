#!/usr/bin/env bash
# Ders 18 Performans Testi Lab — kind cluster + monitoring + metrics-server.
#
# Bu script YALNIZCA ALTYAPI kurar:
#   1) kind cluster (ders18-perf, NodePort port mapping'leri ile)
#   2) metrics-server (kind TLS patch'i ile) → kubectl top + HPA için ŞART
#   3) kube-prometheus-stack (Helm) → Prometheus + Grafana + AlertManager
#
# ÖĞRETİLEN komutlar (docker build, kind load, kubectl apply, kubectl set env,
# k6 run, kubectl autoscale...) bu scriptte YOK — onlar README.md "Kurulum"
# bölümünde ve lab README'lerinde MANUEL çalıştırılır.
#
# k6 host'ta çalışan bir binary'dir (cluster'da değil). Kurulu değilse script
# uyarır ama durmaz — kurulum komutu aşağıda.
set -euo pipefail

CLUSTER_NAME="ders18-perf"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PROM_STACK_VERSION="65.1.1"  # kube-prometheus-stack chart sürümü (sabit → tekrarlanabilir)

# ---- 1. Prerequisite check ----
for cmd in kind kubectl docker helm; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "❌ Eksik: $cmd kurulu değil"
    exit 1
  fi
done
echo "✅ Prerequisite OK (kind, kubectl, docker, helm)"

# k6 zorunlu değil (host tool) ama yoksa workshop yapılamaz → uyar.
if ! command -v k6 >/dev/null 2>&1; then
  echo "⚠️  k6 kurulu değil. Workshop'tan önce kur:"
  echo "      macOS:  brew install k6"
  echo "      Linux:  https://grafana.com/docs/k6/latest/set-up/install-k6/"
  echo "      Docker: k6'yı 'docker run --rm -i grafana/k6 run - <script' ile de çalıştırabilirsin"
else
  echo "✅ k6 bulundu: $(k6 version | head -1)"
fi

# ---- 2. Cluster oluştur ----
if kind get clusters 2>/dev/null | grep -qx "${CLUSTER_NAME}"; then
  echo "ℹ️  Cluster '${CLUSTER_NAME}' zaten var — yeniden oluşturma atlanıyor"
  echo "   Sıfırdan: kind delete cluster --name ${CLUSTER_NAME}"
else
  echo "🚧 kind cluster oluşturuluyor: ${CLUSTER_NAME}"
  kind create cluster --config "${SCRIPT_DIR}/cluster.yaml"
fi

kubectl config use-context "kind-${CLUSTER_NAME}"

# ---- 3. metrics-server (kubectl top + HPA için ŞART) ----
echo "🚧 metrics-server kuruluyor"
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

# kind'da kubelet sertifikası self-signed → metrics-server TLS doğrulamasını atla.
echo "🔧 metrics-server kind TLS patch'i uygulanıyor (--kubelet-insecure-tls)"
kubectl -n kube-system patch deploy metrics-server --type=json \
  -p='[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'
kubectl -n kube-system rollout status deploy/metrics-server --timeout=120s

# ---- 4. kube-prometheus-stack (Helm) ----
echo "🚧 kube-prometheus-stack kuruluyor (chart ${PROM_STACK_VERSION})"
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts >/dev/null 2>&1 || true
helm repo update >/dev/null

helm upgrade --install monitoring prometheus-community/kube-prometheus-stack \
  --version "${PROM_STACK_VERSION}" \
  --namespace monitoring --create-namespace \
  --values "${SCRIPT_DIR}/../infra/kube-prometheus-values.yaml" \
  --wait --timeout 10m

echo "⏳ Grafana ve Prometheus Ready bekleniyor..."
kubectl -n monitoring rollout status deploy/monitoring-grafana --timeout=180s
kubectl -n monitoring rollout status statefulset/prometheus-monitoring-prometheus --timeout=180s 2>/dev/null || true

# ---- 5. Smoke test ----
echo "🧪 metrics-server smoke: kubectl top nodes"
sleep 10  # metrics-server'ın ilk metrikleri toplaması için
kubectl top nodes 2>/dev/null || echo "   (metrics-server henüz ısınıyor — 30sn sonra tekrar dene)"

cat <<EOF

╔══════════════════════════════════════════════════════════════════╗
║  ✅ Altyapı hazır: ${CLUSTER_NAME}
╠══════════════════════════════════════════════════════════════════╣
║  Cluster context: kind-${CLUSTER_NAME}
║  Grafana:    http://localhost:30300   (admin / workshop)
║  Prometheus: http://localhost:30900
║  order-svc:  http://localhost:8001    (deploy edilince — k6 hedefi)
║
║  SIRADAKİ ADIM: README.md → "Kurulum"
║    1) docker build → order-svc + payment-svc
║    2) kind load docker-image ...
║    3) kubectl apply -f manifests/
║    4) k6 run ile Lab 1'e başla
╚══════════════════════════════════════════════════════════════════╝

EOF
