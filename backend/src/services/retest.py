from datetime import date
from fastapi import HTTPException
from sqlalchemy import select,func,update,delete
from sqlalchemy.exc import IntegrityError
from src.models.retest import RetestStudy,RetestSample,RetestClaim,RetestDraft,RetestDraftItem,RetestList,RetestListItem,RetestMeta
from src.services import retest_selection
from src.services.audits import log
from src.utils.serializers import record,now

def today(): return date.today().isoformat()

def _rev(db):
    row=db.get(RetestMeta,'src_rev')
    if not row: row=RetestMeta(key='src_rev',value=0);db.add(row);db.flush()
    return row.value

def _bump(db):
    db.execute(update(RetestMeta).where(RetestMeta.key=='src_rev').values(value=RetestMeta.value+1))

def _studies(db): return list(db.scalars(select(RetestStudy).where(RetestStudy.reviewed==True).order_by(RetestStudy.code)))
def _samples(db): return list(db.scalars(select(RetestSample).where(RetestSample.frozen==True).order_by(RetestSample.batch,RetestSample.number)))
def _claims(db,day): return list(db.scalars(select(RetestClaim).where(RetestClaim.day==day).order_by(RetestClaim.id)))
def _open_draft(db,day): return db.scalar(select(RetestDraft).where(RetestDraft.day==day,RetestDraft.status=='open').order_by(RetestDraft.id.desc()))
def _effective(db,day): return db.scalar(select(RetestList).where(RetestList.day==day).order_by(RetestList.version.desc()))

def _items(db,model,key,id): return list(db.scalars(select(model).where(getattr(model,key)==id).order_by(model.id)))

def state(db,day=None):
    day=day or today()
    studies=_studies(db);samples=_samples(db);claims=_claims(db,day)
    draft=_open_draft(db,day);lst=_effective(db,day)
    eff_items=_items(db,RetestListItem,'list_id',lst.id) if lst else []
    draft_items=_items(db,RetestDraftItem,'draft_id',draft.id) if draft else []
    code_of={s.id:s.code for s in studies}
    assigned={};claimed={}
    for it in eff_items: assigned[it.study_id]=assigned.get(it.study_id,0)+1
    for c in claims: claimed[c.study_id]=claimed.get(c.study_id,0)+1
    claim_by={(c.batch,c.number):c for c in claims}
    eff_by={(it.batch,it.number):it for it in eff_items}
    rev=_rev(db)
    def sample_row(s):
        key=(s.batch,s.number)
        holder=claim_by[key].study_id if key in claim_by else eff_by[key].study_id if key in eff_by else None
        return {**record(s),'status':'claimed' if key in claim_by else 'listed' if key in eff_by else 'free','holder':code_of.get(holder)}
    return {
        'day':day,'src_rev':rev,
        'studies':[{**record(s),'assigned':assigned.get(s.id,0),'claimed':claimed.get(s.id,0),'shortfall':max(0,s.quota-assigned.get(s.id,0))} for s in studies],
        'samples':[sample_row(s) for s in samples],
        'claims':[{**record(c),'code':code_of.get(c.study_id)} for c in claims],
        'draft':({'id':draft.id,'src_rev':draft.src_rev,'stale':draft.src_rev!=rev,'created_at':draft.created_at,
                  'items':[{**record(it),'code':code_of.get(it.study_id)} for it in draft_items]} if draft else None),
        'effective':({'id':lst.id,'version':lst.version,'published_at':lst.published_at,
                      'items':[{**record(it),'code':code_of.get(it.study_id)} for it in eff_items]} if lst else None),
    }

def compile_draft(db,user,day=None):
    day=day or today()
    for old in list(db.scalars(select(RetestDraft).where(RetestDraft.day==day,RetestDraft.status=='open'))):
        db.execute(delete(RetestDraftItem).where(RetestDraftItem.draft_id==old.id));db.delete(old)
    studies=_studies(db);samples=_samples(db);claims=_claims(db,day)
    picked=retest_selection.select(
        [{'id':s.id,'code':s.code,'quota':s.quota,'limits':s.limits or {}} for s in studies],
        [{'id':s.id,'batch':s.batch,'number':s.number,'indicators':s.indicators or {}} for s in samples],
        [{'study_id':c.study_id,'batch':c.batch,'number':c.number} for c in claims])
    draft=RetestDraft(day=day,src_rev=_rev(db),status='open',created_at=now());db.add(draft);db.flush()
    for p in picked: db.add(RetestDraftItem(draft_id=draft.id,study_id=p['study_id'],batch=p['batch'],number=p['number'],claimed=p['claimed']))
    log(db,user,'retest.compile',f'{day} 入选{len(picked)}份');db.commit()
    return state(db,day)

def publish(db,user,day=None):
    day=day or today()
    draft=_open_draft(db,day)
    if not draft: raise HTTPException(404,'当日没有可发布的草稿，请先编单')
    # 原子切换：仅当草稿未过期时置为已发布，并发领样/名额调整会推进 src_rev 使旧草稿切换失败。
    result=db.execute(update(RetestDraft).where(RetestDraft.id==draft.id,RetestDraft.status=='open',RetestDraft.src_rev==_rev(db)).values(status='published'))
    if result.rowcount==0: raise HTTPException(409,'草稿已过期：编单后发生领样或名额调整，请重新编单')
    version=db.scalar(select(func.coalesce(func.max(RetestList.version),0)).where(RetestList.day==day))+1
    lst=RetestList(day=day,version=version,published_at=now());db.add(lst);db.flush()
    items=_items(db,RetestDraftItem,'draft_id',draft.id)
    for it in items: db.add(RetestListItem(list_id=lst.id,study_id=it.study_id,batch=it.batch,number=it.number,claimed=it.claimed))
    log(db,user,'retest.publish',f'{day} 第{version}版 整单{len(items)}条');db.commit()
    return state(db,day)

def claim(db,data,user,day=None):
    day=day or today()
    lst=_effective(db,day)
    if not lst: raise HTTPException(409,'当日尚未发布生效单，不能领样')
    item=db.scalar(select(RetestListItem).where(RetestListItem.list_id==lst.id,RetestListItem.study_id==data.study_id,RetestListItem.batch==data.batch,RetestListItem.number==data.number))
    if not item: raise HTTPException(404,'该茶样不在当日生效单中，或不属于该研究')
    if db.scalar(select(RetestClaim).where(RetestClaim.day==day,RetestClaim.batch==data.batch,RetestClaim.number==data.number)):
        raise HTTPException(409,'同批同编号当日已被领用')
    db.add(RetestClaim(day=day,study_id=data.study_id,batch=data.batch,number=data.number,created_at=now()))
    item.claimed=True
    _bump(db)
    try: db.flush()
    except IntegrityError:  # 并发领样撞上唯一约束：同批同编号当日只认第一笔
        db.rollback();raise HTTPException(409,'同批同编号当日已被领用')
    log(db,user,'retest.claim',f'{day} {data.batch}/{data.number}');db.commit()
    return state(db,day)

def set_quota(db,id,data,user):
    study=db.get(RetestStudy,id)
    if not study: raise HTTPException(404,'复测研究不存在')
    study.quota=data.quota
    _bump(db);log(db,user,'retest.quota',f'{study.code} 名额={data.quota}');db.commit()
    return record(study)
