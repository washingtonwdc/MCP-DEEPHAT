#!/usr/bin/env bash
# ==============================================================================
# Script de Implantação Automatizada em 1-Clique na VPS Free Tier
# Aplicação: SmartTV Club Auto-Sync & Multi-Device IPTV Manager
# Porta: 5050 (TCP) | Senha padrão do Administrador: 0808
# Compatibilidade: Ubuntu 22.04/24.04 LTS e Debian 11/12
# ==============================================================================

set -e

echo "==========================================================="
echo "🚀 INICIANDO INSTALAÇÃO DO SMARTTV AUTO-SYNC NA VPS"
echo "==========================================================="

# 1. Verifica se está executando como root
if [ "$EUID" -ne 0 ]; then
  echo "[ERRO] Execute este script como root ou com sudo."
  exit 1
fi

APP_DIR="/opt/smarttv-sync"
REPO_URL="https://github.com/washingtonwdc/MCP-DEEPHAT.git"

# 2. Atualização dos repositórios e instalação de pacotes essenciais
echo "[1/6] Atualizando pacotes do sistema e instalando dependências..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y python3 python3-pip python3-venv git curl ufw iptables-persistent libglib2.0-0 libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2

# Adiciona 2 GB de SWAP se necessário (essencial para Playwright Chromium em VPS de 1GB RAM)
SWAP_TOTAL=$(free -m | awk '/^Swap:/ {print $2}')
if [ "$SWAP_TOTAL" -lt 1024 ]; then
  echo "  Criando arquivo de SWAP de 2 GB para estabilidade operacional..."
  fallocate -l 2G /swapfile 2>/dev/null || dd if=/dev/zero of=/swapfile bs=1M count=2048
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile 2>/dev/null || true
  if ! grep -q "/swapfile" /etc/fstab; then
    echo "/swapfile none swap sw 0 0" >> /etc/fstab
  fi
fi

# 3. Download / Clonagem do Repositório Oficial
echo "[2/6] Baixando a aplicação para ${APP_DIR}..."
if [ -d "$APP_DIR" ]; then
  echo "  Diretório já existe. Atualizando código via git pull..."
  cd "$APP_DIR"
  git fetch origin master
  git reset --hard origin/master
else
  git clone "$REPO_URL" "$APP_DIR"
  cd "$APP_DIR"
fi

# 4. Criação do Ambiente Virtual Python e Instalação dos Pacotes
echo "[3/6] Configurando ambiente virtual Python (venv)..."
if [ ! -d "${APP_DIR}/.venv" ]; then
  python3 -m venv "${APP_DIR}/.venv"
fi

echo "  Instalando bibliotecas do requirements.txt..."
"${APP_DIR}/.venv/bin/pip" install --upgrade pip
"${APP_DIR}/.venv/bin/pip" install -r "${APP_DIR}/requirements.txt"

# 5. Instalação do Navegador Playwright Headless Chromium e bibliotecas gráficas
echo "[4/6] Instalando Chromium headless e bibliotecas do Playwright..."
"${APP_DIR}/.venv/bin/playwright" install chromium
"${APP_DIR}/.venv/bin/playwright" install-deps chromium || true

# 6. Criação do Serviço Systemd Permanente (Inicialização no Boot)
echo "[5/6] Configurando serviço permanente systemd (smarttv.service)..."
cat << 'EOF' > /etc/systemd/system/smarttv.service
[Unit]
Description=SmartTV Club Multi-Device Auto-Sync Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/smarttv-sync
Environment=PYTHONUNBUFFERED=1
ExecStart=/opt/smarttv-sync/.venv/bin/python smarttv_web.py --host 0.0.0.0 --port 5050
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable smarttv.service
systemctl restart smarttv.service

# 7. Liberação da Porta 5050 no Firewall do Sistema (UFW e iptables do Oracle Cloud)
echo "[6/6] Configurando firewall e abrindo a porta 5050..."
if command -v ufw >/dev/null 2>&1; then
  ufw allow 22/tcp || true
  ufw allow 5050/tcp || true
  echo "y" | ufw enable || true
fi

# Regra direta no iptables (essencial para imagens oficiais da Oracle Cloud Ubuntu)
iptables -I INPUT 1 -p tcp --dport 5050 -j ACCEPT || true
if command -v netfilter-persistent >/dev/null 2>&1; then
  netfilter-persistent save || true
fi

# Descobre o IP Público da VPS
IP_PUBLICO=$(curl -s -4 https://ifconfig.me || curl -s -4 https://api.ipify.org || echo "IP_DA_SUA_VPS")

echo ""
echo "==========================================================="
echo "✅ INSTALAÇÃO CONCLUÍDA COM SUCESSO!"
echo "==========================================================="
echo "📡 Painel Web Operacional em: http://${IP_PUBLICO}:5050"
echo "🔑 Senha de Administrador:    0808"
echo "📺 Agendamento Diário:       Ativo às 00:00 (Brasília)"
echo ""
echo "Comandos úteis:"
echo " - Ver status:    systemctl status smarttv.service"
echo " - Ver logs:      journalctl -u smarttv.service -f"
echo " - Reiniciar:     systemctl restart smarttv.service"
echo "==========================================================="
