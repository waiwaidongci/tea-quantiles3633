import os
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
class Base(DeclarativeBase):
    pass
_url=os.environ['DATABASE_URL']
# sqlite 仅用于本地开发与测试；生产走 PostgreSQL。
engine = create_engine(_url, pool_pre_ping=True, connect_args={'check_same_thread':False} if _url.startswith('sqlite') else {})
Session = sessionmaker(bind=engine, expire_on_commit=False)
def get_db():
    with Session() as db:
        yield db
