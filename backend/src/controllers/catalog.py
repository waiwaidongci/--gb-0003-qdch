from src.services import products,batches
from src.utils.serialize import row
def catalog_summary(db):
 ps=products.list_products(db);bs=batches.list_batches(db)
 return {'products':ps,'batches':bs,'receipt_count':sum(x['receipt_count'] for x in bs)}
