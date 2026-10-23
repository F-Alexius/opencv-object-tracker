# opencv-object-tracker

用 OpenCV 内置追踪器实现的摄像头实时目标追踪 demo。框选目标，程序自动跟随。

<!-- 演示 GIF 位置：录一段 10 秒左右的追踪画面放这里，README 的门面 -->
<!-- ![demo](docs/demo.gif) -->

## 功能

- 摄像头实时画面，鼠标框选目标后开始追踪
- 支持三种内置追踪器：CSRT（精准）/ KCF（均衡）/ MOSSE（快速）
- 画面实时显示 FPS 与追踪状态
- 目标跟丢时红色提示，按 R 可重新框选

## 环境

- Python 3.9+
- `opencv-contrib-python`（内置追踪器在 contrib 扩展包中，普通 opencv-python 没有）

## 安装与运行

```bash
pip install -r requirements.txt
python tracker.py            # 摄像头模式
python tracker.py video.mp4  # 视频文件模式（按原帧率播放）
```

启动后在弹出的窗口中拖鼠标框选目标，按 Enter 确认。

| 按键 | 作用 |
|------|------|
| R | 重新框选目标 |
| ESC | 退出程序 |

切换追踪器：修改 `tracker.py` 顶部的 `TRACKER_TYPE`。

## 实现原理（简述）

1. `cv2.selectROI` 让用户在第一帧上框出目标区域
2. `tracker.init(frame, box)` 以该区域初始化追踪器（提取目标外观特征）
3. 之后每一帧调用 `tracker.update(frame)`，追踪器在上一帧位置附近搜索最相似的区域，输出新位置
4. 主循环负责画框、算 FPS、响应按键

## Roadmap

- [x] 追踪丢失后自动报警 + 冻结模板防污染（v1.2，模板相似度复核）
- [ ] 跟丢后自动重新检测目标
- [ ] HSV 颜色追踪模式（不依赖内置追踪器，手写检测逻辑）
- [ ] 录制追踪视频、导出目标轨迹（CSV）并绘制轨迹图
- [ ] 命令行参数选择追踪器类型

## License

MIT
