#!/usr/bin/env bash
# ==============================================================================
# K12 英语分级背词 + 初中数学每日三题 双科学习系统 - CentOS 一键部署脚本
# 适用系统: CentOS 7 / CentOS Stream 8 & 9 / Rocky Linux / AlmaLinux
# 默认部署目录: /data0/webroot/k12-study-h5 (可通过环境变量 APP_DIR 覆盖)
#
# 使用示例:
#   chmod +x deploy_centos.sh
#   sudo K12_ADMIN_REFERRAL_CODE=ADM999 SERVER_NAME=_ ./deploy_centos.sh
# ==============================================================================

set -euo pipefail

# ---------- 可通过环境变量覆盖的部署参数 ----------
APP_DIR="${APP_DIR:-/data0/webroot/k12-study-h5}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
WEB_PORT="${WEB_PORT:-80}"
SERVER_NAME="${SERVER_NAME:-_}"
K12_ADMIN_REFERRAL_CODE="${K12_ADMIN_REFERRAL_CODE:-ADM999}"
K12_ALLOW_AUTO_PROVISION="${K12_ALLOW_AUTO_PROVISION:-true}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

# 可选：大模型补全配置（留空则仅使用 Free Dictionary API 与本地题库）
LLM_API_BASE="${LLM_API_BASE:-}"
LLM_API_KEY="${LLM_API_KEY:-}"
LLM_MODEL="${LLM_MODEL:-gpt-4o-mini}"

# ---------- 日志工具 ----------
log()  { echo -e "\033[1;34m[INFO]\033[0m $*"; }
ok()   { echo -e "\033[1;32m[OK]\033[0m   $*"; }
warn() { echo -e "\033[1;33m[WARN]\033[0m $*"; }
err()  { echo -e "\033[1;31m[ERR]\033[0m  $*" >&2; exit 1; }

[[ "$(id -u)" -eq 0 ]] || err "请使用 root 或 sudo 运行此脚本"
[[ -d "${APP_DIR}/backend" && -d "${APP_DIR}/frontend" ]] || err "未在 ${APP_DIR} 找到 backend/ 和 frontend/ 目录，请先解压项目或设置 APP_DIR"

# ---------- 1. 检测包管理器并安装基础依赖 ----------
if command -v dnf >/dev/null 2>&1; then
  PKG="dnf"
elif command -v yum >/dev/null 2>&1; then
  PKG="yum"
else
  err "未检测到 dnf 或 yum，请确认当前系统为 CentOS/RHEL 系列"
fi

log "安装基础系统组件 (nginx, sqlite, curl, git)..."
if ! rpm -q epel-release >/dev/null 2>&1; then
  ${PKG} install -y epel-release || warn "epel-release 安装失败，尝试直接安装基础包"
fi
${PKG} install -y nginx sqlite curl git

# ---------- 2. 校验 Python 版本 (>= 3.10) ----------
if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  err "未找到 ${PYTHON_BIN}，请先安装 Python 3.10+ 或通过 PYTHON_BIN=/usr/local/bin/python3.11 指定路径"
fi

PY_VER="$("${PYTHON_BIN}" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
PY_OK="$("${PYTHON_BIN}" -c 'import sys; print(int(sys.version_info >= (3, 10)))')"
if [[ "${PY_OK}" -ne 1 ]]; then
  err "当前 ${PYTHON_BIN} 版本为 ${PY_VER}，需要 Python 3.10+（后端使用了 X | Y 类型注解）。请安装高版本后通过 PYTHON_BIN=... 重新运行。"
fi
ok "Python 版本校验通过: ${PYTHON_BIN} (${PY_VER})"

# ---------- 3. 校验/安装 Node.js (>= 18) ----------
install_node=0
if ! command -v node >/dev/null 2>&1; then
  install_node=1
else
  NODE_MAJOR="$(node -v | sed -E 's/^v([0-9]+).*/\1/')"
  if [[ "${NODE_MAJOR}" -lt 18 ]]; then
    warn "当前 Node.js 版本 v${NODE_MAJOR} 低于 18，将尝试升级至 Node.js 20 LTS"
    install_node=1
  fi
fi

if [[ "${install_node}" -eq 1 ]]; then
  log "通过 NodeSource 安装 Node.js 20 LTS..."
  curl -fsSL https://rpm.nodesource.com/setup_20.x | bash -
  ${PKG} install -y nodejs
fi
ok "Node.js 版本: $(node -v), npm 版本: $(npm -v)"

# ---------- 4. 部署后端虚拟环境与 SQLite WAL 数据库 ----------
log "创建后端 Python 虚拟环境并安装依赖..."
cd "${APP_DIR}/backend"
if [[ ! -d ".venv" ]]; then
  "${PYTHON_BIN}" -m venv .venv
fi
.venv/bin/pip install --upgrade pip -q
.venv/bin/pip install -r requirements.txt

log "初始化 SQLite WAL 数据库 (${APP_DIR}/database/k12_study.db)..."
K12_DB_PATH="${APP_DIR}/database/k12_study.db" \
K12_INIT_SQL_PATH="${APP_DIR}/database/init_k12_study.sql" \
.venv/bin/python -c "
from app import db
db.init_database()
with db.db_session() as conn:
    mode = conn.execute('PRAGMA journal_mode;').fetchone()[0]
    en = conn.execute('SELECT COUNT(*) FROM english_words').fetchone()[0]
    ma = conn.execute('SELECT COUNT(*) FROM math_questions').fetchone()[0]
    print(f'SQLite initialized: journal_mode={mode}, english_words={en}, math_questions={ma}')
"
ok "后端环境与数据库初始化完成"

# ---------- 5. 构建 Vue 3 前端静态包 ----------
log "安装前端依赖并构建生产静态包..."
cd "${APP_DIR}/frontend"
if [[ -f "package-lock.json" ]]; then
  npm ci
else
  npm install
fi
npm run build
[[ -f "${APP_DIR}/frontend/dist/index.html" ]] || err "前端构建失败，未生成 dist/index.html"
ok "前端构建完成: ${APP_DIR}/frontend/dist"

# ---------- 6. 写入环境变量文件 ----------
ENV_FILE="/etc/sysconfig/k12-study-h5"
cat > "${ENV_FILE}" <<EOF
K12_DB_PATH=${APP_DIR}/database/k12_study.db
K12_INIT_SQL_PATH=${APP_DIR}/database/init_k12_study.sql
K12_ADMIN_REFERRAL_CODE=${K12_ADMIN_REFERRAL_CODE}
K12_ALLOW_AUTO_PROVISION=${K12_ALLOW_AUTO_PROVISION}
# 生产环境由 systemd timer 负责每 6 小时增量更新，关闭 FastAPI 内置重复调度器
K12_ENABLE_SCHEDULER=false
LLM_API_BASE=${LLM_API_BASE}
LLM_API_KEY=${LLM_API_KEY}
LLM_MODEL=${LLM_MODEL}
EOF
chmod 600 "${ENV_FILE}"

# ---------- 7. 配置 systemd 后端服务与每 6 小时同步定时器 ----------
log "配置 systemd 服务 (k12-backend.service, k12-sync.service, k12-sync.timer)..."

cat > /etc/systemd/system/k12-backend.service <<EOF
[Unit]
Description=K12 Study H5 FastAPI Backend
After=network.target

[Service]
Type=simple
WorkingDirectory=${APP_DIR}/backend
EnvironmentFile=${ENV_FILE}
ExecStart=${APP_DIR}/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port ${BACKEND_PORT} --workers 1
Restart=always
RestartSec=3
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/k12-sync.service <<EOF
[Unit]
Description=K12 Study Content Incremental Sync (Every 6h)
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=${APP_DIR}/backend
EnvironmentFile=${ENV_FILE}
ExecStart=${APP_DIR}/backend/.venv/bin/python ${APP_DIR}/backend/scripts/sync_content.py --subject all --batch-size 12
StandardOutput=journal
StandardError=journal
EOF

cat > /etc/systemd/system/k12-sync.timer <<EOF
[Unit]
Description=Run K12 Study Content Incremental Sync every 6 hours

[Timer]
OnBootSec=5min
OnUnitActiveSec=6h
Persistent=true
Unit=k12-sync.service

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable --now k12-backend.service
systemctl enable --now k12-sync.timer
ok "后端服务与每 6 小时同步定时器已启动"

# ---------- 8. 配置 Nginx 反向代理与 H5 静态资源 ----------
log "配置 Nginx 站点 (/etc/nginx/conf.d/k12-study-h5.conf)..."
cat > /etc/nginx/conf.d/k12-study-h5.conf <<EOF
server {
    listen ${WEB_PORT};
    server_name ${SERVER_NAME};

    root ${APP_DIR}/frontend/dist;
    index index.html;

    # 前端 H5 静态资源
    location / {
        try_files \$uri \$uri/ /index.html;
    }

    # 反向代理 FastAPI 后端
    location /api/ {
        proxy_pass http://127.0.0.1:${BACKEND_PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 60s;
    }
}
EOF

# 确保 Nginx 可读取静态目录及上级路径
chmod o+rx "$(dirname "${APP_DIR}")" "${APP_DIR}" "${APP_DIR}/frontend" "${APP_DIR}/frontend/dist" || true

# 处理 SELinux（若开启 Enforcing）
if command -v getenforce >/dev/null 2>&1 && [[ "$(getenforce)" == "Enforcing" ]]; then
  log "检测到 SELinux Enforcing，放行 Nginx 网络代理与静态目录上下文..."
  setsebool -P httpd_can_network_connect 1 || true
  chcon -Rt httpd_sys_content_t "${APP_DIR}/frontend/dist" || true
fi

nginx -t
systemctl enable --now nginx
systemctl reload nginx
ok "Nginx 已重载并生效"

# ---------- 9. 放行 firewalld 防火墙端口 ----------
if systemctl is-active --quiet firewalld; then
  log "放行 firewalld 端口 ${WEB_PORT}/tcp..."
  firewall-cmd --permanent --add-port="${WEB_PORT}/tcp" >/dev/null
  firewall-cmd --reload >/dev/null
  ok "防火墙端口 ${WEB_PORT}/tcp 已放行"
fi

# ---------- 10. 健康检查 ----------
sleep 2
log "执行后端与 Nginx 代理健康检查..."
curl -fsS "http://127.0.0.1:${BACKEND_PORT}/api/health" && echo ""
curl -fsS "http://127.0.0.1:${WEB_PORT}/api/health" && echo ""

echo "=============================================================================="
ok "K12 双科学习系统部署完成！"
echo "  访问地址:        http://<服务器IP>:${WEB_PORT}"
echo "  测试学生推荐码:  K12001 / STU888"
echo "  隐藏管理推荐码:  ${K12_ADMIN_REFERRAL_CODE} (配置文件: ${ENV_FILE})"
echo "  后端日志查看:    journalctl -u k12-backend -f"
echo "  定时同步状态:    systemctl list-timers k12-sync.timer"
echo "=============================================================================="