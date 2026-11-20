# K12 英语分级背词 + 初中数学每日三题 双科移动端 H5 学习系统

一套基于 **Vue 3 + FastAPI + SQLite 3 (WAL 模式)** 的低焦虑、高交互、架构高度复用的内部自用 K12 双科自主学习系统。

## 目录结构

```text
k12-study-h5/
├── database/
│   └── init_k12_study.sql          # SQLite WAL 初始化 + 9张核心表 + 英语4学段(48词) + 数学3年级(24题)
├── backend/
│   ├── requirements.txt            # FastAPI / Uvicorn / APScheduler / httpx / Pydantic
│   ├── app/
│   │   ├── config.py               # 全局计时、积分、时区与同步源配置
│   │   ├── db.py                   # SQLite WAL / synchronous=NORMAL / busy_timeout=5000 连接管理
│   │   ├── models.py               # Pydantic 请求/响应模型
│   │   ├── engine.py               # 全科目共享核心引擎（推荐码、30分钟硬计时、抽题、通关、积分、只读档案）
│   │   └── main.py                 # RESTful API + X-Referral-Code 鉴权 + 内置 APScheduler 每6小时触发器
│   ├── scripts/
│   │   └── sync_content.py         # 每6小时增量同步脚本（英语开源词库+Free Dictionary+可选LLM；数学哈希去重）
│   └── tests/
│       └── test_engine.py          # 核心业务规则端到端单元测试
├── deploy/
│   ├── k12-sync.service            # Linux systemd oneshot 服务
│   └── k12-sync.timer              # Linux systemd 每6小时定时器 (OnUnitActiveSec=6h)
└── frontend/
    ├── package.json                # Vue 3 + Vite + Vant 4 + Tailwind CSS + Pinia + Axios + confetti + KaTeX
    └── src/
        ├── api/client.js           # 自动注入 X-Referral-Code 与 401 强制回退推荐码关卡
        ├── stores/studyStore.js    # Pinia 全局档案、积分、批次与特效状态
        ├── utils/{sound,latex}.js  # Web Audio API 合成音效 + speechSynthesis 发音 + KaTeX 公式渲染
        ├── components/             # StealthTimerBar（前20分隐身倒计时）、ScoreEffectOverlay、MathText、WordDetailModal
        └── views/                  # ReferralGateView、HallView、EnglishStudyView、MathStudyView、ProfileView
```

## 快速启动指南

### 1. 启动后端（FastAPI + SQLite WAL）

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 启动后端服务（首次启动自动执行 database/init_k12_study.sql 并启用 WAL 与内置 6h 同步调度器）
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

> 预制测试推荐码：`K12001`、`K12002`、`STU888`、`VIP666`（默认开启 `K12_ALLOW_AUTO_PROVISION=true`，输入任意 6 位字母/数字推荐码均可自动建档；若需严格白名单模式，请设置环境变量 `K12_ALLOW_AUTO_PROVISION=false`）。

### 2. 启动前端（Vue 3 + Vite）

```bash
cd frontend
npm install
npm run dev
```

浏览器打开 `http://localhost:5173`（或手机同局域网访问）即可体验。Vite 已内置 `/api` 代理至 `http://127.0.0.1:8000`。

### 3. 配置 Linux systemd 每 6 小时独立增量更新（可选，与内置 APScheduler 二选一）

若使用 `systemd timer` 独立运行增量脚本，建议在 FastAPI 环境变量中设置 `K12_ENABLE_SCHEDULER=false` 避免重复触发：

```bash
sudo cp deploy/k12-sync.service deploy/k12-sync.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now k12-sync.timer
systemctl list-timers k12-sync.timer
```

手动执行一次增量同步测试：

```bash
python3 backend/scripts/sync_content.py --subject all --batch-size 8
```

## 核心 API 列表

| 方法与路径 | 说明 | 鉴权要求 |
| :--- | :--- | :--- |
| `GET /api/health` | 健康检查、WAL 状态与题库总量 | 公开 |
| `POST /api/auth/verify-code` | 6 位推荐码准入校验/建档 | 公开 |
| `GET /api/user/profile` | 获取当前推荐码档案、积分与今日通关状态 | `X-Referral-Code` |
| `PUT /api/user/phone` | 免验证码直绑 11 位中国大陆手机号 | `X-Referral-Code` |
| `POST /api/sessions/start` | 统一开启英语（10词）或数学（3题）批次，写入 30 分钟硬截止时间 | `X-Referral-Code` |
| `POST /api/sessions/{id}/submit` | 统一校验提交、即时算分、全对通关晋升与每日 `+5` 分奖励 | `X-Referral-Code` |
| `POST /api/sessions/{id}/check-expiry` | 超时校验与作废落库 | `X-Referral-Code` |
| `GET /api/archive/english` | 英语历史批次（含耗时、首错标红）与一/二/三级词库只读清单 | `X-Referral-Code` |
| `GET /api/archive/math` | 数学历史批次与错题本（含 LaTeX 分步解析，严格只读） | `X-Referral-Code` |
| `GET /api/sync/logs` | 查看最近 10 次每 6 小时增量同步日志 | `X-Referral-Code` |
