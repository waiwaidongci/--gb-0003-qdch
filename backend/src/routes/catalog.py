from fastapi import APIRouter,Depends
from sqlalchemy.orm import Session
from src.config.database import get_db
from src.controllers.dependencies import current_user,writers
from src.controllers.catalog import catalog_summary
from src.services import products,batches
from src.schemas.product import ProductInput
from src.schemas.batch import BatchInput
router=APIRouter(tags=['catalog'])
@router.get('/catalog')
def summary(db:Session=Depends(get_db),user=Depends(current_user)): return catalog_summary(db)
@router.get('/products')
def all_products(db:Session=Depends(get_db),user=Depends(current_user)): return products.list_products(db)
@router.post('/products',status_code=201)
def add_product(data:ProductInput,db:Session=Depends(get_db),user=Depends(writers)): return products.save_product(db,data,user)
@router.get('/batches')
def all_batches(db:Session=Depends(get_db),user=Depends(current_user)): return batches.list_batches(db)
@router.post('/batches',status_code=201)
def add_batch(data:BatchInput,db:Session=Depends(get_db),user=Depends(writers)): return batches.create_batch(db,data,user)
@router.get('/batches/{id}/receipts')
def receipts(id:int,db:Session=Depends(get_db),user=Depends(current_user)): return batches.list_receipts(db,id)
