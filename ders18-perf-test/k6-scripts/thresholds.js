// thresholds.js — LAB 1: SLO threshold'lu test.
//
// Aynı load profili, ama bu kez SLO'ları k6 threshold'u olarak tanımlıyoruz.
// Threshold ihlal edilirse k6 exit code 99 döner (CI/CD'de "fail").
//
// SLO'lar:
//   - p99 latency < 500ms
//   - error rate  < %1
//   - p95 latency < 300ms (uyarı seviyesi, abortOnFail YOK)
//
// Çalıştır:
//   k6 run k6-scripts/thresholds.js
//   echo $?   # 0 = pass, 99 = en az bir threshold fail
//
// DENEY: order-svc'nin DB latency'sini artırıp tekrar çalıştır →
//   kubectl set env deploy/order-svc SIMULATED_DB_LATENCY_MS=200
//   k6 run k6-scripts/thresholds.js   # artık p99 < 500ms FAIL eder
import { userFlow } from "./common.js";

export const options = {
  stages: [
    { duration: "30s", target: 100 },
    { duration: "2m", target: 100 },
    { duration: "30s", target: 0 },
  ],
  thresholds: {
    // p99 < 500ms — ana SLO. İhlal edilirse test fail.
    "http_req_duration": ["p(99)<500", "p(95)<300"],
    // Hata oranı < %1. payment-svc zaten %5 random 500 ürettiği için
    // POST_RATIO yüksekse bu kasıtlı olarak zorlanır → SLO tasarımını tartış.
    "http_req_failed": ["rate<0.01"],
    // Belirli endpoint'e özel SLO (tag ile). GET /orders daha sıkı.
    "http_req_duration{endpoint:GET /orders}": ["p(99)<300"],
  },
  summaryTrendStats: ["avg", "min", "med", "p(90)", "p(95)", "p(99)", "max"],
};

export default function () {
  userFlow();
}
