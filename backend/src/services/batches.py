import hashlib,json
from sqlalchemy import select,func
from fastapi import HTTPException
from src.models import ReceiptBatch,Receipt,Product
from src.utils.serialize import row
from .audit import record
def list_batches(db):
 return [dict(row(b),receipt_count=db.scalar(select(func.count()).select_from(Receipt).where(Receipt.batch_id==b.id))) for b in db.scalars(select(ReceiptBatch).order_by(ReceiptBatch.id))]
def create_batch(db,data,user):
 if db.scalar(select(ReceiptBatch).where(ReceiptBatch.name==data.name)): raise HTTPException(409,'批次名称已存在')
 refs=[x.reference for x in data.receipts]
 if len(refs)!=len(set(refs)): raise HTTPException(422,'收据 reference 重复')
 valid=set(db.scalars(select(Product.sku)))
 unknown=set(s for x in data.receipts for s in x.items)-valid
 if unknown: raise HTTPException(422,'未知 SKU: '+','.join(sorted(unknown)))
 rows=[{'reference':x.reference,'items':sorted(set(x.items))} for x in data.receipts]
 checksum=hashlib.sha256(json.dumps(rows,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
 batch=ReceiptBatch(name=data.name,filename=data.filename,checksum=checksum);db.add(batch);db.flush()
 db.add_all([Receipt(batch_id=batch.id,**r) for r in rows]);db.commit();record(db,user.email,'batch.import',{'batch_id':batch.id,'count':len(rows)});return dict(row(batch),receipt_count=len(rows))
def list_receipts(db,batch_id):
 if not db.get(ReceiptBatch,batch_id): raise HTTPException(404,'批次不存在')
 return [row(x) for x in db.scalars(select(Receipt).where(Receipt.batch_id==batch_id).order_by(Receipt.id).limit(100))]
