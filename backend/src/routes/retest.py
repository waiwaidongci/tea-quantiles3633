from fastapi import APIRouter,Depends
from src.config.database import get_db
from src.middlewares.auth import current_user,writer
from src.schemas.retest import ClaimInput,QuotaInput
from src.controllers import retest
router=APIRouter()
@router.get('/retest/state')
def state(day:str=None,db=Depends(get_db),user=Depends(current_user)): return retest.state(db,day)
@router.post('/retest/compile')
def compile_draft(day:str=None,db=Depends(get_db),user=Depends(writer)): return retest.compile_draft(db,user,day)
@router.post('/retest/publish')
def publish(day:str=None,db=Depends(get_db),user=Depends(writer)): return retest.publish(db,user,day)
@router.post('/retest/claim')
def claim(data:ClaimInput,day:str=None,db=Depends(get_db),user=Depends(writer)): return retest.claim(db,data,user,day)
@router.put('/retest/studies/{id}/quota')
def quota(id:int,data:QuotaInput,db=Depends(get_db),user=Depends(writer)): return retest.set_quota(db,id,data,user)
