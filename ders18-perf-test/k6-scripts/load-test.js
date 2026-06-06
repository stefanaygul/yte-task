// load-test.js — LAB 1: Temel load test + baseline ölçümü.
//
// Amaç: Sistemin NORMAL yük altındaki davranışını ölçmek. Burada threshold YOK;
// sadece "baseline" rakamlarını (avg / p95 / p99 latency, RPS, error rate)
// okuyup not alıyoruz. SLO eşiğini thresholds.js'te ekleyeceğiz.
//
// Profil: ramp-up (30s) → steady 100 VU (2 dk) → ramp-down (30s).
//
// Çalıştır:
//   k6 run k6-scripts/load-test.js
//   k6 run -e BASE_URL=http://localhost:8001 k6-scripts/load-test.js
import { userFlow } from "./common.js";

export const options = {
  stages: [
    { duration: "30s", target: 100 }, // kademeli ramp-up (ani şok yok)
    { duration: "2m", target: 100 }, // steady state — baseline burada okunur
    { duration: "30s", target: 0 }, // ramp-down
  ],
  // Özette p95 ve p99'u açıkça göster.
  summaryTrendStats: ["avg", "min", "med", "p(90)", "p(95)", "p(99)", "max"],
};

export default function () {
  userFlow();
}
