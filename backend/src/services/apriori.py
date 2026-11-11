from itertools import combinations
from math import ceil
import hashlib,json

def mine_rules(baskets,products,min_support=.05,min_confidence=.35,min_lift=1.,max_size=3):
 if not baskets: raise ValueError('批次没有收据')
 if not 0<min_support<=1 or not 0<min_confidence<=1 or not 0<=min_lift<=100 or not 2<=max_size<=4: raise ValueError('阈值不合法')
 transactions=[frozenset(b) for b in baskets]
 if any(not b for b in transactions): raise ValueError('收据不得为空')
 if any(not b.issubset(products) for b in transactions): raise ValueError('存在未知商品')
 n=len(transactions);minimum=ceil(n*min_support-1e-12)
 universe=sorted(set().union(*transactions));counts={};previous=set()
 for sku in universe:
  item=frozenset([sku]);count=sum(item<=t for t in transactions)
  if count>=minimum: counts[item]=count;previous.add(item)
 level_counts=[len(previous)]
 for size in range(2,max_size+1):
  candidates=set()
  for a,b in combinations(sorted(previous,key=lambda x:tuple(sorted(x))),2):
   union=a|b
   if len(union)==size and all(frozenset(s) in previous for s in combinations(union,size-1)): candidates.add(union)
  current=set()
  for candidate in candidates:
   count=sum(candidate<=t for t in transactions)
   if count>=minimum: counts[candidate]=count;current.add(candidate)
  level_counts.append(len(current));previous=current
  if not previous: break
 rules=[]
 for itemset,count in counts.items():
  if len(itemset)<2: continue
  for size in range(1,len(itemset)):
   for left in combinations(sorted(itemset),size):
    antecedent=frozenset(left);consequent=itemset-antecedent
    confidence=count/counts[antecedent];lift=confidence/(counts[consequent]/n)
    if confidence+1e-12<min_confidence or lift+1e-12<min_lift: continue
    price=sum(products[s]['price'] for s in itemset);cost=sum(products[s]['cost'] for s in itemset)
    rules.append({'antecedent':sorted(antecedent),'consequent':sorted(consequent),'support_count':count,'support':count/n,'confidence':confidence,'lift':lift,'bundle_price':round(price,2),'gross_profit':round(price-cost,2),'margin':(price-cost)/price if price else 0})
 rules.sort(key=lambda x:(-x['lift'],-x['confidence'],-x['support'],x['antecedent'],x['consequent']))
 return {'receipt_count':n,'frequent_itemsets':len(counts),'level_counts':level_counts,'rules':rules,'checksum':hashlib.sha256(json.dumps([sorted(t) for t in transactions],sort_keys=True).encode()).hexdigest(),'method':'Apriori / binary basket presence / no causal claims','formulas':{'support':'count(A∪B)/N','confidence':'count(A∪B)/count(A)','lift':'confidence(A→B)/support(B)','margin':'(sum(price)-sum(cost))/sum(price)'}}
