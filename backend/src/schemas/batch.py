from pydantic import BaseModel,Field
class ReceiptInput(BaseModel):
 reference:str=Field(min_length=1,max_length=70)
 items:list[str]=Field(min_length=1,max_length=30)
class BatchInput(BaseModel):
 name:str=Field(min_length=1,max_length=100)
 filename:str=Field(min_length=1,max_length=150)
 receipts:list[ReceiptInput]=Field(min_length=2,max_length=5000)
