// soak-test.js — LAB 3: Soak (dayanıklılık) testi + memory leak avı.
//
// Amaç: Sabit, ılımlı yükü UZUN süre uygulayıp zamanla bozulan şeyleri yakalamak:
// memory leak, file descriptor sızıntısı, connection pool tükenmesi, disk dolması.
// Bunlar load/stress test'in kısa süresinde görünmez — sadece zamanla ortaya çıkar.
//
// Burada hedef: order-svc'de MEMORY_LEAK=true iken her request 100KB tutulur ve
// bırakılmaz → RSS sürekli tırmanır → 256Mi limit'e çarpınca OOMKill.
//
// Profil: 100 VU, sabit, 5 dk (workshop ölçeği; prod'da saatler/günler).
// THINK=1 → her VU saniyede ~1 istek (gerçekçi kullanıcı temposu).
//
// Çalıştır — ÖNCE leak'i aç:
//   kubectl set env deploy/order-svc MEMORY_LEAK=true
//   kubectl rollout status deploy/order-svc
//   T1: k6 run -e THINK=1 k6-scripts/soak-test.js
//   T2: watch -n5 kubectl top pods           # memory tırmanışını izle
//   T2: kubectl get pods -w                   # RESTARTS artışı = OOMKill
//
// KARŞILAŞTIR — leak'i kapat, tekrar çalıştır (memory düz kalır):
//   kubectl set env deploy/order-svc MEMORY_LEAK=false
import { userFlow } from "./common.js";

export const options = {
  scenarios: {
    soak: {
      executor: "constant-vus",
      vus: 100,
      duration: __ENV.DURATION || "5m", // workshop için kısa; prod'da saatler
    },
  },
  thresholds: {
    // Leak OOM'a yol açıp pod restart olursa hatalar buradan görünür.
    "http_req_failed": ["rate<0.05"],
  },
  summaryTrendStats: ["avg", "med", "p(95)", "p(99)", "max"],
};

export default function () {
  userFlow();
}
