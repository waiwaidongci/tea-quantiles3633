from pydantic import BaseModel,Field
class RetestClaimInput(BaseModel):
    study_id:int=Field(gt=0)
    batch:str=Field(min_length=1,max_length=40)
    number:str=Field(min_length=1,max_length=40)
class RetestQuotaInput(BaseModel):
    quota:int=Field(ge=0,le=5000)
ClaimInput=RetestClaimInput
QuotaInput=RetestQuotaInput
