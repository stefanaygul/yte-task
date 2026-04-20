from locust import HttpUser, task, between
import random


class ECommerceUser(HttpUser):
    wait_time = between(0.5, 2)

    @task(5)
    def browse_products(self):
        self.client.get("/products/")

    @task(3)
    def view_product(self):
        product_id = random.randint(1, 8)
        self.client.get(f"/products/{product_id}")

    @task(1)
    def place_order(self):
        product_id = random.randint(1, 8)
        quantity = random.randint(1, 3)
        self.client.post("/orders/", json={
            "customer_email": f"user{random.randint(1, 1000)}@test.com",
            "items": [
                {"product_id": product_id, "quantity": quantity}
            ],
        })

    @task(1)
    def check_health(self):
        self.client.get("/health")
