from sqlalchemy.orm import Mapped,mapped_column
from sqlalchemy import String,Float
from src.config.database import Base
class Product(Base):
 __tablename__='products'
 id:Mapped[int]=mapped_column(primary_key=True)
 sku:Mapped[str]=mapped_column(String(30),unique=True)
 name:Mapped[str]=mapped_column(String(80))
 category:Mapped[str]=mapped_column(String(50))
 price:Mapped[float]=mapped_column(Float)
 cost:Mapped[float]=mapped_column(Float)
