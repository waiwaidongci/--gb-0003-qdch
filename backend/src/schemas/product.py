from pydantic import BaseModel,Field,model_validator
class ProductInput(BaseModel):
 sku:str=Field(pattern=r'^[A-Z0-9-]{2,30}$')
 name:str=Field(min_length=1,max_length=80)
 category:str=Field(min_length=1,max_length=50)
 price:float=Field(gt=0,le=10000,allow_inf_nan=False)
 cost:float=Field(ge=0,le=10000,allow_inf_nan=False)
 @model_validator(mode='after')
 def check_cost(self):
  if self.cost>self.price: raise ValueError('成本不得高于售价')
  return self
