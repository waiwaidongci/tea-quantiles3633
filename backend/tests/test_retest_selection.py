"""选样算法核对：候选重叠、拿满优先、编号定序、已领固定。"""
import unittest
from src.services.retest_selection import select

def st(id,code,quota,**limits): return {'id':id,'code':code,'quota':quota,'limits':limits}
def smp(id,number,batch='2026-11',**ind): return {'id':id,'batch':batch,'number':number,'indicators':ind}
def picked(result,claimed=False): return {(r['study_id'],r['number']) for r in result if r['claimed']==claimed}

class SelectionTest(unittest.TestCase):
    def test_overlap_shared_candidate_keeps_all_full(self):
        # 候选重叠：01 同时满足两项研究，02 只满足 S2；重叠样本须让给只能用它的一方以外的研究
        r=select([st(1,'S1',1,a=10),st(2,'S2',1,a=5)],
                 [smp(1,'01',a=12),smp(2,'02',a=6)],[])
        self.assertEqual(picked(r),{(1,'01'),(2,'02')})

    def test_full_count_beats_concentration(self):
        # S1 独占两份也只能算 1 个拿满；S2、S3 各拿一份可算 2 个拿满
        r=select([st(1,'S1',2,a=1),st(2,'S2',1,b=5),st(3,'S3',1,c=5)],
                 [smp(1,'01',a=9,b=9),smp(2,'02',a=9,c=9)],[])
        self.assertEqual(picked(r),{(2,'01'),(3,'02')})

    def test_tie_break_prefers_lower_codes(self):
        # 平局：编号小的研究先拿，编号小的茶样先配
        r=select([st(1,'S1',1,a=1),st(2,'S2',1,a=1)],[smp(1,'01',a=9)],[])
        self.assertEqual(picked(r),{(1,'01')})
        r=select([st(1,'S1',2,a=1)],[smp(1,'01',a=9),smp(2,'02',a=9),smp(3,'03',a=9)],[])
        self.assertEqual(picked(r),{(1,'01'),(1,'02')})

    def test_claimed_kept_and_counts_toward_quota(self):
        # 已领归属不变且计入名额：S2 已领 01 即足额不再新配；S1 只能从余池领 02
        claims=[{'study_id':2,'batch':'2026-11','number':'01'}]
        r=select([st(1,'S1',2,a=10),st(2,'S2',1,a=10)],
                 [smp(1,'01',a=20),smp(2,'02',a=15)],claims)
        self.assertEqual(picked(r,claimed=True),{(2,'01')})
        self.assertEqual(picked(r),{(1,'02')})

    def test_ineligible_samples_skipped(self):
        # 低于下限或缺指标的茶样不得入选
        r=select([st(1,'S1',1,a=10)],[smp(1,'01',a=5),smp(2,'02',b=3)],[])
        self.assertEqual(picked(r),set())

    def test_sample_used_once_per_list(self):
        r=select([st(1,'S1',1,a=1),st(2,'S2',1,a=1)],[smp(1,'01',a=9),smp(2,'02',a=9)],[])
        self.assertEqual(sorted(x['number'] for x in r),['01','02'])

    def test_deterministic(self):
        args=([st(1,'S1',2,a=10),st(2,'S2',2,a=5),st(3,'S3',1,b=3)],
              [smp(1,'01',a=20,b=1),smp(2,'02',a=15,b=5),smp(3,'03',a=12,b=0),smp(4,'04',a=3,b=9)],[])
        self.assertEqual(select(*args),select(*args))

if __name__=='__main__': unittest.main()
