from fastapi import APIRouter,Depends
from sqlalchemy.orm import Session
from sqlalchemy import select
from src.config.database import get_db
from src.controllers.dependencies import current_user
from src.models import AuditLog
from src.utils.serialize import row
router=APIRouter()
@router.get('/audit')
def logs(db:Session=Depends(get_db),user=Depends(current_user)): return [row(a) for a in db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(200))]
