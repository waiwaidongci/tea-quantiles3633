# 复测单模块验证记录（2026-11-18）

## 环境
- Python 3.11 venv，安装 requirements 中本模块所需子集：fastapi 0.115.6、uvicorn、SQLAlchemy 2.0.36、redis 5.2.1、PyJWT 2.10.1、numpy 2.2.1、scipy 1.15.1，另加 httpx、fakeredis（仅测试）。
- 测试库：sqlite（`DATABASE_URL=sqlite:///…`）；Redis 以 fakeredis 垫片替代；完整运行仍以 docker compose（PostgreSQL16 + Redis7）为准。

## 自动化测试：`cd backend && python -m unittest tests.test_retest_selection tests.test_retest_service tests.test_retest_api`
结果：**18 项全部通过（OK，约 1s）**。

- 选样算法（7 项）：候选重叠共享样本让位使各方拿满；拿满数优先于集中堆叠；平局按研究/茶样编号定序；已领归属固定且计入名额；低于下限/缺指标样本剔除；同批同编号单内唯一；同输入结果确定。
- 业务流（8 项）：编单→发布→欠额归零；**领样撞上重排**（领 RT-02 一份后把 RT-03 名额调到 2，重编时已领条目原样保留、其余重排、同批同编号不重复、发布后欠额=名额−已配、总欠额=6−5=1）；**并发领样后旧草稿发布返回 409**、重编后可发布；同批同编号当日只能领一次（重复 409、冒用他研究 404）；未发布不能领（409）、非生效单茶样不能领（404）；名额调整使旧草稿过期；次日同批同编号可再领（约束按日隔离）；整单一次性切换（RT-03 名额归零后新版整单 4 条，与草稿完全一致）。
- API 冒烟（3 项）：未登录 401、viewer 只读 403；登录→编单→发布→领样→过期 409→重编→第 2 版；名额接口合法/非法值。

## 实时 HTTP 冒烟（uvicorn:19311，sqlite + fakeredis 垫片，SEED_DEMO=true）
- 登录 admin → 编单：RT-01←{01,04}、RT-02←{03,06}、RT-03←{02}（02 号样三项研究均够格，只出现一次）→ 发布第 1 版，欠额全 0。
- 领 RT-02 的 2026-11/03 → 旧草稿发布 **HTTP 409**。
- RT-03 名额调 2 → 重编：03 号样仍归 RT-02（已领），其余重排 → 发布第 2 版，RT-03 欠 1（总名额 6 > 合格茶样 5）。
- 重复领用同一茶样 **HTTP 409**。

## 其他核对
- `python -m scripts.seed_demo`（sqlite）：users 3、studies 3、observations 360、retest_studies 3、retest_samples 6，自然键幂等不覆盖。
- 前端 `node --input-type=module --check`：pages/retest.js、api/retest.js、router/index.js、main.js 语法通过。

## 已知边界
- 选样为 0-1 整数规划精确求解（SciPy/HiGHS），当日规模（研究数十、茶样数千）可秒解；平局权重之外仍并列时由求解器确定性返回。
- `src/config/database.py` 仅当 `DATABASE_URL` 为 sqlite 时附加 `check_same_thread=False`（本地/测试），生产 PostgreSQL 不受影响。
- 本地无 Redis/PostgreSQL 时以 fakeredis/sqlite 验证；docker compose 仍是完整运行方式。
