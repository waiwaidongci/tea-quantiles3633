from sqlalchemy import Column,Integer,String,JSON,Boolean,ForeignKey,UniqueConstraint
from src.config.database import Base

class RetestStudy(Base):
    """已复核研究及其指标下限与当日名额。"""
    __tablename__='retest_studies'
    id=Column(Integer,primary_key=True)
    code=Column(String(40),unique=True,nullable=False)
    name=Column(String(120),nullable=False)
    limits=Column(JSON,nullable=False,default=dict)
    quota=Column(Integer,nullable=False,default=0)
    reviewed=Column(Boolean,nullable=False,default=True)

class RetestSample(Base):
    """冻结茶样留样，同批同编号唯一。"""
    __tablename__='retest_samples'
    __table_args__=(UniqueConstraint('batch','number'),)
    id=Column(Integer,primary_key=True)
    batch=Column(String(40),nullable=False)
    number=Column(String(40),nullable=False)
    indicators=Column(JSON,nullable=False,default=dict)
    frozen=Column(Boolean,nullable=False,default=True)

class RetestClaim(Base):
    """当日领用记录：同批同编号一天只能领用一次，归属不再变更。"""
    __tablename__='retest_claims'
    __table_args__=(UniqueConstraint('day','batch','number'),)
    id=Column(Integer,primary_key=True)
    day=Column(String(10),nullable=False)
    study_id=Column(Integer,ForeignKey('retest_studies.id'),nullable=False)
    batch=Column(String(40),nullable=False)
    number=Column(String(40),nullable=False)
    created_at=Column(String(40),nullable=False)

class RetestDraft(Base):
    """当日复测草稿单；src_rev 记录编单时的来源版本，用于发布前校验。"""
    __tablename__='retest_drafts'
    id=Column(Integer,primary_key=True)
    day=Column(String(10),nullable=False)
    src_rev=Column(Integer,nullable=False)
    status=Column(String(20),nullable=False,default='open')
    created_at=Column(String(40),nullable=False)

class RetestDraftItem(Base):
    __tablename__='retest_draft_items'
    id=Column(Integer,primary_key=True)
    draft_id=Column(Integer,ForeignKey('retest_drafts.id'),nullable=False)
    study_id=Column(Integer,ForeignKey('retest_studies.id'),nullable=False)
    batch=Column(String(40),nullable=False)
    number=Column(String(40),nullable=False)
    claimed=Column(Boolean,nullable=False,default=False)

class RetestList(Base):
    """生效单：发布时整单一次性切换，旧版本整体保留备查。"""
    __tablename__='retest_lists'
    id=Column(Integer,primary_key=True)
    day=Column(String(10),nullable=False)
    version=Column(Integer,nullable=False)
    published_at=Column(String(40),nullable=False)

class RetestListItem(Base):
    __tablename__='retest_list_items'
    id=Column(Integer,primary_key=True)
    list_id=Column(Integer,ForeignKey('retest_lists.id'),nullable=False)
    study_id=Column(Integer,ForeignKey('retest_studies.id'),nullable=False)
    batch=Column(String(40),nullable=False)
    number=Column(String(40),nullable=False)
    claimed=Column(Boolean,nullable=False,default=False)

class RetestMeta(Base):
    """来源版本计数：领样或名额调整都会推进，草稿据此判过期。"""
    __tablename__='retest_meta'
    key=Column(String(40),primary_key=True)
    value=Column(Integer,nullable=False,default=0)
