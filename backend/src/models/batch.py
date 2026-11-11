from sqlalchemy.orm import Mapped,mapped_column
from sqlalchemy import String,DateTime
from datetime import datetime,timezone
from src.config.database import Base
class ReceiptBatch(Base):
 __tablename__='receipt_batches'
 id:Mapped[int]=mapped_column(primary_key=True)
 name:Mapped[str]=mapped_column(String(100),unique=True)
 filename:Mapped[str]=mapped_column(String(150))
 checksum:Mapped[str]=mapped_column(String(64))
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
