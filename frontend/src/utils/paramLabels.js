/** 参数字段中文映射（可按项目继续加） */
export const PARAM_LABEL_MAP = {
  device_title: '设备名称',
  device_name: '设备名称',
  device_sn: '蓝牙 SN',
  wifi_ssid: 'WiFi 名称',
  wifi_password: 'WiFi 密码',
  sleep_control: '休眠时长（秒）',
  live_stream_play: '播放时长（秒）',
  test_count: '测试次数',
  swipe_test_count: '循环滑动次数',
  device_udid: '设备序列号',
  current_app: '目标 App',
  device_type: '设备类型',
  device_no: '设备编号',
  device_id: '设备 ID',
}

export function paramLabel(key) {
  return PARAM_LABEL_MAP[key] || key
}