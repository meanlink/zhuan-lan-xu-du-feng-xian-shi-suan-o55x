# 专栏续读风险试算

分类与阈值选择的真实业务分析小型项目。完整模拟客户、痛点、上下游、算法公式与一天工作剧本见 [BUSINESS.md](BUSINESS.md)。

## 模块与业务流程
供稿口径（版本化字段/单位/观察窗口声明）→ 数据接入（JSON/CSV、保留原值并按口径换算、窗口不符隔离、批次指纹）→ 参数化分析（异步 Python worker）→ 结果复核（指标、图形、明细、解释、批准）→ 定时分发（本地收件箱、CSV/JSON、SHA256）；另有批次换版、业务总览和审计轨迹。
三个贯穿全栈的实体：Dataset 数据批次、Job 分析任务、Report 分发计划；辅助 User、Audit、Delivery，以及 SupplySpec 供稿口径版本、Quarantine 隔离记录、ReversionPlan 换版案。

## 快速启动
```bash
cp .env.example .env
docker compose up -d --build --wait
docker compose exec -T backend python -m scripts.seed_demo
```
访问 http://localhost:18207；后端文档 http://localhost:19207/docs；数据库宿主端口 17707。
`SEED_DEMO=true` 自动幂等 seed；不覆盖用户修改。手动 seed 命令可重复执行。

## 演示账号与权限
|账号|密码|真实权限|
|---|---|---|
|admin@demo.local|Demo123!|接入、执行、批准、分发、暂停、读取与下载|
|analyst@demo.local|Demo123!|接入、执行、读取与下载；不能批准或安排分发|
|viewer@demo.local|Demo123!|只读与下载|

## 技术与本地开发
Python 3.12 / FastAPI / SQLAlchemy / NumPy / SciPy / scikit-learn；MySQL 8.0；Redis 7；Nginx；原生 HTML CSS JavaScript ES modules（用户指定）。后端所有校验、持久化和算法在服务端。无前端打包步骤。
后端：安装 backend/requirements.txt，设置 DATABASE_URL、REDIS_URL、JWT_SECRET、ARTIFACT_DIR 后在 backend/ 执行 `python -m migrations.initial`、`python -m scripts.seed_demo`、`uvicorn src.main:app`，另开 `python -m src.worker`。前端使用带 /api 反向代理的 Nginx，直接打开 index.html 不支持 API。

## 目录与工程约定
backend/src/{models,schemas,services,routes,controllers,middlewares,constants,config,utils}；backend/scripts/seed_demo.py；backend/migrations/initial.py。
frontend/src/{api,stores,types,components/common,hooks,pages,router,utils,constants}。
Role 枚举：admin/analyst/viewer；JobStatus：queued/running/completed/failed。后端 backend/src/constants/enums.py，前端 frontend/src/constants/enums.js；路由权限在 middlewares/auth.py；页面按相同角色控制操作入口。

## 供稿口径与批次换版
供稿方常把完成率写成小数或百分数、把七日窗口混入十四日样本。口径按族版本化，声明字段、标准单位与观察窗口；接入时保留供稿原值（raw_records）并按口径换算，换算依据随记录保存，窗口不符的记录隔离存因。修订口径生成新版本并废止旧版；之后可对已有现行批次立换版案：冻结原批次指纹与目标版本快照，worker 逐批生成替代批次（staging），全部通过分析输入校验才一次性切换新试验入口（原批次转 superseded、替代批次转 current），任一失败保留旧版。同一原批次的进行中换版案唯一（数据库锁，后到 409）；中断按条目进度恢复，重试不新增替代批次，发布以 (id, status, epoch) 条件更新为闸，旧执行晚回不发布。排队与已完成试验仍读取创建时选定的批次，旧结果不变。页面：口径与换版（维护口径、立案、看待换版/处理中/完成/失败）、数据接入（核对隔离原因与转换依据）。

## 环境变量与 Docker
COMPOSE_PROJECT_NAME=reader-risk；FRONTEND_PORT=18207；BACKEND_PORT=19207；DB_PORT=17707；DB_PASSWORD、JWT_SECRET 见 .env.example；SEED_DEMO 默认 true。共享命名产物卷供后端下载与 worker 写入，数据库/Redis 各持久卷。
恰好五服务均有健康检查。Redis 队列加 SQL 排队状态兜底；worker 按 next_run 生成本地收件箱文件。周期 60 秒至 30 天。分发结果为批准分析的固定快照；若需新数据重新计算并建立新计划。当前不连接邮件或企业聊天。
错误响应、请求编号、Redis 每 IP 每分钟 240 次限流、JWT 和数据库操作审计。演示密钥与密码仅供本机模拟；生产部署前配置独立密钥与账号。

## 数据与验收
所有数据为固定随机种子生成的模拟业务数据，不能作为实际生产决策证据。项目独立算法、输入边界及业务局限详见 BUSINESS.md。测试与截图统一存放 ../../test-artifacts/gb-1008/，源码不含日志/截图/测试报告。
清理本项目演示数据：`docker compose down -v --remove-orphans`（会删除本项目命名卷）。

## License
MIT，见 LICENSE。
