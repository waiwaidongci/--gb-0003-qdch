from src.services import runs,proposals
from src.utils.csv_export import csv_response
from src.models import Product
from sqlalchemy import select
def export_rules(db,id):
 r=runs.get_run(db,id);names={p.sku:p.name for p in db.scalars(select(Product))}
 rules=r.result.get('rules',[])
 return csv_response(f'rules-{id}.csv',[[','.join(names.get(s,s) for s in x['antecedent']),','.join(names.get(s,s) for s in x['consequent']),x['support_count'],x['support'],x['confidence'],x['lift'],x['gross_profit'],x['margin']] for x in rules],['前件','后件','支持数','支持度','置信度','提升度','组合毛利','毛利率'])
def export_proposals(db):
 return csv_response('bundle-proposals.csv',[[p['id'],p['name'],p['status'],','.join(p['rule']['antecedent']),','.join(p['rule']['consequent']),p['rule']['lift'],p['note']] for p in proposals.list_proposals(db)],['编号','提案','状态','前件SKU','后件SKU','提升度','说明'])
