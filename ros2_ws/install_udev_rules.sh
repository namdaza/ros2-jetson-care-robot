#!/bin/bash

# =========================================================================
# Script tự động tạo udev rules cho Lidar, Arduino Motor, Arduino Sonar và Camera
# =========================================================================

if [ "$EUID" -ne 0 ]
  then echo "❌ Vui lòng chạy script với quyền sudo: sudo ./install_udev_rules.sh"
  exit
fi

RULES_FILE="/etc/udev/rules.d/99-robot-usb.rules"
echo "Bắt đầu tạo file rules: $RULES_FILE"
echo "" > $RULES_FILE

function bind_device() {
    local DEVICENAME=$1
    local SYMLINK_NAME=$2
    
    read -p "🔌 RÚT TẤT CẢ cáp USB ra để chuẩn bị. Bấm [Enter] để tiếp tục..."
    
    # Lưu danh sách thiết bị hiện tại
    OLD_DEVS=$(ls /dev/ttyUSB* /dev/ttyACM* 2>/dev/null)
    
    read -p "🔌 BÂY GIỜ hãy cẮM cáp của [$DEVICENAME] vào máy. Bấm [Enter] khi đã cắm xong..."
    sleep 2 # Chờ hệ điều hành nhận thiết bị
    
    # Tìm thiết bị mới
    NEW_DEVS=$(ls /dev/ttyUSB* /dev/ttyACM* 2>/dev/null)
    
    TARGET_DEV=""
    for dev in $NEW_DEVS; do
        if [[ ! "$OLD_DEVS" == *"$dev"* ]]; then
            TARGET_DEV=$dev
            break
        fi
    done
    
    if [ -z "$TARGET_DEV" ]; then
        echo "❌ Lỗi: Không nhận diện được thiết bị mới nào được cắm vào! Hãy thử lại quá trình."
        exit 1
    fi
    
    echo "✅ Đã tìm thấy [$DEVICENAME] tại cổng: $TARGET_DEV"
    
    # Lấy thông tin Vendor và Product ID
    ID_VENDOR=$(udevadm info -a -n $TARGET_DEV | grep '{idVendor}' | head -n 1 | awk -F'==' '{print $2}' | tr -d '"')
    ID_PRODUCT=$(udevadm info -a -n $TARGET_DEV | grep '{idProduct}' | head -n 1 | awk -F'==' '{print $2}' | tr -d '"')
    SERIAL_NUM=$(udevadm info -a -n $TARGET_DEV | grep '{serial}' | head -n 1 | awk -F'==' '{print $2}' | tr -d '"')
    
    # CH340 thường không có Serial duy nhất. Nếu cần dùng cổng vật lý:
    # Ở đây dùng Vendor và Product là chính ưu tiên, hỗ trợ chia cổng
    if [ -z "$SERIAL_NUM" ] || [ "$SERIAL_NUM" == "0000:00:00.0" ]; then
        # Nếu thiết bị chung chung (như ch340), tốt nhất dùng ATTRS{idVendor} và idProduct
        RULE="SUBSYSTEM==\"tty\", ATTRS{idVendor}==\"$ID_VENDOR\", ATTRS{idProduct}==\"$ID_PRODUCT\", SYMLINK+=\"$SYMLINK_NAME\", MODE=\"0666\""
        echo "⚠️  Cảnh báo: Thiết bị này không có Số Serial độc nhất. Tự động liên kết bằng VendorID."
    else
        RULE="SUBSYSTEM==\"tty\", ATTRS{idVendor}==\"$ID_VENDOR\", ATTRS{idProduct}==\"$ID_PRODUCT\", ATTRS{serial}==\"$SERIAL_NUM\", SYMLINK+=\"$SYMLINK_NAME\", MODE=\"0666\""
    fi
    
    echo $RULE >> $RULES_FILE
    echo "📝 Đã ghi Rule cho [$SYMLINK_NAME]: $RULE"
    echo "----------------------------------------------------"
}

function bind_video_device() {
    local DEVICENAME=$1
    local SYMLINK_NAME=$2

    read -p "🔌 RÚT camera USB ra để chuẩn bị. Bấm [Enter] để tiếp tục..."

    OLD_DEVS=$(ls /dev/video* 2>/dev/null)

    read -p "🔌 BÂY GIỜ hãy CẮM camera [$DEVICENAME] vào máy. Bấm [Enter] khi đã cắm xong..."
    sleep 3

    NEW_DEVS=$(ls /dev/video* 2>/dev/null)

    TARGET_DEV=""
    for dev in $NEW_DEVS; do
        if [[ ! "$OLD_DEVS" == *"$dev"* ]]; then
            TARGET_DEV=$dev
            break
        fi
    done

    if [ -z "$TARGET_DEV" ]; then
        echo "❌ Lỗi: Không nhận diện được camera mới nào được cắm vào! Hãy thử lại quá trình."
        exit 1
    fi

    echo "✅ Đã tìm thấy [$DEVICENAME] tại cổng: $TARGET_DEV"

    ID_VENDOR=$(udevadm info -a -n $TARGET_DEV | grep '{idVendor}' | head -n 1 | awk -F'==' '{print $2}' | tr -d '"')
    ID_PRODUCT=$(udevadm info -a -n $TARGET_DEV | grep '{idProduct}' | head -n 1 | awk -F'==' '{print $2}' | tr -d '"')

    if [ -z "$ID_VENDOR" ] || [ -z "$ID_PRODUCT" ]; then
        echo "❌ Lỗi: Không đọc được idVendor/idProduct của camera."
        exit 1
    fi

    RULE="SUBSYSTEM==\"video4linux\", KERNEL==\"video*\", ATTRS{idVendor}==\"$ID_VENDOR\", ATTRS{idProduct}==\"$ID_PRODUCT\", SYMLINK+=\"$SYMLINK_NAME\", MODE=\"0666\", TAG+=\"uaccess\""

    echo $RULE >> $RULES_FILE
    echo "📝 Đã ghi Rule cho [$SYMLINK_NAME]: $RULE"
    echo "----------------------------------------------------"
}

bind_device "RPLIDAR" "lidar"
bind_device "ARDUINO_MOTOR (Điều khiển bánh)" "arduino_motor"
bind_device "ARDUINO_SONAR (Cảm biến siêu âm)" "arduino_sonar"
bind_video_device "WEBCAM HUMAN FOLLOWING" "camera_human"

echo "Tải lại cấu hình UDEV hệ thống..."
udevadm control --reload-rules
udevadm trigger

echo "========================================================================="
echo "🎉 HOÀN THẤT! Từ giờ các thiết bị của bạn sẽ luôn là:"
echo " 1. /dev/lidar"
echo " 2. /dev/arduino_motor"
echo " 3. /dev/arduino_sonar"
echo " 4. /dev/camera_human"
echo "Bất kể bạn cắm vào lỗ USB nào hay thứ tự khởi động ra sao."
echo "========================================================================="
