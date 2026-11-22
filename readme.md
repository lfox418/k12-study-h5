# K12 双科自主学习系统 — 生产环境打包与部署手册

## 一、 系统架构与目录规范

* **项目根目录**：`/data0/webroot/k12-study-h5`
* **数据库文件**：`/data0/webroot/k12-study-h5/database/k12_study.db`（SQLite 3，WAL 并发模式）
* **后端服务**：Python 3.12 + FastAPI + Uvicorn（监听本地 `127.0.0.1:8000`，由 `k12-backend.service` 托管）
* **定时更新与清理**：每 6 小时自动同步公开词库/题库并清理无效批次（由 `k12-sync.timer` 触发 `k12-sync.service`）
* **前端访问入口**：`https://你的域名/k12/`（静态资源由 Nginx 反向代理分发，后端 API 前缀 `/k12/api/`）

---

## 二、 首次全量部署步骤

### 1. 拉取代码并初始化 SQLite 数据库

```bash
# 克隆或进入项目目录
cd /data0/webroot/k12-study-h5

# 创建数据库与备份目录
mkdir -p database backups

# 若数据库尚未初始化，导入建表与基础预制题库 SQL
sqlite3 database/k12_study.db < database/init_k12_study.sql

# 验证表结构是否完整（应包含 11 张核心表）
sqlite3 database/k12_study.db ".tables"
```

### 2. 配置 Python 虚拟环境与后端依赖

```bash
cd /data0/webroot/k12-study-h5

# 创建虚拟环境并安装依赖
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r backend/requirements.txt
```

### 3. 配置前端环境变量并执行生产环境打包

由于系统部署在子路径 `/k12/` 下，打包前必须固定 API 前缀与静态资源路由基准路径：

```bash
cd /data0/webroot/k12-study-h5/frontend

# 1. 写入生产环境 API 路径前缀（对应 Nginx 的 /k12/api/ 代理）
cat > .env.production << 'EOF'
VITE_API_BASE=/k12/api
EOF

# 2. 检查 axios 实例若存在硬编码 '/api' 则替换为 '/k12/api'
sed -i "s|baseURL: '/api'|baseURL: '/k12/api'|g" src/api/*.js 2>/dev/null || true
sed -i 's|baseURL: "/api"|baseURL: "/k12/api"|g' src/api/*.js 2>/dev/null || true

# 3. 安装前端依赖并带 --base=/k12/ 参数编译打包
npm install
npm run build -- --base=/k12/
```

打包完成后，静态产物将输出至 `/data0/webroot/k12-study-h5/frontend/dist/`。

---

## 三、 Systemd 后台服务与 6 小时定时器配置

### 1. 配置后端 API 常驻服务 (`k12-backend.service`)

```bash
sudo tee /etc/systemd/system/k12-backend.service > /dev/null << 'EOF'
[Unit]
Description=K12 Study H5 FastAPI Backend
After=network.target

[Service]
Type=simple
User=donglin
Group=donglin
WorkingDirectory=/data0/webroot/k12-study-h5/backend
Environment="SQLITE_DB_PATH=/data0/webroot/k12-study-h5/database/k12_study.db"
ExecStart=/data0/webroot/k12-study-h5/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
```

> **说明**：SQLite 写操作在单进程 `--workers 1` + WAL 模式下并发最稳健，可避免多 Worker 争抢写锁。

### 2. 配置每 6 小时自动更新词库/题库与清理定时器

```bash
# 复制仓库预置的 service 与 timer 单元文件
sudo cp -f /data0/webroot/k12-study-h5/deploy/k12-sync.service /etc/systemd/system/
sudo cp -f /data0/webroot/k12-study-h5/deploy/k12-sync.timer /etc/systemd/system/

# 重载 systemd 并启动全部服务与定时器
sudo systemctl daemon-reload
sudo systemctl enable --now k12-backend.service
sudo systemctl enable --now k12-sync.timer
```

---

## 四、 Nginx 子路径反向代理配置

在站点配置文件（如 `/etc/nginx/conf/cdn.clhdsci.conf`）的 `server { ... }` 块中确认包含以下完整规则：

```nginx
    # 1. 后端 API 反向代理（将 /k12/api/ 转发至本地 FastAPI 8000 端口）
    location ^~ /k12/api/ {
        proxy_pass [http://127.0.0.1:8000/api/](http://127.0.0.1:8000/api/);
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
    }

    # 2. 前端 H5 静态资源与 Vue Router History 模式路由回退
    location ^~ /k12/ {
        alias /data0/webroot/k12-study-h5/frontend/dist/;
        index index.html;
        try_files $uri $uri/ @k12_spa;
    }

    location @k12_spa {
        root /data0/webroot/k12-study-h5/frontend/dist;
        rewrite ^ /index.html break;
    }

    # 3. 根路径自动补全斜杠重定向
    location = /k12 {
        return 301 /k12/;
    }
```

检测并重载 Nginx 配置：

```bash
sudo nginx -t && sudo systemctl reload nginx
```

---

## 五、 日常 Git 同步一键更新脚本 (`update_deploy.sh`)

后续每次在本地修改代码并推送到 Git 后，只需在服务器上运行以下一键更新脚本（自动完成**数据库备份 -> 拉取代码 -> 后端更新重启 -> 前端带 `/k12/` 前缀打包**）：

```bash
cat > /data0/webroot/k12-study-h5/update_deploy.sh << 'EOF'
#!/usr/bin/env bash
set -e

PROJECT_DIR="/data0/webroot/k12-study-h5"
cd "$PROJECT_DIR"

echo "=== [1/5] 备份 SQLite 数据库 ==="
mkdir -p backups
if [ -f "database/k12_study.db" ]; then
    cp -f database/k12_study.db "backups/k12_study_$(date +%Y%m%d_%H%M).db"
    # 仅保留最近 15 份备份，自动清理旧备份
    ls -tp backups/k12_study_*.db | grep -v '/$' | tail -n +16 | xargs -I {} rm -- {} 2>/dev/null || true
fi

echo "=== [2/5] 拉取最新 Git 代码 ==="
git pull origin main

echo "=== [3/5] 更新后端依赖并重启服务 ==="
.venv/bin/pip install -r backend/requirements.txt -q
sudo systemctl restart k12-backend.service

echo "=== [4/5] 同步定时器配置 ==="
if [ -f "deploy/k12-sync.service" ] && [ -f "deploy/k12-sync.timer" ]; then
    sudo cp -f deploy/k12-sync.service /etc/systemd/system/
    sudo cp -f deploy/k12-sync.timer /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl restart k12-sync.timer
fi

echo "=== [5/5] 重新打包 Vue 3 前端 (/k12/ 子路径) ==="
cd "$PROJECT_DIR/frontend"
echo "VITE_API_BASE=/k12/api" > .env.production
npm install --silent
npm run build -- --base=/k12/

echo "=== 部署完成！当前后端状态： ==="
sudo systemctl is-active k12-backend.service
EOF

chmod +x /data0/webroot/k12-study-h5/update_deploy.sh
```

以后每次同步代码只需执行：

```bash
/data0/webroot/k12-study-h5/update_deploy.sh
```

---

## 六、 常用运维与故障排查速查

| 检查项 | 执行命令 | 预期正常结果 |
| :--- | :--- | :--- |
| **查看后端运行日志** | `sudo journalctl -u k12-backend.service -n 50 --no-pager` | 显示 `SQLite WAL 数据库已就绪` 及 `200 OK` 访问日志 |
| **查看 6 小时定时任务状态** | `systemctl list-timers k12-sync.timer --no-pager` | 显示 `NEXT` 下次触发时间及 `LEFT` 剩余倒计时 |
| **手动立即触发一次同步/清理** | `sudo systemctl start k12-sync.service` | 立即拉取增量词库/题库并清理 10 分钟前无考核结果的无效批次 |
| **查看同步脚本执行日志** | `sudo journalctl -u k12-sync.service -n 50 --no-pager` | 显示各学段新增词数、新增数学题数及清理记录数 |
| **本地直连测试后端健康度** | `curl -s http://127.0.0.1:8000/api/health` | 返回 `{"status":"ok"}` 或正常健康状态 JSON |
