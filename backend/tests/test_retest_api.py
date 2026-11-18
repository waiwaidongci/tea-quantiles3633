"""复测单 API 冒烟：路由、鉴权、限流中间件下的完整编单-发布-领样链路。"""
import unittest
from tests import base
from sqlalchemy import select
from fastapi.testclient import TestClient
from src.main import app
from src.models.user import User
from src.utils.security import token,hash_password

class ApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cm=TestClient(app)
        cls.client=cls.cm.__enter__()
    @classmethod
    def tearDownClass(cls):
        cls.cm.__exit__(None,None,None)
    def setUp(self):
        base.reset(); base.seed_retest()
        with base.Session() as db:
            db.add(User(email='analyst@demo.local',role='analyst',password_hash=hash_password('x')))
            db.add(User(email='viewer@demo.local',role='viewer',password_hash=hash_password('x')))
            db.commit()
            self.analyst=token(db.scalar(select(User).where(User.email=='analyst@demo.local')))
            self.viewer=token(db.scalar(select(User).where(User.email=='viewer@demo.local')))
        self.h={'Authorization':'Bearer '+self.analyst}

    def test_full_flow_and_stale_guard(self):
        r=self.client.get('/retest/state',headers=self.h)
        self.assertEqual(r.status_code,200)
        self.assertEqual(len(r.json()['studies']),3)
        self.assertEqual(self.client.post('/retest/compile',headers=self.h).status_code,200)
        r=self.client.post('/retest/publish',headers=self.h)
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.json()['effective']['version'],1)
        item=r.json()['effective']['items'][0]
        body={'study_id':item['study_id'],'batch':item['batch'],'number':item['number']}
        # 编好草稿后发生并发领样 → 旧草稿不能发布
        self.assertEqual(self.client.post('/retest/compile',headers=self.h).status_code,200)
        self.assertEqual(self.client.post('/retest/claim',json=body,headers=self.h).status_code,200)
        self.assertEqual(self.client.post('/retest/publish',headers=self.h).status_code,409)
        # 重新编单后整单切换为第 2 版
        self.assertEqual(self.client.post('/retest/compile',headers=self.h).status_code,200)
        r=self.client.post('/retest/publish',headers=self.h)
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.json()['effective']['version'],2)
        # 同批同编号当日只能领用一次
        self.assertEqual(self.client.post('/retest/claim',json=body,headers=self.h).status_code,409)

    def test_auth_and_roles(self):
        self.assertEqual(self.client.get('/retest/state').status_code,401)
        vh={'Authorization':'Bearer '+self.viewer}
        self.assertEqual(self.client.get('/retest/state',headers=vh).status_code,200)
        self.assertEqual(self.client.post('/retest/compile',headers=vh).status_code,403)

    def test_quota_endpoint(self):
        s=self.client.get('/retest/state',headers=self.h).json()
        sid=s['studies'][0]['id']
        r=self.client.put(f'/retest/studies/{sid}/quota',json={'quota':3},headers=self.h)
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.json()['quota'],3)
        self.assertEqual(self.client.put(f'/retest/studies/{sid}/quota',json={'quota':-1},headers=self.h).status_code,422)

if __name__=='__main__': unittest.main()
