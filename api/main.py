from fastapi import FastAPI
from database import engine, Base
from routers import products, orders, health

# BUG: DB bağlantı retry yok — PostgreSQL henüz hazır değilse uygulama crash olur
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Chaos E-Commerce API", version="0.1.0")

app.include_router(health.router)
app.include_router(products.router)
app.include_router(orders.router)


@app.on_event("startup")
async def seed_data():
    from database import SessionLocal
    from models import Product

    db = SessionLocal()
    if db.query(Product).count() == 0:
        sample_products = [
            Product(name="Mechanical Keyboard", price=89.99, stock=100, category="electronics"),
            Product(name="USB-C Hub", price=34.99, stock=200, category="electronics"),
            Product(name="Standing Desk Mat", price=49.99, stock=150, category="office"),
            Product(name="Noise Cancelling Headphones", price=199.99, stock=50, category="electronics"),
            Product(name="Webcam HD 1080p", price=59.99, stock=75, category="electronics"),
            Product(name="Ergonomic Mouse", price=44.99, stock=120, category="electronics"),
            Product(name="Monitor Light Bar", price=39.99, stock=90, category="office"),
            Product(name="Laptop Stand", price=29.99, stock=180, category="office"),
        ]
        db.add_all(sample_products)
        db.commit()
    db.close()
