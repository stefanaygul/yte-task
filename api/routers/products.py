from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Product
from schemas import ProductCreate
from services.cache import (
    get_cached_product,
    set_cached_product,
    get_cached_product_list,
    set_cached_product_list,
)

router = APIRouter(prefix="/products", tags=["products"])


@router.get("/")
def list_products(db: Session = Depends(get_db)):
    cached = get_cached_product_list()
    if cached:
        return cached

    products = db.query(Product).all()
    result = [
        {
            "id": p.id,
            "name": p.name,
            "price": p.price,
            "stock": p.stock,
            "category": p.category,
        }
        for p in products
    ]
    set_cached_product_list(result)
    return result


@router.get("/{product_id}")
def get_product(product_id: int, db: Session = Depends(get_db)):
    cached = get_cached_product(product_id)
    if cached:
        return cached

    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    result = {
        "id": product.id,
        "name": product.name,
        "description": product.description,
        "price": product.price,
        "stock": product.stock,
        "category": product.category,
    }
    set_cached_product(product_id, result)
    return result


@router.post("/")
def create_product(product: ProductCreate, db: Session = Depends(get_db)):
    db_product = Product(**product.model_dump())
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    # BUG: products:all cache invalidate edilmiyor — liste stale kalır
    return {"id": db_product.id, "name": db_product.name}
