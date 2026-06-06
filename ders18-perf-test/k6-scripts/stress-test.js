// stress-test.js — LAB 2: Stress test + saturation point bulma.
//
// Amaç: Yükü kademeli artırarak sistemin KIRILMA noktasını (saturation point)
// bulmak. Yük arttıkça latency ve error rate'i izle; p99'un 500ms'i geçtiği
// (ya da error rate'in fırladığı) seviye = saturation point.
//
// Profil: 100 → 300 → 500 → 1000 VU. Her seviyede 1 dk steady (gözlemleyebil).
// THINK=0 → VU'lar maksimum hızda basar (gerçek stress).
//
// Çalıştır (iki terminal):
//   T1: k6 run k6-scripts/stress-test.js
//   T2: watch -n2 kubectl top pods         # CPU/memory tırmanışı
//   T2: kubectl get pods -w                # restart/OOM var mı
//
// DENEY (DB bottleneck kanıtı):
//   kubectl set env deploy/order-svc SIMULATED_DB_LATENCY_MS=100
//   k6 run k6-scripts/stress-test.js   # saturation point DAHA ERKEN gelir
import { userFlow } from "./common.js";

export const options = {
  // Threshold "abortOnFail" ile: p99 1s'i kalıcı aşarsa testi erken durdur
  // (sistemi gereksiz yere ezme). Yorumu kaldırarak deneyebilirsin.
  thresholds: {
    "http_req_duration": [{ threshold: "p(99)<1000", abortOnFail: false }],
  },
  stages: [
    { duration: "30s", target: 100 }, // ısınma
    { duration: "1m", target: 100 }, //  ~baseline
    { duration: "30s", target: 300 },
    { duration: "1m", target: 300 },
    { duration: "30s", target: 500 },
    { duration: "1m", target: 500 },
    { duration: "30s", target: 1000 }, // büyük ihtimalle burada kırılır
    { duration: "1m", target: 1000 },
    { duration: "30s", target: 0 }, // ramp-down
  ],
  summaryTrendStats: ["avg", "med", "p(90)", "p(95)", "p(99)", "max"],
};

export default function () {
  userFlow();
}
