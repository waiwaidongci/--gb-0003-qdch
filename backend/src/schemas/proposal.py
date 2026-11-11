from pydantic import BaseModel,Field
from typing import Literal
class ProposalInput(BaseModel):
 run_id:int=Field(gt=0)
 rule_index:int=Field(ge=0)
 name:str=Field(min_length=1,max_length=100)
 note:str=Field(max_length=500,default='')
class ReviewInput(BaseModel):
 status:Literal['approved','rejected']
 note:str=Field(max_length=500)
