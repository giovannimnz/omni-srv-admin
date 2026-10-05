#!/bin/bash
# omni::antigravity-hub-install — Instala/atualiza o Antigravity Hub (tar.gz) nos hosts da frota
# Risk: medium (instala binarios como root, cria symlink no PATH)
# Version: 1.0.0
# Nota: roda como root via Landscape
set -euo pipefail

# ─── Configurações ────────────────────────────────────────────────────────────
VERSION="2.19.1-6046815158665216"
ARCH="$(uname -m)"
TARBALL_URL_ARM64="https://storage.googleapis.com/antigravity-public/antigravity-hub/${VERSION}/linux-arm/Antigravity.tar.gz"
TARBALL_URL_X64="https://storage.googleapis.com/antigravity-public/antigravity-hub/${VERSION}/linux-x64/Antigravity.tar.gz"
INSTALL_BASE="/opt/antigravity-hub"
INSTALL_DIR="${INSTALL_BASE}/${VERSION}"
SYMLINK="/usr/local/bin/antigravity"
DESKTOP_FILE="/usr/share/applications/antigravity-hub.desktop"
ICON_DIR="/usr/share/icons/hicolor/512x512/apps"
ICON_FILE="${ICON_DIR}/antigravity-hub.png"
TMP_DIR="$(mktemp -d /tmp/agy-hub-install.XXXXXX)"

HOST="$(hostname)"
echo "=== HOST: ${HOST} — Antigravity Hub ${VERSION} ==="
echo "Arch: ${ARCH} | Timestamp: $(date '+%Y-%m-%d %H:%M:%S %Z')"

# ─── Seleciona URL por arquitetura ────────────────────────────────────────────
case "${ARCH}" in
  aarch64|arm64) TARBALL_URL="${TARBALL_URL_ARM64}"; EXTRACT_DIR="Antigravity-arm64" ;;
  x86_64)        TARBALL_URL="${TARBALL_URL_X64}"; EXTRACT_DIR="Antigravity" ;;
  *)
    echo "SKIP: arquitetura ${ARCH} nao suportada"
    exit 0
    ;;
esac

# ─── Verifica se já está instalado na versão correta ─────────────────────────
CURRENT_VER=""
if [ -f "${INSTALL_DIR}/.version" ]; then
  CURRENT_VER="$(cat "${INSTALL_DIR}/.version")"
fi

if [ "${CURRENT_VER}" = "${VERSION}" ] && [ -f "${INSTALL_DIR}/antigravity" ] && [ -L "${SYMLINK}" ]; then
  echo "INFO: Versao ${VERSION} ja instalada em ${INSTALL_DIR}. Nada a fazer."
  echo "antigravity -> $(readlink ${SYMLINK})"
  exit 0
fi

echo "Instalando versao ${VERSION}..."

# ─── Download ─────────────────────────────────────────────────────────────────
TARBALL="${TMP_DIR}/Antigravity.tar.gz"
echo "Download: ${TARBALL_URL}"
curl -fsSL --retry 3 --retry-delay 5 \
  -o "${TARBALL}" \
  "${TARBALL_URL}"
echo "Download concluido: $(du -sh "${TARBALL}" | cut -f1)"

# ─── Extração e instalação ────────────────────────────────────────────────────
echo "Extraindo..."
tar -xzf "${TARBALL}" -C "${TMP_DIR}/"

mkdir -p "${INSTALL_DIR}"
cp -r "${TMP_DIR}/${EXTRACT_DIR}/." "${INSTALL_DIR}/"

# Permissões
chown -R root:root "${INSTALL_DIR}"
chmod -R a+rX "${INSTALL_DIR}"
chmod +x "${INSTALL_DIR}/antigravity"
[ -f "${INSTALL_DIR}/chrome_crashpad_handler" ] && chmod +x "${INSTALL_DIR}/chrome_crashpad_handler"
# chrome-sandbox precisa SUID root (Chromium sandbox)
if [ -f "${INSTALL_DIR}/chrome-sandbox" ]; then
  chown root:root "${INSTALL_DIR}/chrome-sandbox"
  chmod 4755 "${INSTALL_DIR}/chrome-sandbox"
fi

# ─── Symlink no PATH ──────────────────────────────────────────────────────────
ln -sfn "${INSTALL_DIR}/antigravity" "${SYMLINK}"
echo "Symlink: ${SYMLINK} -> ${INSTALL_DIR}/antigravity"

# ─── Marcadores de versão ─────────────────────────────────────────────────────
echo "${VERSION}" > "${INSTALL_DIR}/.version"
date -u '+%Y-%m-%dT%H:%M:%SZ' > "${INSTALL_DIR}/.installed-at"
echo "${TARBALL_URL}" > "${INSTALL_DIR}/.source-url"
echo "${ARCH}" > "${INSTALL_DIR}/.arch"

# ─── Ícone ────────────────────────────────────────────────────────────────────
mkdir -p "${ICON_DIR}"
python3 - "${INSTALL_DIR}/resources/app.asar" "${ICON_FILE}" << 'PYEOF'
import struct, json, sys

asar_path, out_path = sys.argv[1], sys.argv[2]
try:
    with open(asar_path, "rb") as f:
        f.read(4)
        struct.unpack("<I", f.read(4))[0]
        f.read(4)
        header_data_size = struct.unpack("<I", f.read(4))[0]
        header_json = f.read(header_data_size).decode("utf-8", errors="ignore")
        header_offset = (8 + 4 + 4 + header_data_size + 3) & ~3
        header = json.loads(header_json)
        icon = header.get("files", {}).get("icon.png")
        if not icon:
            print("icon.png nao encontrado no asar")
            sys.exit(0)
        offset, size = int(icon["offset"]), int(icon["size"])
        f.seek(header_offset + offset)
        data = f.read(size)
    with open(out_path, "wb") as out:
        out.write(data)
    print(f"Icone extraido: {size} bytes")
except Exception as e:
    print(f"Aviso: falha ao extrair icone: {e}")
PYEOF

# Fallback de ícone
if [ ! -f "${ICON_FILE}" ]; then
  if [ -f /usr/share/pixmaps/antigravity.png ]; then
    cp /usr/share/pixmaps/antigravity.png "${ICON_FILE}"
    echo "Fallback: copiado de /usr/share/pixmaps/antigravity.png"
  fi
fi

gtk-update-icon-cache "${ICON_DIR}/../.." 2>/dev/null || true

# ─── .desktop file ────────────────────────────────────────────────────────────
cat > "${DESKTOP_FILE}" << DESKTOP
[Desktop Entry]
Name=Antigravity 2.0
Comment=Antigravity Hub — AI-powered development environment
GenericName=Development Tool
Exec=/usr/local/bin/antigravity --no-sandbox %U
Icon=antigravity-hub
Type=Application
StartupNotify=true
StartupWMClass=Antigravity
Categories=Development;IDE;
MimeType=x-scheme-handler/antigravity-hub;
Keywords=antigravity;ai;coding;ide;hub;
Version=1.0
DESKTOP

update-desktop-database /usr/share/applications/ 2>/dev/null || true
echo ".desktop criado: ${DESKTOP_FILE}"

# Propaga para diretório local de usuários (XRDP / desktop menus)
for user_home in /home/*; do
  if [ -d "${user_home}" ]; then
    user_apps="${user_home}/.local/share/applications"
    mkdir -p "${user_apps}"
    cp "${DESKTOP_FILE}" "${user_apps}/"
    chown -R "$(basename "${user_home}"):" "${user_apps}/antigravity-hub.desktop" 2>/dev/null || true
  fi
done

# ─── Limpeza ──────────────────────────────────────────────────────────────────
rm -rf "${TMP_DIR}"

# ─── Remove versoes antigas (mantém só a atual) ───────────────────────────────
for old_dir in "${INSTALL_BASE}"/*/; do
  old_ver="$(basename "${old_dir}")"
  if [ "${old_ver}" != "${VERSION}" ] && [ -d "${old_dir}" ]; then
    echo "Removendo versao antiga: ${old_ver}"
    rm -rf "${old_dir}"
  fi
done

# ─── Relatório final ──────────────────────────────────────────────────────────
echo ""
echo "=== INSTALAÇÃO CONCLUÍDA ==="
echo "Versao:   ${VERSION}"
echo "Dir:      ${INSTALL_DIR}"
echo "Binario:  ${SYMLINK} -> $(readlink ${SYMLINK})"
echo "Desktop:  ${DESKTOP_FILE}"
echo "Icone:    ${ICON_FILE} ($([ -f "${ICON_FILE}" ] && echo "OK" || echo "AUSENTE"))"
echo "which:    $(which antigravity 2>/dev/null || echo 'nao no PATH do shell root')"
