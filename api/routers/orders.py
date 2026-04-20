from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Product, Order, OrderItem
from schemas import OrderCreate
from services.payment import process_payment
from services.queue import publish_order_event

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("/")
def create_order(order_data: OrderCreate, db: Session = Depends(get_db)):
    order = Order(customer_email=order_data.customer_email)
    db.add(order)
    db.flush()

    total = 0.0

    for item in order_data.items:
        # BUG: N+1 query — her item için ayrı SELECT
        product = db.query(Product).filter(Product.id == item.product_id).first()
        if not product:
            raise HTTPException(status_code=404, detail=f"Product {item.product_id} not found")

        # BUG: Race condition — SELECT ... FOR UPDATE yok
        # İki concurrent istek aynı stok'u okuyup ikisi de sipariş verebilir
        if product.stock < item.quantity:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient stock for {product.name}",
            )

        product.stock -= item.quantity

        order_item = OrderItem(
            order_id=order.id,
            product_id=product.id,
            quantity=item.quantity,
            unit_price=product.price,
        )
        db.add(order_item)
        total += product.price * item.quantity

    order.total_amount = total

    # BUG: Distributed transaction yok
    # DB commit başarılı olur ama queue publish başarısız olursa
    # sipariş DB'de var ama event hiç gönderilmez
    db.commit()

    payment_ok = process_payment(order.id, total, order_data.customer_email)

    if payment_ok:
        order.status = "paid"
        db.commit()

        publish_order_event(order.id, "order_paid", {
            "customer_email": order_data.customer_email,
            "total": total,
        })
    else:
        # BUG: Stok geri verilmiyor — ödeme başarısız olsa da stok düşmüş kalır
        order.status = "cancelled"
        db.commit()

    return {
        "order_id": order.id,
        "status": order.status,
        "total": total,
    }


@router.get("/")
def list_orders(db: Session = Depends(get_db)):
    orders = db.query(Order).all()
    result = []
    for o in orders:
        # BUG: N+1 query — her order için items ayrı sorgulanır (lazy loading)
        items = [
            {
                "product_id": item.product_id,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
            }
            for item in o.items
        ]
        result.append({
            "id": o.id,
            "customer_email": o.customer_email,
            "total_amount": o.total_amount,
            "status": o.status,
            "items": items,
        })
    return result


@router.get("/{order_id}")
def get_order(order_id: int, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    return {
        "id": order.id,
        "customer_email": order.customer_email,
        "total_amount": order.total_amount,
        "status": order.status,
        "items": [
            {
                "product_id": item.product_id,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
            }
            for item in order.items
        ],
    }
