from sqlalchemy import select
from fastapi import HTTPException
from src.models import Product
from src.utils.serialize import row
from .audit import record
def list_products(db): return [dict(row(p),margin=round((p.price-p.cost)/p.price,4)) for p in db.scalars(select(Product).order_by(Product.id))]
def save_product(db,data,user):
 if db.scalar(select(Product).where(Product.sku==data.sku)): raise HTTPException(409,'SKU 已存在')
 item=Product(**data.model_dump());db.add(item);db.commit();record(db,user.email,'product.create',{'sku':item.sku});return row(item)
