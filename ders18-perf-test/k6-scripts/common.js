// common.js — Tüm k6 script'lerinin paylaştığı yardımcılar.
//
// Tek bir yerde: hedef URL, istek karışımı (GET ağırlıklı + biraz POST),
// ve custom metrikler. Diğer script'ler buradan import eder.
//
// Hedef URL override:  k6 run -e BASE_URL=http://localhost:8001 load-test.js
import http from "k6/http";
import { check, sleep } from "k6";
import { Counter } from "k6/metrics";

// kind cluster.yaml, order-svc NodePort 30801'i host 8001'e map ediyor.
export const BASE_URL = __ENV.BASE_URL || "http://localhost:8001";

// İstek başına "düşünme süresi" (saniye). Soak/load için gerçekçi davranış.
// 0 verirsen VU'lar nefes almadan basar (stress/spike için mantıklı).
const THINK = parseFloat(__ENV.THINK || "0");

// Trafiğin yüzde kaçı POST /orders olsun (gerisi GET /orders).
// POST daha pahalı (payment-svc + DB write) → bottleneck'i hızlandırır.
const POST_RATIO = parseFloat(__ENV.POST_RATIO || "0.2");

// Custom metrikler — k6 özetinde ayrı görünür.
export const ordersCreated = new Counter("orders_created");
export const ordersFailed = new Counter("orders_failed");

// Tek bir kullanıcı iterasyonu: ya GET ya POST.
export function userFlow() {
  const roll = Math.random();
  if (roll < POST_RATIO) {
    const res = http.post(`${BASE_URL}/orders`, null, {
      tags: { endpoint: "POST /orders" },
    });
    const ok = check(res, {
      "POST /orders status 200": (r) => r.status === 200,
    });
    if (ok) ordersCreated.add(1);
    else ordersFailed.add(1);
  } else {
    const res = http.get(`${BASE_URL}/orders`, {
      tags: { endpoint: "GET /orders" },
    });
    check(res, {
      "GET /orders status 200": (r) => r.status === 200,
    });
  }
  if (THINK > 0) sleep(THINK);
}
