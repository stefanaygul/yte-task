// spike-test.js — LAB 3: Spike (ani yük) testi.
//
// Amaç: Trafiğin ANİDEN patlamasına (flash sale, viral tweet, retry fırtınası)
// sistemin tepkisini görmek. Stress'ten farkı: yük kademeli değil, BİR ANDA çıkar.
//
// İzlenecek: Spike anında latency/error fırlar mı? Spike bitince sistem NE KADAR
// SÜREDE normale döner (recovery time)? Kalıcı hasar (crash, OOM, takılı kalma) var mı?
//
// Profil: 100 VU baseline → 10sn'de 1000'e fırla → 30sn tut → 100'e düş → recovery izle.
//
// Çalıştır:
//   T1: k6 run k6-scripts/spike-test.js
//   T2: watch -n1 kubectl top pods
import { userFlow } from "./common.js";

export const options = {
  stages: [
    { duration: "30s", target: 100 }, // sakin baseline
    { duration: "10s", target: 1000 }, // 💥 SPIKE — 10sn'de 10x
    { duration: "30s", target: 1000 }, // tepede tut
    { duration: "10s", target: 100 }, // ani düşüş
    { duration: "1m", target: 100 }, // RECOVERY: latency normale dönüyor mu?
    { duration: "20s", target: 0 },
  ],
  summaryTrendStats: ["avg", "med", "p(90)", "p(95)", "p(99)", "max"],
};

export default function () {
  userFlow();
}
