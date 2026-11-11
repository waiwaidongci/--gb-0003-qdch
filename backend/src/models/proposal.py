from sqlalchemy.orm import Mapped,mapped_column
from sqlalchemy import String,JSON,ForeignKey,DateTime
from datetime import datetime,timezone
from src.config.database import Base
class BundleProposal(Base):
 __tablename__='bundle_proposals'
 id:Mapped[int]=mapped_column(primary_key=True)
 run_id:Mapped[int]=mapped_column(ForeignKey('rule_runs.id'))
 name:Mapped[str]=mapped_column(String(100))
 status:Mapped[str]=mapped_column(String(20),default='draft')
 rule:Mapped[dict]=mapped_column(JSON)
 note:Mapped[str]=mapped_column(String(500),default='')
 creator_id:Mapped[int]=mapped_column(ForeignKey('users.id'))
 created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
