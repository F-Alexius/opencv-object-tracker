"""
opencv-object-tracker v1.2
============================
实时目标追踪：用鼠标框选一个物体，程序会自动跟着它走。

v1.2 新增：跟丢自动报警 + 模板冻结
    程序自己裁剪一份"目标照片"（模板），每帧对比当前追踪框和照片的
    相似度；一旦相似度跌破阈值（或追踪器自己报告丢失），立即判定跟丢：
    停止更新追踪器（防止模板被错误画面污染），红色报警，按 R 重新框选。

用法：
    python tracker.py            —— 用摄像头（默认）
    python tracker.py 视频.mp4   —— 用本地视频文件

操作说明：
    启动后在第一帧上拖鼠标框选目标，按 Enter 确认
    追踪中按 R   —— 重新框选目标
    追踪中按 ESC —— 退出程序

需要的库：opencv-contrib-python（内置追踪器在 contrib 扩展包里）
"""

import sys   # 读命令行参数（视频文件路径）
import cv2   # OpenCV 主库，所有计算机视觉功能的入口
import time  # 用来计算帧率 FPS

# ============ 可调参数（改这里就行） ============

TRACKER_TYPE = "CSRT"   # 追踪器类型，可选 "CSRT" / "KCF" / "MOSSE"
                        # CSRT：最准但稍慢（推荐）
                        # KCF ：速度和精度均衡
                        # MOSSE：最快但容易跟丢

CAMERA_ID = 0           # 摄像头编号，笔记本自带摄像头一般是 0

CONFIDENCE_THRESHOLD = 0.3   # 相似度低于它就判定跟丢（0~1，越大越严格）
TEMPLATE_SIZE = (64, 64)     # 比对前把图像块统一缩放成这个尺寸

# ===============================================


def create_tracker(name):
    """按名字创建一个 OpenCV 内置追踪器。

    不同版本的 OpenCV 里 MOSSE 的位置不一样（有的挪进了 legacy 模块），
    所以逐个尝试，找到能用的那个。
    """
    name = name.upper()
    if name == "CSRT":
        return cv2.TrackerCSRT_create()
    if name == "KCF":
        return cv2.TrackerKCF_create()
    if name == "MOSSE":
        # 新版 OpenCV 把 MOSSE 移到了 legacy 里
        if hasattr(cv2, "TrackerMOSSE_create"):
            return cv2.TrackerMOSSE_create()
        return cv2.legacy.TrackerMOSSE_create()
    raise ValueError(f"不支持的追踪器类型: {name}")


def draw_box(frame, box, color=(0, 255, 0)):
    """在画面上画出追踪框（一个矩形）。

    box 是 (x, y, w, h)：左上角坐标 + 宽高。
    """
    x, y, w, h = [int(v) for v in box]  # OpenCV 返回的是浮点数，画图要整数
    cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)


def crop_patch(frame, box):
    """把 box 框住的区域裁出来，处理成 64x64 的灰度小图。

    统一尺寸 + 转灰度，是为了让"不同位置、不同大小的框"也能公平比对。
    """
    x, y, w, h = [int(v) for v in box]
    patch = frame[max(y, 0):y + h, max(x, 0):x + w]  # 数组切片裁剪，防止越界
    if patch.size == 0:      # 框完全移出画面时裁出来是空的
        return None
    gray = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)   # 彩色转灰度，只看轮廓
    return cv2.resize(gray, TEMPLATE_SIZE)


def similarity(template, frame, box):
    """当前追踪框和初始模板的相似度：1.0 = 一模一样，0 = 毫无关系。

    matchTemplate 是 OpenCV 的"找相似"函数，逐像素对比两张图，
    TM_CCOEFF_NORMED 是一种抗光照变化的比对算法。
    """
    patch = crop_patch(frame, box)
    if patch is None:
        return 0.0
    return float(cv2.matchTemplate(patch, template, cv2.TM_CCOEFF_NORMED)[0][0])


def main():
    # ---- 第一幕：打开视频源 ----
    # 命令行带了参数就当视频文件用，没带就用摄像头
    # sys.argv[0] 是脚本自己的名字，sys.argv[1] 才是第一个参数
    source = sys.argv[1] if len(sys.argv) > 1 else CAMERA_ID

    # VideoCapture 既能接摄像头（传编号），也能接视频文件（传路径）
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        raise RuntimeError(f"打不开视频源: {source}（摄像头被占用，或视频路径不对）")

    # ---- 第二幕：读第一帧，框选目标，完成初始化 ----
    ok, frame = cap.read()
    if not ok:
        raise RuntimeError("读不到画面")

    # selectROI 会弹出一个窗口：拖鼠标框选，Enter 确认，C 取消
    print("请在弹出的窗口中框选要追踪的目标，按 Enter 确认")
    box = cv2.selectROI("Tracker", frame, fromCenter=False)
    if box == (0, 0, 0, 0):   # 用户没框直接取消了
        print("未选择目标，程序退出")
        cap.release()
        return

    # 用第一帧 + 框选位置初始化追踪器
    tracker = create_tracker(TRACKER_TYPE)
    tracker.init(frame, box)

    # 同时给自己留一份"目标照片"，之后每帧拿来比对（v1.2 新增）
    template = crop_patch(frame, box)

    lost = False   # 状态开关：False = 追踪中，True = 已跟丢
    print(f"开始追踪，追踪器：{TRACKER_TYPE}（按 R 重新框选，ESC 退出）")

    prev_time = time.time()   # 上一帧的时间戳，用来算 FPS

    # 视频文件要按它原本的帧率播放，不然会"快进"；摄像头则是来一帧处理一帧
    if isinstance(source, str):
        video_fps = cap.get(cv2.CAP_PROP_FPS) or 30  # 读不到就按 30 算
        frame_delay = int(1000 / video_fps)          # 每帧该停留多少毫秒
    else:
        frame_delay = 1

    # ---- 第三幕：主循环，每一帧画面走一遍 ----
    while True:
        ok, frame = cap.read()
        if not ok:
            print("画面结束或读取失败，退出")
            break

        # 计算帧率：FPS = 1 / 这一帧花的时间
        now = time.time()
        fps = 1.0 / max(now - prev_time, 1e-6)  # 防止除以零
        prev_time = now

        if not lost:
            # 【追踪中】核心一行：让追踪器根据新一帧画面更新目标位置
            found, box = tracker.update(frame)

            # 再用我们自己的模板复核一遍（v1.2 新增）
            score = similarity(template, frame, box)

            if not found or score < CONFIDENCE_THRESHOLD:
                # 追踪器报告丢失，或者画面已经不像目标了 → 判定跟丢
                lost = True
                print(f"[!] 目标丢失（相似度 {score:.2f}），追踪器已冻结，按 R 重新框选")
                # 进入丢失状态后不再调用 tracker.update()，
                # 追踪器内部的模板就此冻结，不会被柱子、草地污染
                status = f"LOST! (sim {score:.2f}) Press R"
                color = (0, 0, 255)      # 红色 = 报警
            else:
                draw_box(frame, box)
                status = f"Tracking | sim {score:.2f} | FPS {fps:.0f}"
                color = (0, 255, 0)      # 绿色 = 正常
        else:
            # 【已跟丢】什么都不更新，画面照播，红字持续报警
            status = "LOST! Press R to reselect"
            color = (0, 0, 255)

        # 把状态文字画在画面左上角
        cv2.putText(frame, status, (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

        cv2.imshow("Tracker", frame)

        # waitKey(n) = 等 n 毫秒并取按键，没有按键返回 -1
        key = cv2.waitKey(frame_delay) & 0xFF
        if key == 27:            # ESC 的键码是 27
            break
        if key == ord("r"):      # 按 R 重新框选目标
            box = cv2.selectROI("Tracker", frame, fromCenter=False)
            if box != (0, 0, 0, 0):
                tracker = create_tracker(TRACKER_TYPE)  # 重新创建并初始化
                tracker.init(frame, box)
                template = crop_patch(frame, box)       # "目标照片"也要重拍
                lost = False                            # 解除报警状态

    # ---- 第四幕：收尾 ----
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
