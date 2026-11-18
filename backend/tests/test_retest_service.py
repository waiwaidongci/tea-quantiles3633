"""复测单业务流核对：编单/发布/领样/名额调整/欠额，含领样撞上重排与并发领样。"""
import unittest
from types import SimpleNamespace
from fastapi import HTTPException
from tests import base
from src.services import retest

USER=SimpleNamespace(email='tester@demo.local')
DAY='2026-11-18'
DAY2='2026-11-19'

class ServiceTest(unittest.TestCase):
    def setUp(self):
        base.reset(); base.seed_retest()

    def state(self,day=DAY):
        with base.Session() as db: return retest.state(db,day)
    def compile(self,day=DAY):
        with base.Session() as db: return retest.compile_draft(db,USER,day)
    def publish(self,day=DAY):
        with base.Session() as db: return retest.publish(db,USER,day)
    def claim(self,item,day=DAY,study_id=None):
        data=SimpleNamespace(study_id=study_id or item['study_id'],batch=item['batch'],number=item['number'])
        with base.Session() as db: return retest.claim(db,data,USER,day)
    def set_quota(self,code,quota):
        sid=next(x for x in self.state()['studies'] if x['code']==code)['id']
        with base.Session() as db: return retest.set_quota(db,sid,SimpleNamespace(quota=quota),USER)

    def test_compile_publish_flow_and_shortfall(self):
        s=self.compile()
        draft=s['draft']
        self.assertIsNotNone(draft)
        self.assertFalse(draft['stale'])
        # 候选重叠：02 号样三项研究都够格，但同批同编号在单里只出现一次
        keys=[(i['batch'],i['number']) for i in draft['items']]
        self.assertEqual(len(keys),len(set(keys)))
        self.assertEqual(len(draft['items']),5)  # 名额 2+2+1，候选足够，全部拿满
        # 发布前欠额=名额；发布后归零
        self.assertEqual({x['code']:x['shortfall'] for x in s['studies']},{'RT-01':2,'RT-02':2,'RT-03':1})
        s=self.publish()
        self.assertEqual(s['effective']['version'],1)
        self.assertEqual({x['code']:x['shortfall'] for x in s['studies']},{'RT-01':0,'RT-02':0,'RT-03':0})
        # 整单一次性切换：生效单与发布前草稿完全一致
        self.assertEqual({(i['batch'],i['number'],i['code']) for i in s['effective']['items']},
                         {(i['batch'],i['number'],i['code']) for i in draft['items']})
        # 编单确定性：同样输入重编结果一致
        again=self.compile()
        self.assertEqual({(i['batch'],i['number'],i['code']) for i in again['draft']['items']},
                         {(i['batch'],i['number'],i['code']) for i in draft['items']})

    def test_claim_then_recompile_keeps_claim(self):
        # 领样撞上重排：已领归属不变，只重排未领茶样
        self.compile(); s=self.publish()
        item=next(i for i in s['effective']['items'] if i['code']=='RT-02')
        s=self.claim(item)
        self.assertEqual(len(s['claims']),1)
        self.set_quota('RT-03',2)  # 名额调整：总名额 6 > 合格茶样 5
        s=self.compile()
        claimed=[i for i in s['draft']['items'] if i['claimed']]
        self.assertEqual([(c['code'],c['batch'],c['number']) for c in claimed],
                         [('RT-02',item['batch'],item['number'])])
        keys=[(i['batch'],i['number']) for i in s['draft']['items']]
        self.assertEqual(len(keys),len(set(keys)))
        s=self.publish()
        self.assertEqual(s['effective']['version'],2)
        self.assertEqual(len(s['effective']['items']),5)  # 1 已领 + 4 新配
        claimed=[i for i in s['effective']['items'] if i['claimed']]
        self.assertEqual((claimed[0]['code'],claimed[0]['batch'],claimed[0]['number']),
                         ('RT-02',item['batch'],item['number']))
        # 欠额 = 名额 − 生效已配；总欠额 = 6 − 5 = 1
        for x in s['studies']: self.assertEqual(x['shortfall'],max(0,x['quota']-x['assigned']))
        self.assertEqual(sum(x['shortfall'] for x in s['studies']),1)
        sample=next(t for t in s['samples'] if (t['batch'],t['number'])==(item['batch'],item['number']))
        self.assertEqual((sample['status'],sample['holder']),('claimed','RT-02'))

    def test_stale_draft_cannot_publish_after_concurrent_claim(self):
        self.compile(); s=self.publish()
        item=s['effective']['items'][0]
        self.compile()                 # 新草稿编好
        self.claim(item)               # 期间发生并发领样
        with self.assertRaises(HTTPException) as ctx: self.publish()
        self.assertEqual(ctx.exception.status_code,409)
        self.assertTrue(self.state()['draft']['stale'])
        self.compile()                 # 重新编单后才能发布
        s=self.publish()
        self.assertEqual(s['effective']['version'],2)

    def test_claim_once_per_day(self):
        self.compile(); s=self.publish()
        item=s['effective']['items'][0]
        self.claim(item)
        with self.assertRaises(HTTPException) as ctx: self.claim(item)
        self.assertEqual(ctx.exception.status_code,409)
        other=next(x for x in s['studies'] if x['id']!=item['study_id'])
        with self.assertRaises(HTTPException) as ctx: self.claim(item,study_id=other['id'])
        self.assertEqual(ctx.exception.status_code,404)

    def test_claim_requires_effective_list(self):
        item={'study_id':1,'batch':'2026-11','number':'01'}
        with self.assertRaises(HTTPException) as ctx: self.claim(item)
        self.assertEqual(ctx.exception.status_code,409)  # 尚未发布生效单
        self.compile(); s=self.publish()
        rt01=next(x for x in s['studies'] if x['code']=='RT-01')
        with self.assertRaises(HTTPException) as ctx:
            self.claim({'study_id':rt01['id'],'batch':'2026-11','number':'05'})  # 05 不在生效单
        self.assertEqual(ctx.exception.status_code,404)

    def test_quota_change_stales_draft(self):
        self.compile()
        self.set_quota('RT-01',3)
        with self.assertRaises(HTTPException) as ctx: self.publish()
        self.assertEqual(ctx.exception.status_code,409)
        self.assertTrue(self.state()['draft']['stale'])

    def test_next_day_can_claim_same_sample(self):
        self.compile(); s=self.publish()
        item=s['effective']['items'][0]
        self.claim(item)
        self.assertEqual(len(self.state()['claims']),1)
        self.compile(day=DAY2); s2=self.publish(day=DAY2)  # 次日重编，结果与昨日一致（确定性）
        same=next(i for i in s2['effective']['items'] if (i['batch'],i['number'])==(item['batch'],item['number']))
        self.claim(same,day=DAY2)  # 唯一约束按日隔离，次日同批同编号可再领
        self.assertEqual(len(self.state(DAY2)['claims']),1)
        self.assertEqual(len(self.state()['claims']),1)

    def test_atomic_switch_replaces_whole_list(self):
        self.compile(); s=self.publish()
        self.assertEqual(len(s['effective']['items']),5)
        self.set_quota('RT-03',0)
        s=self.compile()
        draft_keys={(i['batch'],i['number'],i['code']) for i in s['draft']['items']}
        s=self.publish()
        self.assertEqual(s['effective']['version'],2)
        self.assertEqual(len(s['effective']['items']),4)  # RT-03 名额归零，整单只剩 2+2
        self.assertEqual({(i['batch'],i['number'],i['code']) for i in s['effective']['items']},draft_keys)
        rt03=next(x for x in s['studies'] if x['code']=='RT-03')
        self.assertEqual((rt03['assigned'],rt03['shortfall']),(0,0))

if __name__=='__main__': unittest.main()
