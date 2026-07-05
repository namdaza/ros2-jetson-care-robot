#!/bin/bash

set -euo pipefail
PORT="${PORT:-5000}"
ROBOT_UI_DIR="/home/jetson/mopero/robot_ui"

echo "[start_ui] Bat dau UI..."
cd "${ROBOT_UI_DIR}"

set +u
source /opt/ros/foxy/setup.bash
set -u

# Stop old UI processes to avoid stale code and "Port 5000 is in use".
pkill -f "python3 /home/jetson/mopero/robot_ui/run_app.py" 2>/dev/null || true
pkill -f "python3 run_app.py" 2>/dev/null || true
pkill -f "run_app.py" 2>/dev/null || true
pkill -f "firefox.*http://localhost:${PORT}" 2>/dev/null || true
pkill -f "chromium.*http://localhost:${PORT}" 2>/dev/null || true
pkill -f "google-chrome.*http://localhost:${PORT}" 2>/dev/null || true
sleep 1

PORT="${PORT}" /usr/bin/python3 "${ROBOT_UI_DIR}/run_app.py" &

sleep 6

export DISPLAY=:0
export XAUTHORITY=/home/jetson/.Xauthority
export XDG_RUNTIME_DIR=/run/user/1000
export MOZ_DISABLE_GFX_SANITY_TEST=1
export MOZ_WEBRENDER=0
export MOZ_X11_EGL=0
export LIBGL_ALWAYS_SOFTWARE=1

USB_MIC_SOURCE="alsa_input.usb-Jieli_Technology_USB_Composite_Device-02.mono-fallback"
if pactl list short sources | awk '{print $2}' | grep -qx "${USB_MIC_SOURCE}"; then
    echo "[start_ui] Set default microphone: ${USB_MIC_SOURCE}"
    pactl set-default-source "${USB_MIC_SOURCE}"
else
    FALLBACK_USB_MIC="$(pactl list short sources | awk '/alsa_input\.usb/ {print $2; exit}')"
    if [ -n "${FALLBACK_USB_MIC}" ]; then
        echo "[start_ui] Set fallback USB microphone: ${FALLBACK_USB_MIC}"
        pactl set-default-source "${FALLBACK_USB_MIC}"
    else
        echo "[start_ui] Khong tim thay USB microphone, giu default source hien tai."
    fi
fi

HDMI_AUDIO_SINK="alsa_output.platform-70030000.hda.hdmi-stereo"
if pactl list short sinks | awk '{print $2}' | grep -qx "${HDMI_AUDIO_SINK}"; then
    echo "[start_ui] Set default speaker: ${HDMI_AUDIO_SINK}"
    pactl set-default-sink "${HDMI_AUDIO_SINK}"
else
    FALLBACK_HDMI_SINK="$(pactl list short sinks | awk 'tolower($2) ~ /hdmi/ {print $2; exit}')"
    if [ -n "${FALLBACK_HDMI_SINK}" ]; then
        echo "[start_ui] Set fallback HDMI speaker: ${FALLBACK_HDMI_SINK}"
        pactl set-default-sink "${FALLBACK_HDMI_SINK}"
    else
        echo "[start_ui] Khong tim thay HDMI speaker, giu default sink hien tai."
    fi
fi

FIREFOX_PROFILE="/home/jetson/.mozilla/robot_ui_firefox"
mkdir -p "${FIREFOX_PROFILE}"
cat > "${FIREFOX_PROFILE}/user.js" <<'EOF'
user_pref("media.navigator.permission.disabled", true);
user_pref("media.navigator.video.enabled", false);
user_pref("media.autoplay.default", 0);
user_pref("browser.shell.checkDefaultBrowser", false);
user_pref("browser.sessionstore.resume_from_crash", false);
EOF

if command -v chromium-browser >/dev/null 2>&1; then
    chromium-browser --kiosk --no-first-run --disable-session-crashed-bubble --autoplay-policy=no-user-gesture-required "http://localhost:${PORT}"
elif command -v chromium >/dev/null 2>&1; then
    chromium --kiosk --no-first-run --disable-session-crashed-bubble --autoplay-policy=no-user-gesture-required "http://localhost:${PORT}"
elif command -v google-chrome >/dev/null 2>&1; then
    google-chrome --kiosk --no-first-run --disable-session-crashed-bubble --autoplay-policy=no-user-gesture-required "http://localhost:${PORT}"
else
    echo "[start_ui] Khong tim thay Chromium/Chrome. Mo Firefox voi profile robot UI da allow microphone."
    firefox --kiosk --profile "${FIREFOX_PROFILE}" "http://localhost:${PORT}"
fi
