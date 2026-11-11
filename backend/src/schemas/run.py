from pydantic import BaseModel,Field
class RunInput(BaseModel):
 name:str=Field(min_length=1,max_length=100)
 batch_id:int=Field(gt=0)
 min_support:float=Field(ge=.01,le=1,allow_inf_nan=False)
 min_confidence:float=Field(ge=.01,le=1,allow_inf_nan=False)
 min_lift:float=Field(ge=0,le=100,allow_inf_nan=False)
 max_size:int=Field(ge=2,le=4)
