from sqlalchemy.orm import Mapped,mapped_column
from sqlalchemy import String,JSON,Float,Integer,ForeignKey,DateTime
from datetime import datetime,timezone
from src.config.database import Base
class RuleRun(Base):
 __tablename__='rule_runs'
 id:Mapped[int]=mapped_column(primary_key=True)
 batch_id:Mapped[int]=mapped_column(ForeignKey('receipt_batches.id'))
 name:Mapped[str]=mapped_column(String(100))
 status:Mapped[str]=mapped_column(String(20),default='queued')
 min_support:Mapped[float]=mapped_column(Float)
 min_confidence:Mapped[float]=mapped_column(Float)
 min_lift:Mapped[float]=mapped_column(Float,default=1.)
 max_size:Mapped[int]=mapped_column(Integer,default=3)
 result:Mapped[dict]=mapped_column(JSON,default=dict)
 error:Mapped[str|None]=mapped_column(String(1000),nullable=True)
 creator_id:Mapped[int]=mapped_column(ForeignKey('users.id'))
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
