import httpx


PAYMENT_SERVICE_URL = "https://httpbin.org/post"


def process_payment(order_id: int, amount: float, customer_email: str) -> bool:
    # BUG: timeout yok — payment servisi yavaşlarsa thread sonsuza kadar bloklanır
    # BUG: retry yok — geçici network hatası sipariş kaybına yol açar
    # BUG: circuit breaker yok — payment servisi down ise tüm istekler birikir
    response = httpx.post(
        PAYMENT_SERVICE_URL,
        json={
            "order_id": order_id,
            "amount": amount,
            "customer_email": customer_email,
        },
    )

    return response.status_code == 200
