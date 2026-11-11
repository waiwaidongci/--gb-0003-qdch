from sqlalchemy.orm import Mapped,mapped_column
from sqlalchemy import String,JSON,ForeignKey,UniqueConstraint
from src.config.database import Base
class Receipt(Base):
 __tablename__='receipts'
 __table_args__=(UniqueConstraint('batch_id','reference'),)
 id:Mapped[int]=mapped_column(primary_key=True)
 batch_id:Mapped[int]=mapped_column(ForeignKey('receipt_batches.id'))
 reference:Mapped[str]=mapped_column(String(70))
 items:Mapped[list]=mapped_column(JSON)
