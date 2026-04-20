import redis
import json

# BUG: timeout yok — Redis yavaşlarsa veya durursa sonsuza kadar bekler
# BUG: decode_responses olmadan binary dönebilir
redis_client = redis.Redis(host="redis", port=6379, db=0)


def get_cached_product(product_id: int):
    data = redis_client.get(f"product:{product_id}")
    if data:
        return json.loads(data)
    return None


def set_cached_product(product_id: int, product_data: dict):
    # BUG: TTL yok — cache sonsuza kadar yaşar, invalidation elle yapılmalı
    redis_client.set(f"product:{product_id}", json.dumps(product_data))


def get_cached_product_list():
    data = redis_client.get("products:all")
    if data:
        return json.loads(data)
    return None


def set_cached_product_list(products_data: list):
    redis_client.set("products:all", json.dumps(products_data))


# BUG: Ürün güncellendiğinde cache invalidation yok
# set_cached_product günceller ama products:all listesi stale kalır
