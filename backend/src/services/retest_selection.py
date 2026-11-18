"""当日复测单选样：候选重叠时按业务规则定夺。

目标按字典序：
1. 拿满名额的研究尽可能多；
2. 入选茶样总数尽可能多；
3. 平局按研究编号、茶样批号/编号定序（小号优先，结果确定）。

三级目标折算为整数权重后用 0-1 整数规划（SciPy/HiGHS）精确求解：
- x_ij=1 表示茶样 j 分给研究 i，y_i=1 表示研究 i 拿满；
- 约束：研究 i 入选不超过剩余名额，y_i=1 当且仅当达到剩余名额，同批同编号至多入选一次；
- 权重：拿满奖励 F 大于全部入选奖励之和，入选奖励 U 大于全部编号次序权重之和，
  故求解器严格按字典序优化，次序权重只在平局时定序。
"""
import numpy as np
from scipy.optimize import milp,LinearConstraint,Bounds
from scipy.sparse import lil_matrix


def _eligible(indicators, limits):
    for key, floor in limits.items():
        value = indicators.get(key)
        if value is None or value < floor:
            return False
    return True


def select(studies, samples, claims):
    """studies: 已复核研究 [{id, code, quota, limits}]；
    samples: 冻结茶样 [{id, batch, number, indicators}]；
    claims: 当日已领 [{study_id, batch, number}]，归属固定且计入名额。
    返回 [{study_id, batch, number, claimed}]，已领条目原样保留。"""
    result = [dict(c, claimed=True) for c in claims]
    claimed_keys = {(c['batch'], c['number']) for c in claims}
    claimed_count = {}
    for c in claims:
        claimed_count[c['study_id']] = claimed_count.get(c['study_id'], 0) + 1

    pool = [s for s in samples if (s['batch'], s['number']) not in claimed_keys]
    active = [st for st in studies if st['quota'] - claimed_count.get(st['id'], 0) > 0]
    demand = {st['id']: st['quota'] - claimed_count.get(st['id'], 0) for st in active}
    pairs = [(i, j) for i, st in enumerate(active) for j, s in enumerate(pool) if _eligible(s['indicators'], st['limits'])]
    if not active or not pairs:
        return result

    s_rank = {i: r + 1 for r, i in enumerate(sorted(range(len(active)), key=lambda i: (active[i]['code'], active[i]['id'])))}
    p_rank = {j: r + 1 for r, j in enumerate(sorted(range(len(pool)), key=lambda j: (pool[j]['batch'], pool[j]['number'], pool[j]['id'])))}
    weight = {(i, j): s_rank[i] * (len(pool) + 1) + p_rank[j] for i, j in pairs}
    unit = sum(weight.values()) + 1          # 超过全部次序权重之和：第二级目标
    full = (len(pool) + 1) * unit            # 超过全部入选奖励之和：第一级目标

    n_x, n_y = len(pairs), len(active)
    rows = 2 * n_y + len(pool)
    a = lil_matrix((rows, n_x + n_y))
    c = np.zeros(n_x + n_y)
    ub = np.zeros(rows)
    for e, (i, j) in enumerate(pairs):
        c[e] = weight[(i, j)] - unit
        a[i, e] = 1                      # 研究名额上限
        a[n_y + i, e] = -1               # 拿满约束：d_i*y_i <= 入选数
        a[2 * n_y + j, e] = 1            # 同批同编号至多一次
    for i, st in enumerate(active):
        d = demand[st['id']]
        ub[i] = d
        a[n_y + i, n_x + i] = d
        c[n_x + i] = -full
    for j in range(len(pool)):
        ub[2 * n_y + j] = 1

    res = milp(c, integrality=np.ones(n_x + n_y), bounds=Bounds(0, 1),
               constraints=LinearConstraint(a.tocsr(), -np.inf, ub))
    if not res.success:
        raise ValueError('选样求解失败：' + str(res.message))
    for e, (i, j) in enumerate(pairs):
        if res.x[e] > 0.5:
            sample = pool[j]
            result.append({'study_id': active[i]['id'], 'batch': sample['batch'], 'number': sample['number'], 'claimed': False})
    return result
