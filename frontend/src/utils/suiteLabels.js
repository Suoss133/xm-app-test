/** 套件英文 key → 中文显示名 */
export const SUITE_LABEL_MAP = {
  LiveImageUniversal: '出图压测',
  binding: '蓝牙绑定压测',
  BluetoothBinding: '蓝牙绑定压测',
  KoocamSlidingEvent: '时间轴随机滑动',
  event_video_play: '事件视频播放压测',
  '9811_event_video_play': 'C9811事件播放压测',
  SearchAddDevice: '搜索添加设备',
  KoocamDownLoadVideo: '下载视频',
  LoginEmail: '邮箱登录',
}

export function suiteLabel(name) {
  return SUITE_LABEL_MAP[name] || name
}