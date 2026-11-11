import random,hashlib,json
from sqlalchemy import select,func
from src.config.database import Base,engine,SessionLocal
from src.models import *
from src.utils.security import hash_password
from src.services.apriori import mine_rules
PRODUCTS=[('OAT','燕麦拿铁','饮品',15.,7.),('BREAD','全麦餐包','烘焙',9.,3.5),('YOG','原味酸奶','乳品',8.,4.),('NUT','每日坚果','零食',12.,5.),('TEA','乌龙冷萃','饮品',10.,3.),('RICE','海苔饭团','鲜食',7.,3.),('EGG','溏心鸡蛋','鲜食',5.,2.),('SAND','鸡肉三明治','鲜食',16.,8.),('APPLE','鲜切苹果','水果',8.,4.),('COOK','燕麦曲奇','烘焙',11.,4.),('WATER','山泉水','饮品',3.,1.),('CHOC','黑巧方块','零食',13.,5.)]
def seed():
 Base.metadata.create_all(engine)
 with SessionLocal() as db:
  for role,name in [('admin','沈禾 · 选品负责人'),('analyst','陆简 · 商品研究员'),('viewer','林栩 · 门店督导')]:
   email=role+'@gucang.demo'
   if not db.scalar(select(User).where(User.email==email)): db.add(User(email=email,name=name,role=role,password_hash=hash_password('Gucang2026!')))
  for sku,name,category,price,cost in PRODUCTS:
   if not db.scalar(select(Product).where(Product.sku==sku)): db.add(Product(sku=sku,name=name,category=category,price=price,cost=cost))
  db.commit();rng=random.Random(20261112)
  for idx,title in enumerate(['秋季早餐街区','午间便利补给','晚间轻食样本']):
   name=f'{title} · 400篮'
   generated=[]
   for i in range(400):
    items=set()
    if rng.random()<.39:
     items.add('OAT')
     if rng.random()<.78: items.add('BREAD')
     if rng.random()<.40: items.add('EGG')
    if rng.random()<.28:
     items.add('YOG')
     if rng.random()<.68: items.add('NUT')
    if rng.random()<.26:
     items.add('RICE')
     if rng.random()<.70: items.add('TEA')
    for sku,_,_,_,_ in PRODUCTS:
     if rng.random()<.055: items.add(sku)
    if not items: items.add(rng.choice(PRODUCTS)[0])
    generated.append({'reference':f'A{idx+1}-{i+1:04d}','items':sorted(items)})
   batch=db.scalar(select(ReceiptBatch).where(ReceiptBatch.name==name))
   if not batch:
    batch=ReceiptBatch(name=name,filename=f'gucang-autumn-baskets-{idx+1}.jsonl',checksum=hashlib.sha256(json.dumps(generated,sort_keys=True).encode()).hexdigest());db.add(batch);db.flush()
    db.add_all([Receipt(batch_id=batch.id,**x) for x in generated]);db.commit()
  admin=db.scalar(select(User).where(User.role=='admin'))
  if not db.scalar(select(RuleRun).where(RuleRun.name=='秋季早餐基准研究')):
   batch=db.scalar(select(ReceiptBatch).order_by(ReceiptBatch.id));baskets=list(db.scalars(select(Receipt.items).where(Receipt.batch_id==batch.id).order_by(Receipt.id)))
   products={p.sku:{'price':p.price,'cost':p.cost} for p in db.scalars(select(Product))}
   result=mine_rules(baskets,products,.05,.35,1.,3)
   run=RuleRun(name='秋季早餐基准研究',batch_id=batch.id,min_support=.05,min_confidence=.35,min_lift=1.,max_size=3,status='succeeded',result=result,creator_id=admin.id);db.add(run);db.flush()
   if result['rules']: db.add(BundleProposal(name='早餐温暖搭档 · 试点草案',run_id=run.id,rule=result['rules'][0],note='先在两家样板店验证陈列效果；关联不代表因果。',creator_id=admin.id))
   db.add(AuditLog(actor='seed',action='demo.created',detail={'receipts':1200,'seed':20261112}));db.commit()
  counts={t.__tablename__:db.scalar(select(func.count()).select_from(t)) for t in [User,Product,ReceiptBatch,Receipt,RuleRun,BundleProposal]}
  print(json.dumps(counts,ensure_ascii=False));return counts
if __name__=='__main__': seed()
