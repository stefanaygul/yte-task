# Backend Developer Görevleri — Chaos E-Commerce

## Senaryo
Black Friday gecesi 03:00. Alarm çaldı. Sistem "çalışıyor" ama müşteriler şikayetçi:
siparişler kayboluyor, stoklar eksilere düşüyor, bazı istekler asla dönmüyor.
Senin görevin kodu inceleyip bug'ları bulmak ve fix'lemek.

---

## B1 — Startup Resilience (Kolay)
**Dosya:** `api/database.py`, `api/main.py`
**Problem:** Uygulama başlarken DB'ye bağlanamıyorsa anında crash oluyor. Container orchestration'da servisler sırayla ayağa kalkmaz.
**Görev:**
- DB bağlantısı için retry mekanizması ekle (exponential backoff)
- `Base.metadata.create_all()` çağrısını retry ile sar

**Çıktı:** `docker-compose down && docker-compose up` komutunu 5 kez çalıştır, hiçbirinde crash olmamalı.

---

## B2 — Connection Pool Tuning (Kolay)
**Dosya:** `api/database.py`
**Problem:** `pool_size=5` ve `max_overflow=0`. 6. concurrent istek DB bağlantısı bulamaz.
**Görev:**
- Uygun pool_size ve max_overflow değerlerini belirle
- Neden bu değerleri seçtiğini açıkla (container RAM, PostgreSQL max_connections ile ilişki)

**Çıktı:** Locust ile 50 concurrent user test et, connection timeout hatası olmamalı.

---

## B3 — Race Condition Fix (Orta)
**Dosya:** `api/routers/orders.py`
**Problem:** İki kullanıcı aynı anda son 1 ürünü sipariş edebilir. `SELECT ... FOR UPDATE` yok.
**Görev:**
- Stok kontrolünde pessimistic locking uygula
- Veya optimistic locking (version column) kullan — yaklaşımını açıkla

**Test:** İki terminal aç, aynı anda `curl` ile aynı ürüne sipariş ver. Stok negatife düşmemeli.

---

## B4 — N+1 Query (Orta)
**Dosya:** `api/routers/orders.py`
**Problem:** `list_orders` endpoint'i her order için ayrı query atıyor (lazy loading).
**Görev:**
- `joinedload` veya `selectinload` kullanarak N+1 sorununu çöz
- Fix öncesi ve sonrası query sayısını logla/karşılaştır

**Çıktı:** 100 sipariş varken `GET /orders/` tek bir query ile dönmeli.

---

## B5 — Payment Timeout & Retry (Orta)
**Dosya:** `api/services/payment.py`
**Problem:** Payment servisi timeout olmadan çağrılıyor. Servis yavaşlarsa thread bloklanır.
**Görev:**
- httpx çağrısına timeout ekle (connect + read)
- Retry mekanizması ekle (max 3 deneme, exponential backoff)
- Idempotency key kullan (aynı ödeme iki kez alınmasın)

**Çıktı:** Payment servisi 10s gecikmeyle döndüğünde API 5s içinde cevap vermeli.

---

## B6 — Circuit Breaker (Zor)
**Dosya:** `api/services/payment.py`
**Problem:** Payment servisi down olduğunda tüm istekler timeout'a kadar bekler, cascade failure oluşur.
**Görev:**
- Circuit breaker pattern'ı uygula (closed → open → half-open)
- Eşik değerlerini sen belirle (kaç hata sonrası açılsın, ne kadar süre sonra half-open'a geçsin)
- Kütüphane kullanabilirsin (tenacity, pybreaker) veya kendin yaz

**Çıktı:** Payment 5 kez üst üste fail ettikten sonra circuit açılmalı, sonraki istekler anında fail etmeli.

---

## B7 — Cache Invalidation (Orta)
**Dosya:** `api/services/cache.py`, `api/routers/products.py`
**Problem:** Ürün eklendiğinde veya stok değiştiğinde cache güncellenmemiyor.
**Görev:**
- Cache TTL ekle
- Ürün oluşturulduğunda / güncellendiğinde ilgili cache key'lerini invalidate et
- Cache stampede'e karşı önlem al (lock veya probabilistic early expiration)

**Çıktı:** Ürün stoku 0'a düştüğünde, `GET /products/` hâlâ eski stoku göstermemeli.

---

## B8 — Redis Failure Handling (Orta)
**Dosya:** `api/services/cache.py`
**Problem:** Redis down olursa tüm API çöker. Cache bir optimization, kritik yol olmamalı.
**Görev:**
- Redis çağrılarına timeout ekle
- Redis down olduğunda graceful fallback yap (doğrudan DB'den oku)
- try/except ile cache hatalarını yut ama logla

**Çıktı:** `docker stop redis` sonrası API çalışmaya devam etmeli.

---

## B9 — Distributed Transaction (Zor)
**Dosya:** `api/routers/orders.py`
**Problem:** DB commit başarılı olur ama queue publish başarısız olursa, sipariş DB'de var ama event gönderilmez.
**Görev:**
- Outbox pattern uygula: event'i ayrı bir tabloya yaz, ayrı bir process queue'ya publish etsin
- Veya Saga pattern ile compensating transaction yaz

**Çıktı:** Queue down iken sipariş verildiğinde, queue geri gelince event'in gönderildiğini doğrula.

---

## B10 — Worker Connection Management (Kolay)
**Dosya:** `worker/consumer.py`
**Problem:** Her mesajda yeni DB engine + session oluşturuluyor.
**Görev:**
- Global connection pool oluştur, callback içinde session kullan
- Hatalı mesajları DLQ'ya gönder (basic_nack + requeue=False)
- prefetch_count ayarla

**Çıktı:** 1000 mesaj gönder, DB connection sayısı sabit kalmalı (`SELECT count(*) FROM pg_stat_activity`).

---

## Değerlendirme Rubriği

| Puan | Açıklama |
|------|----------|
| 0 | Yapılmadı |
| 1 | Denendi ama çalışmıyor veya yeni bug ekledi |
| 2 | Çalışıyor ama neden bu yaklaşımı seçtiği açıklanmamış |
| 3 | Çalışıyor + trade-off analizi yapılmış + test edilmiş |
