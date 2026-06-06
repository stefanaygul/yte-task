// capacity-test.js — LAB 4: Kapasite doğrulama + HPA gözlemleme.
//
// Amaç: Lab 2'de bulduğun "1 pod = ~N RPS @ SLO" rakamından hesapladığın hedef
// RPS'i (örn. 600) sisteme SABİT yük olarak basmak ve HPA'nın otomatik scale
// etmesini canlı izlemek.
//
// VU değil RPS hedefliyoruz: ramping-arrival-rate executor sabit bir İSTEK HIZI
// üretir (VU sayısını k6 kendi ayarlar). Kapasite planlaması RPS bazlıdır, bu yüzden
// doğru executor budur.
//
// Hedef RPS override:
//   k6 run -e RATE=600 k6-scripts/capacity-test.js
//
// Çalıştır (iki terminal):
//   T1: k6 run -e RATE=600 k6-scripts/capacity-test.js
//   T2: kubectl get hpa -w          # replica sayısı 2 → ... artışını izle
//   T2: watch -n2 kubectl top pods  # pod başına CPU %60 hedefine yaklaşıyor mu
//
// GÖZLEM: Scale-up ne kadar sürdü? Yeni pod Ready olana dek geçen sürede
// latency'ye ne oldu? (Bu, "proactive vs reactive scaling" tartışmasının kanıtı.)
import { userFlow } from "./common.js";

const RATE = parseInt(__ENV.RATE || "600", 10); // hedef istek/saniye

export const options = {
  scenarios: {
    capacity: {
      executor: "ramping-arrival-rate",
      startRate: 50, //  başlangıç RPS
      timeUnit: "1s", // "rate" = istek / saniye
      // VU havuzu: arrival-rate, hız tutturmak için VU ödünç alır. Az ayırırsan
      // k6 "insufficient VUs" uyarısı verir → bottleneck k6 olur, sistem değil.
      preAllocatedVUs: 100,
      maxVUs: 500,
      stages: [
        { duration: "1m", target: RATE }, // hedef RPS'e ramp → HPA tetiklenmeye başlar
        { duration: "4m", target: RATE }, // uzun steady → HPA stabilize olsun, scale tamamlansın
        { duration: "30s", target: 0 }, // ramp-down → scale-down (cooldown sonrası) izlenebilir
      ],
    },
  },
  thresholds: {
    // Kapasite YETERLİYSE bu SLO'lar yük boyunca korunur. HPA yeterince hızlı
    // scale edemezse p99 geçici aşılır → tam da görmek istediğimiz an.
    "http_req_duration": ["p(99)<500"],
    "http_req_failed": ["rate<0.01"],
  },
  summaryTrendStats: ["avg", "med", "p(95)", "p(99)", "max"],
};

export default function () {
  userFlow();
}
