"""复测单测试公共基建：环境变量、fakeredis 补丁、建表与演示数据。

注意：本模块必须在任何 src.* 导入之前完成环境变量与 Redis 补丁。
"""
import os,tempfile
os.environ.setdefault('DATABASE_URL','sqlite:///'+os.path.join(tempfile.gettempdir(),'retest_test.sqlite3'))
os.environ.setdefault('JWT_SECRET','retest-test-secret')
os.environ.setdefault('REDIS_URL','redis://127.0.0.1:9/0')
os.environ.setdefault('SEED_DEMO','false')
import fakeredis
from redis import Redis
Redis.from_url=fakeredis.FakeStrictRedis.from_url

from sqlalchemy import delete
from src.config.database import Base,engine,Session
from src.models import user,study,observation,run,review,audit
from src.models import retest as retest_models
from src.models.user import User
from src.models.audit import Audit
from src.models.retest import (RetestStudy,RetestSample,RetestClaim,RetestDraft,
    RetestDraftItem,RetestList,RetestListItem,RetestMeta)
from scripts.seed_demo import seed_retest as _seed_retest

Base.metadata.create_all(engine)

TABLES=(RetestClaim,RetestDraftItem,RetestDraft,RetestListItem,RetestList,
        RetestStudy,RetestSample,RetestMeta,Audit,User)

def reset():
    with Session() as db:
        for model in TABLES: db.execute(delete(model))
        db.commit()

def seed_retest():
    with Session() as db:
        _seed_retest(db)
        db.commit()
