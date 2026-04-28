"""
桌面宠物 - 带对话功能版本
基于 Tkinter + Pillow 实现
功能：GIF动画、拖拽移动、点击交互、底部输入框直接对话

使用方法：
1. pip install pillow requests
2. 修改下面的配置区
3. python main.py

【接入 WorkBuddy 大模型】
1. 启动 WorkBuddy 的 HTTP 服务：
   打开命令行，运行：codebuddy --serve --port 8080
2. 在下方配置区设置 WORKBUDDY_MODE = True
3. 直接开聊！
"""

import tkinter as tk
from tkinter import scrolledtext, messagebox
from PIL import Image, ImageTk, ImageSequence
import random
import os
import sys
import threading
import requests
import json
import subprocess
import time
import ctypes
from ctypes import wintypes
from spirits_config import SPIRITS_LIST


# ========== Windows API：获取当前活动窗口 ==========
def get_active_window_info():
    """返回 (窗口标题, 窗口类名)"""
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if hwnd == 0:
            return ("（无活动窗口）", "")
        length = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value or "（无标题）"
        class_buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, class_buf, 256)
        class_name = class_buf.value
        return (title, class_name)
    except Exception:
        return ("（获取失败）", "")


# 音乐控制支持
try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False

# Word文档读取支持
try:
    from docx import Document
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

# 语音合成支持
try:
    import pyttsx3
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False

# ============ 精灵配置区 ============
# 精灵列表由 spirits_config.py 统一维护

# 生成字典方便查找（兼容旧代码）
def _build_spirits_config():
    return {f"{i+1}.{name}": gif for i, (name, folder, gif) in enumerate(SPIRITS_LIST)}

SPIRITS_CONFIG = _build_spirits_config()

# GIF资源文件夹
GIF_BASE_PATH = r"E:\index\日常模型\盖亚爷爷桌宠\Lib_GIF"

# 获取精灵GIF路径的辅助函数
def get_spirit_gif_path(spirit_key):
    """根据精灵key获取GIF完整路径"""
    if spirit_key not in SPIRITS_CONFIG:
        return None
    gif_name = SPIRITS_CONFIG[spirit_key]
    # 从key中提取文件夹名 (格式: "1.盖亚" -> "1.盖亚")
    folder = spirit_key.split(".", 1)[1] if "." in spirit_key else spirit_key
    return os.path.join(GIF_BASE_PATH, spirit_key, gif_name)

# 默认目标尺寸（宽x高），设为 None 则使用精灵原始尺寸
# 406 = 250 * 1.3 * 1.25（大30%后再大25%）
TARGET_SIZE = (406, 406)

# 去白边配置（用于减轻 GIF 透明边缘的白色轮廓）
ENABLE_WHITE_HALO_CLEANUP = True
WHITE_HALO_THRESHOLD = 245  # 越小越激进，建议 235-250
# 大 GIF 优化：文件较大时自动抽帧（每 N 帧取 1 帧）
LARGE_GIF_MB_THRESHOLD = 4
LARGE_GIF_FRAME_STEP = 2

# 上次选择的精灵保存文件
LAST_SPIRIT_FILE = r"E:\index\日常模型\盖亚爷爷桌宠\last_spirit.txt"


def remove_white_halo(frame, threshold=WHITE_HALO_THRESHOLD):
    """清理贴着透明边缘的近白像素，减少白色描边。"""
    rgba = frame.convert("RGBA")
    pixels = rgba.load()
    width, height = rgba.size
    to_clear = []

    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            if a == 0:
                continue

            is_near_white = r >= threshold and g >= threshold and b >= threshold
            if not is_near_white:
                continue

            # 只清理“贴着透明区域”的近白像素，避免误伤主体中的白色细节
            touches_transparent = False
            for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if 0 <= nx < width and 0 <= ny < height and pixels[nx, ny][3] == 0:
                    touches_transparent = True
                    break

            if touches_transparent:
                to_clear.append((x, y))

    for x, y in to_clear:
        pixels[x, y] = (0, 0, 0, 0)

    return rgba

# ===== 语音合成配置 =====
# 声音开关：True 开启，False 关闭
VOICE_ENABLED = True

# TTS 语速 (100 = 正常, 200 = 快一倍, 50 = 慢一半)
TTS_RATE = 150

# TTS 音量 (0.0 - 1.0)
TTS_VOLUME = 0.8

# ===== 对话模式 =====
# False（默认）：本地模拟回复（关键词匹配，无需联网）
# True：接入 WorkBuddy 大模型
WORKBUDDY_MODE = True

# WorkBuddy 本地服务地址
WORKBUDDY_HOST = "127.0.0.1"
WORKBUDDY_PORT = 8080
WORKBUDDY_BASE_URL = f"http://{WORKBUDDY_HOST}:{WORKBUDDY_PORT}"

# 所有 WorkBuddy API 请求都必须携带此安全头
WORKBUDDY_HEADERS = {
    "Content-Type": "application/json",
    "x-codebuddy-request": "1"
}

# 会话 ID（用于保持上下文对话）
# 留空则每次创建新会话
WORKBUDDY_SESSION_ID = ""

# 桌宠运行期间的多轮对话上下文（发给 codebuddy 的 prompt 里带上）
CHAT_HISTORY_MAX_TURNS = 15
CHAT_HISTORY_MAX_CHARS_PER_MSG = 2500

# codebuddy 单次调用超时（秒），长回复、写报告类任务可适当加大
CODEBUDDY_TIMEOUT_SEC = 180


# ======================================================
#  以下内容一般不需要修改
# ======================================================

class DesktopPet:
    def __init__(self, root):
        self.root = root
        self.root.title("桌面宠物")
        self.session_id = WORKBUDDY_SESSION_ID
        self.chat_history = []  # [{"role":"user"|"assistant", "content": str}, ...]
        self._chat_history_lock = threading.Lock()

        # ===== 窗口设置 =====
        self.root.attributes("-transparentcolor", "#f0f0f0")  # 灰色背景变透明
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)

        # ===== 精灵系统 =====
        self.current_spirit = None  # 当前精灵名
        self.frames = []           # 当前播放的PIL帧列表
        self.photo_images = []     # 预加载的PhotoImage对象
        self.current_frame_index = 0
        self.spirit_cache = {}     # 缓存已处理好的精灵帧，避免重复解码/处理
        # ===== 加载上次选择的精灵或默认 =====
        self._load_last_spirit()
        
        # ===== 加载 GIF =====
        if not self.frames or not self.photo_images:
            messagebox.showerror("错误", "无法加载任何精灵GIF")
            sys.exit(1)

        self.pet_img = self.photo_images[0]  # 使用预加载的图片
        self.pet_width = self.frames[0].width
        self.pet_height = self.frames[0].height
        
        # ===== 创建画布 =====
        self.canvas_height = self.pet_height + 60  # 留空间给按钮和输入框
        self.canvas = tk.Canvas(
            self.root,
            width=self.pet_width,
            height=self.canvas_height,
            bg="#f0f0f0",  # 和透明色一致
            highlightthickness=0
        )
        self.canvas.pack()
        
        # 绘制宠物图像
        self.pet_image_on_canvas = self.canvas.create_image(
            0, 0, anchor=tk.NW, image=self.pet_img
        )

        # ===== 创建精灵切换按钮 =====
        self._create_spirit_button()
        
        # ===== 语音开关 =====
        self.voice_enabled = VOICE_ENABLED
        
        # ===== 对话气泡 =====
        self.bubble = self.canvas.create_text(
            self.pet_width // 2, -30,
            text="",
            fill="#333333",
            font=("Microsoft YaHei", 10),
            width=200,
            justify=tk.CENTER
        )
        
        # ===== 底部输入框（居中）=====
        self.input_entry = tk.Entry(
            self.root,
            font=("Microsoft YaHei", 9),
            width=26,
            bg="#ffffff",
            relief=tk.FLAT,
            insertbackground="#333"
        )
        self.canvas.create_window(
            self.pet_width // 2, self.pet_height + 30,  # 居中
            window=self.input_entry,
            anchor=tk.CENTER
        )
        self.input_entry.insert(0, "在这里输入消息，回车发送...")
        self.input_entry.config(fg="gray")
        self.input_entry.bind("<FocusIn>", self._on_input_focus_in)
        self.input_entry.bind("<FocusOut>", self._on_input_focus_out)
        self.input_entry.bind("<Return>", self.send_message_from_input)
        
        # ===== 绑定事件 =====
        self.canvas.bind("<Button-1>", self.on_pet_click)
        self.canvas.bind("<B1-Motion>", self.drag_pet)
        self.canvas.bind("<Double-Button-1>", self.open_dialog)
        self.root.bind("<Button-3>", self.show_menu)
        
        # ===== 初始位置 =====
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        self.x = screen_w - self.pet_width - 50
        self.y = screen_h - self.canvas_height - 100
        self.root.geometry(f"+{self.x}+{self.y}")
        
        # ===== 移动参数 =====
        self.dx = 0
        self.dy = 0
        self.is_idle = True
        self.auto_move_enabled = False
        
        # ===== 闲聊语句 =====
        self.idle_phrases = [
            "你好呀~", "今天天气不错！", "要不要聊聊？",
            "戳我一下试试~", "双击我可以聊天哦！",
            "我在这儿呢~", "无聊的话就找我玩吧",
            "(*^▽^*)", "(｡•́︿•̀｡)",
        ]
        
        # ===== 启动循环 =====
        self.animate_gif()
        self.move_automatically()
        self.random_bubble()
        
        # ===== 对话窗口 =====
        self.dialog_window = None
        
        # ===== 气泡定时器 =====
        self.bubble_timer = None

    def _load_last_spirit(self):
        """加载上次选择的精灵"""
        last_spirit = None
        try:
            if os.path.exists(LAST_SPIRIT_FILE):
                with open(LAST_SPIRIT_FILE, 'r', encoding='utf-8') as f:
                    last_spirit = f.read().strip()
        except:
            pass
        
        # 验证上次的精灵是否有效
        if last_spirit and last_spirit in SPIRITS_CONFIG:
            self._load_spirit(last_spirit)
        else:
            # 默认加载第一个有效精灵
            first_spirit = next(iter(SPIRITS_CONFIG), None)
            if first_spirit:
                self._load_spirit(first_spirit)

    def _load_spirit(self, spirit_name):
        """加载指定精灵的静态GIF"""
        gif_path = get_spirit_gif_path(spirit_name)
        if not gif_path or not os.path.exists(gif_path):
            print(f"找不到GIF: {gif_path}")
            return False

        # 命中缓存：切换已加载过的精灵时秒切
        if spirit_name in self.spirit_cache:
            cached_frames, cached_images = self.spirit_cache[spirit_name]
            self.frames = cached_frames
            self.photo_images = cached_images
            self.current_frame_index = 0
            self.current_spirit = spirit_name
            if hasattr(self, 'pet_img') and self.photo_images:
                self.pet_img = self.photo_images[0]
                self.canvas.itemconfig(self.pet_image_on_canvas, image=self.pet_img)
            return True
        
        try:
            gif = Image.open(gif_path)
            raw_frames = [frame.copy() for frame in ImageSequence.Iterator(gif)]
            file_size_mb = os.path.getsize(gif_path) / (1024 * 1024)
            if file_size_mb >= LARGE_GIF_MB_THRESHOLD and len(raw_frames) > 1:
                raw_frames = raw_frames[::LARGE_GIF_FRAME_STEP]
            self.frames = raw_frames
            self.current_frame_index = 0
            self.current_spirit = spirit_name
            
            # 缩放到目标尺寸
            if TARGET_SIZE:
                new_frames = []
                for frame in self.frames:
                    resized = frame.convert("RGBA").resize(TARGET_SIZE, Image.Resampling.LANCZOS)
                    if ENABLE_WHITE_HALO_CLEANUP:
                        resized = remove_white_halo(resized)
                    new_frames.append(resized)
                self.frames = new_frames
            else:
                self.frames = [frame.convert("RGBA") for frame in self.frames]
                if ENABLE_WHITE_HALO_CLEANUP:
                    self.frames = [remove_white_halo(frame) for frame in self.frames]
            
            # 预加载PhotoImage
            self.photo_images = [ImageTk.PhotoImage(frame) for frame in self.frames]
            self.spirit_cache[spirit_name] = (self.frames, self.photo_images)
            
            # 更新显示
            if hasattr(self, 'pet_img') and self.photo_images:
                self.pet_img = self.photo_images[0]
                self.canvas.itemconfig(self.pet_image_on_canvas, image=self.pet_img)
            
            return True
        except Exception as e:
            print(f"加载GIF失败: {e}")
            return False

    def _create_spirit_button(self):
        """创建精灵切换按钮"""
        self.spirit_btn = tk.Button(
            self.canvas,
            text="🔄 切换精灵",
            font=("Microsoft YaHei", 7),
            command=self._show_spirit_selector,
            bg="#9c27b0",  # 紫色
            fg="white",
            relief=tk.RAISED,
            cursor="hand2"
        )
        # 按钮放在精灵图右下角
        self.spirit_btn.window = self.canvas.create_window(
            self.pet_width - 5,
            self.pet_height - 5,
            window=self.spirit_btn,
            anchor=tk.SE
        )

    def _toggle_voice(self):
        """切换语音开关"""
        self.voice_enabled = not self.voice_enabled
        if self.voice_enabled:
            icon = "🔊"
            color = "#4CAF50"
        else:
            icon = "🔇"
            color = "#f44336"
        
        # 更新对话框按钮
        if hasattr(self, 'dialog_voice_btn') and self.dialog_voice_btn.winfo_exists():
            self.dialog_voice_btn.config(text=icon, bg=color)

    def _speak(self, text):
        """语音合成播放（暂未启用）"""
        pass  # TODO: 之后再实现语音功能

    def _show_spirit_selector(self):
        """显示精灵选择窗口（3行滚轮式，上下各灰显1个，中间高亮可选）"""
        selector = tk.Toplevel(self.root)
        selector.title("选择精灵")
        selector.geometry("280x260")
        selector.resizable(False, False)
        selector.attributes("-topmost", True)
        selector.configure(bg="#2d2d2d")

        spirit_names = list(SPIRITS_CONFIG.keys())  # ["1.盖亚", "2.谱尼", ...]
        scroll_index = [0]

        # ── 标题 ──
        tk.Label(
            selector,
            text="⚡ 选择精灵  （滚轮/点击切换）",
            font=("Microsoft YaHei", 10, "bold"),
            bg="#2d2d2d", fg="#00d4aa"
        ).pack(pady=(12, 6))

        # ── 三行预览容器 ──
        wheel_frame = tk.Frame(selector, bg="#1e1e2e", bd=0)
        wheel_frame.pack(fill=tk.X, padx=24)

        # 上一行（灰显）
        row_prev = tk.Frame(wheel_frame, bg="#1a1a2e", height=36)
        row_prev.pack(fill=tk.X, pady=(0, 2))
        row_prev.pack_propagate(False)
        lbl_prev = tk.Label(row_prev, text="", font=("Microsoft YaHei", 11),
                            bg="#1a1a2e", fg="#555577", anchor="center", cursor="hand2")
        lbl_prev.pack(fill=tk.BOTH, expand=True)

        # 中间行（高亮 + 选中按钮）
        row_cur = tk.Frame(wheel_frame, bg="#3d3d5c", height=48)
        row_cur.pack(fill=tk.X, pady=(0, 2))
        row_cur.pack_propagate(False)
        lbl_cur = tk.Label(row_cur, text="", font=("Microsoft YaHei", 14, "bold"),
                           bg="#3d3d5c", fg="#ffffff", anchor="w", cursor="hand2")
        lbl_cur.pack(side=tk.LEFT, padx=18, fill=tk.Y)

        def on_select():
            self._select_spirit(spirit_names[scroll_index[0]], selector)

        btn_select = tk.Button(row_cur, text="✓ 选择", font=("Microsoft YaHei", 9, "bold"),
                               command=on_select, bg="#00d4aa", fg="#1a1a2e",
                               relief=tk.FLAT, cursor="hand2", padx=8)
        btn_select.pack(side=tk.RIGHT, padx=10, pady=8)

        # 下一行（灰显）
        row_next = tk.Frame(wheel_frame, bg="#1a1a2e", height=36)
        row_next.pack(fill=tk.X)
        row_next.pack_propagate(False)
        lbl_next = tk.Label(row_next, text="", font=("Microsoft YaHei", 11),
                            bg="#1a1a2e", fg="#555577", anchor="center", cursor="hand2")
        lbl_next.pack(fill=tk.BOTH, expand=True)

        def _name(key):
            return key.split(".", 1)[1] if "." in key else key

        def update_view():
            idx = scroll_index[0]
            n = len(spirit_names)
            lbl_prev.config(text="▲  " + _name(spirit_names[(idx - 1) % n]))
            lbl_cur.config(text="   " + _name(spirit_names[idx]))
            lbl_next.config(text="▼  " + _name(spirit_names[(idx + 1) % n]))

        def scroll_prev(event=None):
            scroll_index[0] = (scroll_index[0] - 1) % len(spirit_names)
            update_view()

        def scroll_next(event=None):
            scroll_index[0] = (scroll_index[0] + 1) % len(spirit_names)
            update_view()

        # 点击上/下行也能切换
        lbl_prev.bind("<Button-1>", lambda e: scroll_prev())
        lbl_next.bind("<Button-1>", lambda e: scroll_next())

        # 鼠标滚轮绑定（绑到整个窗口及所有子控件）
        def on_wheel(event):
            if event.delta > 0:
                scroll_prev()
            else:
                scroll_next()

        selector.bind_all("<MouseWheel>", on_wheel)
        # 窗口关闭时解绑，避免影响主窗口
        selector.protocol("WM_DELETE_WINDOW", lambda: (selector.unbind_all("<MouseWheel>"), selector.destroy()))

        # ── 提示文字 ──
        tk.Label(selector, text="鼠标滚轮 或 点击上下行切换",
                 font=("Microsoft YaHei", 8), bg="#2d2d2d", fg="#666688").pack(pady=(8, 2))

        # ── 关闭按钮 ──
        tk.Button(selector, text="关闭",
                  command=lambda: (selector.unbind_all("<MouseWheel>"), selector.destroy()),
                  bg="#ff6b6b", fg="white", font=("Microsoft YaHei", 10),
                  relief=tk.FLAT, cursor="hand2", padx=20).pack(pady=(4, 12))

        # 初始化当前精灵定位
        if self.current_spirit and self.current_spirit in spirit_names:
            scroll_index[0] = spirit_names.index(self.current_spirit)
        update_view()

    def _select_spirit(self, spirit_name, selector):
        """选择精灵"""
        selector.destroy()
        if self._load_spirit(spirit_name):
            # 去掉序号显示
            display_name = spirit_name.split(".", 1)[1] if "." in spirit_name else spirit_name
            self.show_bubble(f"已切换到：{display_name}", duration=2000)
            # 保存选择
            self._save_last_spirit(spirit_name)

    def _toggle_auto_move_selector(self, btn):
        """切换自动移动（在选择窗口里）"""
        self.toggle_auto_move()
        if self.auto_move_enabled:
            btn.config(text="▶️ 开启", bg="#4CAF50")
        else:
            btn.config(text="⏸️ 关闭", bg="#f44336")

    def _save_last_spirit(self, spirit_name):
        """保存选择的精灵"""
        try:
            with open(LAST_SPIRIT_FILE, 'w', encoding='utf-8') as f:
                f.write(spirit_name)
        except:
            pass

    def _check_workbuddy_connection(self):
        """检查 WorkBuddy 服务是否可用"""
        try:
            resp = requests.get(f"{WORKBUDDY_BASE_URL}/api/v1/health", timeout=5)
            if resp.status_code == 200:
                self.show_bubble("🤖 哼，本大爷的 AI 已就绪！有何贵干？", duration=3000)
                return True
        except Exception:
            pass

        # health 失败，尝试直接发消息测试
        try:
            resp = requests.post(
                f"{WORKBUDDY_BASE_URL}/api/v1/runs",
                json={"text": "ping", "sender": {"id": "test", "name": "test"}},
                headers=WORKBUDDY_HEADERS,
                timeout=5
            )
            if resp.status_code in (200, 202):
                self.show_bubble("🤖 哼，本大爷的 AI 已就绪！有何贵干？", duration=3000)
                return True
            elif resp.status_code == 401:
                self.show_bubble("⚠️ 需要登录 WorkBuddy，请先在浏览器打开 http://127.0.0.1:8080 授权", duration=6000)
            else:
                self.show_bubble(f"WorkBuddy 连接异常（{resp.status_code}）", duration=3000)
        except requests.exceptions.ConnectionError:
            self.show_bubble("⚠️ 未检测到 WorkBuddy 服务，请先运行：codebuddy --serve --port 8080", duration=5000)
        except Exception as e:
            self.show_bubble(f"连接检查失败：{str(e)}", duration=3000)
        return False

    def animate_gif(self):
        """播放 GIF 动画帧"""
        if not self.frames or not self.photo_images:
            self.root.after(100, self.animate_gif)
            return
        
        self.current_frame_index = (self.current_frame_index + 1) % len(self.frames)
        self.pet_img = self.photo_images[self.current_frame_index]
        self.canvas.itemconfig(self.pet_image_on_canvas, image=self.pet_img)
        self.root.after(267, self.animate_gif)

    def drag_pet(self, event):
        self.x = event.x_root - self.pet_width // 2
        self.y = event.y_root - self.canvas_height // 2
        self.root.geometry(f"+{self.x}+{self.y}")
        self.is_idle = False
        self.root.after(3000, self._set_idle_true)

    def _set_idle_true(self):
        self.is_idle = True

    def on_pet_click(self, event):
        phrase = random.choice(self.idle_phrases)
        self.show_bubble(phrase)
        self.is_idle = False
        self.root.after(3000, self._set_idle_and_hide)

    def _set_idle_and_hide(self):
        self.is_idle = True
        self.hide_bubble()

    def show_bubble(self, text, duration=3000):
        self.canvas.itemconfig(self.bubble, text=text)
        if duration > 0:
            self.root.after(duration, self.hide_bubble)

    def hide_bubble(self):
        self.canvas.itemconfig(self.bubble, text="")

    def random_bubble(self):
        if self.is_idle and random.random() < 0.15:
            phrase = random.choice(self.idle_phrases)
            self.show_bubble(phrase, duration=2500)
        self.root.after(5000, self.random_bubble)

    def move_automatically(self):
        if self.auto_move_enabled and self.is_idle:
            self.x += self.dx
            self.y += self.dy
            screen_w = self.root.winfo_screenwidth()
            screen_h = self.root.winfo_screenheight()
            if self.x <= 0 or self.x >= screen_w - self.pet_width:
                self.dx = -self.dx
            if self.y <= 0 or self.y >= screen_h - self.canvas_height:
                self.dy = -self.dy
            self.root.geometry(f"+{int(self.x)}+{int(self.y)}")
        self.root.after(50, self.move_automatically)

    # ===== 输入框事件 =====

    def _on_input_focus_in(self, event):
        if self.input_entry.get() == "在这里输入消息，回车发送...":
            self.input_entry.delete(0, tk.END)
            self.input_entry.config(fg="#333333")

    def _on_input_focus_out(self, event):
        if not self.input_entry.get().strip():
            self.input_entry.insert(0, "在这里输入消息，回车发送...")
            self.input_entry.config(fg="gray")

    def send_message_from_input(self, event=None):
        user_msg = self.input_entry.get().strip()
        if not user_msg or user_msg == "在这里输入消息，回车发送...":
            return
        self.input_entry.delete(0, tk.END)
        self.input_entry.config(fg="#333333")
        self.show_bubble(user_msg, duration=2000)

        if self.dialog_window is None or not tk.Toplevel.winfo_exists(self.dialog_window):
            self.open_dialog()
        self.append_chat("你", user_msg)
        threading.Thread(target=self._get_reply, args=(user_msg,), daemon=True).start()


    # ===== 对话功能 =====

    def open_dialog(self, event=None):
        if self.dialog_window is not None and tk.Toplevel.winfo_exists(self.dialog_window):
            self.dialog_window.lift()
            return

        self.dialog_window = tk.Toplevel(self.root)
        self.dialog_window.title("🍃 和盖亚爷爷聊天")
        self.dialog_window.attributes("-topmost", True)
        self.dialog_window.resizable(True, True)
        self.dialog_window.geometry(f"420x550+{self.x + self.pet_width + 10}+{self.y - 20}")
        self.dialog_window.configure(bg="#2d2d2d")  # 深色背景

        # 标题栏
        title_frame = tk.Frame(self.dialog_window, bg="#1a1a2e", height=40)
        title_frame.pack(fill=tk.X)
        
        # 喇叭按钮（在对话框标题栏右侧）
        voice_frame = tk.Frame(title_frame, bg="#1a1a2e")
        voice_frame.pack(side=tk.RIGHT, padx=10)
        self.dialog_voice_btn = tk.Button(
            voice_frame,
            text="🔊" if self.voice_enabled else "🔇",
            font=("Microsoft YaHei", 11),
            command=self._toggle_voice,
            bg="#4CAF50" if self.voice_enabled else "#f44336",
            fg="white",
            relief=tk.FLAT,
            cursor="hand2",
            width=2
        )
        self.dialog_voice_btn.pack(side=tk.RIGHT, padx=5, pady=5)
        
        title_label = tk.Label(title_frame, text="🍃 盖亚爷爷", font=("Microsoft YaHei", 12, "bold"),
                              bg="#1a1a2e", fg="#00d4aa")
        title_label.pack(side=tk.LEFT, padx=15, pady=8)

        # 聊天显示区域
        self.chat_display = scrolledtext.ScrolledText(
            self.dialog_window,
            wrap=tk.WORD,
            font=("Microsoft YaHei", 11),
            state=tk.DISABLED,
            bg="#1e1e2e",
            fg="#ffffff",
            insertbackground="#00d4aa",
            relief=tk.FLAT,
            padx=10,
            pady=10
        )
        self.chat_display.pack(fill=tk.BOTH, expand=True, padx=15, pady=(10, 5))

        # 配置标签样式
        self.chat_display.tag_configure("user", foreground="#64b5f6", font=("Microsoft YaHei", 11, "bold"))
        self.chat_display.tag_configure("pet", foreground="#81c784", font=("Microsoft YaHei", 10))
        self.chat_display.tag_configure("system", foreground="#ffa726", font=("Microsoft YaHei", 9, "italic"))

        # 等待提示区域
        self.waiting_frame = tk.Frame(self.dialog_window, bg="#1e1e2e")
        self.waiting_label = tk.Label(self.waiting_frame, text="", font=("Microsoft YaHei", 10),
                                      bg="#1e1e2e", fg="#00d4aa")
        self.waiting_label.pack(pady=5)

        # 输入区域
        input_frame = tk.Frame(self.dialog_window, bg="#2d2d2d")
        input_frame.pack(fill=tk.X, padx=15, pady=10)

        # 换行输入框（支持多行）
        self.input_field = tk.Text(input_frame, font=("Microsoft YaHei", 11), height=5,
                                   bg="#3d3d5c", fg="#ffffff", insertbackground="#00d4aa",
                                   relief=tk.FLAT, wrap=tk.WORD)
        self.input_field.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.input_field.bind("<Control-Return>", self.send_message)
        
        # 发送按钮
        send_btn = tk.Button(
            input_frame, text="发送", command=self.send_message,
            bg="#00d4aa", fg="#1a1a2e", font=("Microsoft YaHei", 10, "bold"),
            relief=tk.FLAT, padx=15, pady=5, cursor="hand2"
        )
        send_btn.pack(side=tk.RIGHT, padx=(10, 0))

        # 关闭按钮
        close_btn = tk.Button(
            self.dialog_window, text="关闭", command=self.close_dialog,
            bg="#ff6b6b", fg="white", font=("Microsoft YaHei", 9),
            relief=tk.FLAT, padx=15, cursor="hand2"
        )
        close_btn.pack(pady=(0, 10))

        self.dialog_window.protocol("WM_DELETE_WINDOW", self.close_dialog)

        mode_tip = "（接入 WorkBuddy 大模型）" if WORKBUDDY_MODE else "（本地模拟回复）"
        self.append_chat("宠物", f"😤 吾乃盖亚爷爷！{mode_tip}\n石破天惊，便是你等之辈！有何能耐？报上名来！😊")

    def append_chat(self, sender, message, tag="pet"):
        """添加聊天内容"""
        self.chat_display.config(state=tk.NORMAL)
        if sender == "你":
            prefix = "\n👤 你: "
            msg_tag = "user"
        elif sender == "系统":
            prefix = "\n💡 "
            msg_tag = "system"
        else:
            prefix = "\n🐾 宠物: "
            msg_tag = "pet"
        
        self.chat_display.insert(tk.END, prefix + message, msg_tag)
        self.chat_display.insert(tk.END, "\n")
        self.chat_display.see(tk.END)
        self.chat_display.config(state=tk.DISABLED)

    def show_waiting(self, show=True):
        """显示/隐藏等待动画"""
        if show:
            self.waiting_frame.pack(pady=5)
            self._animate_waiting()
        else:
            self.waiting_frame.pack_forget()
            self.waiting_index = 0

    def _animate_waiting(self):
        """旋转等待动画"""
        if not hasattr(self, 'waiting_index'):
            self.waiting_index = 0
        
        chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧"]
        self.waiting_label.config(text=f"思考中... {chars[self.waiting_index % len(chars)]}")
        self.waiting_index += 1
        
        if self.waiting_frame.winfo_ismapped():
            self.root.after(100, self._animate_waiting)

    def send_message(self, event=None):
        user_msg = self.input_field.get("1.0", tk.END).strip()
        if not user_msg:
            return
        self.input_field.delete("1.0", tk.END)
        self.append_chat("你", user_msg)
        self.show_waiting(True)
        threading.Thread(target=self._get_reply, args=(user_msg,), daemon=True).start()

    def _get_reply(self, user_msg):
        """获取回复"""
        # 先检查是否是屏幕/窗口检测指令
        screen_result = self._check_screen_command(user_msg)
        if screen_result:
            self.root.after(0, lambda r=screen_result, u=user_msg: self._show_reply(r, u))
            return

        # 先检查是否是记忆保存指令
        memory_result = self._check_memory_command(user_msg)
        if memory_result:
            self.root.after(0, lambda r=memory_result, u=user_msg: self._show_reply(r, u))
            return

        # 检查是否是文件操作指令
        file_result = self._check_file_command(user_msg)
        if file_result:
            self.root.after(0, lambda r=file_result, u=user_msg: self._show_reply(r, u))
            return
        
        if WORKBUDDY_MODE:
            reply = self._workbuddy_reply(user_msg)
        else:
            reply = self._local_reply(user_msg)
        self.root.after(0, lambda r=reply, u=user_msg: self._show_reply(r, u))

    def _clip_history_text(self, text):
        if len(text) <= CHAT_HISTORY_MAX_CHARS_PER_MSG:
            return text
        return text[:CHAT_HISTORY_MAX_CHARS_PER_MSG] + "\n…(已截断)"

    def _format_chat_history_for_prompt(self):
        with self._chat_history_lock:
            if not self.chat_history:
                return ""
            max_items = CHAT_HISTORY_MAX_TURNS * 2
            chunk = list(self.chat_history[-max_items:])
        lines = []
        for item in chunk:
            role_label = "用户" if item["role"] == "user" else "盖亚爷爷"
            lines.append(f"{role_label}: {self._clip_history_text(item['content'])}")
        return (
            "\n=== 本轮对话记录（请结合上下文理解与回答）===\n"
            + "\n".join(lines)
            + "\n=== 对话记录结束 ===\n"
        )

    def _record_chat_turn(self, user_msg, assistant_msg):
        with self._chat_history_lock:
            self.chat_history.append({"role": "user", "content": user_msg})
            self.chat_history.append({"role": "assistant", "content": assistant_msg})
            max_len = CHAT_HISTORY_MAX_TURNS * 2
            while len(self.chat_history) > max_len:
                self.chat_history.pop(0)

    def _path_token_looks_like_file(self, s):
        """判断用户说的片段是否像文件路径/文件名，避免把自然语言当成路径。"""
        s = (s or "").strip()
        if not s or len(s) > 240:
            return False
        if "/" in s or "\\" in s:
            return True
        import re
        if re.match(r"^[a-zA-Z]:[/\\]", s):
            return True
        lower = s.lower()
        for ext in (".txt", ".md", ".doc", ".docx", ".pdf", ".xlsx", ".csv", ".json", ".log", ".py", ".png", ".jpg", ".jpeg", ".gif"):
            if ext in lower:
                return True
        if re.match(r"^[\w\-.]+\.\w{2,8}$", s):
            return True
        return False

    def _should_snapshot_chat_into_memory(self, msg, msg_lower):
        """用户指代「刚才你查到的/上面那段」等，用对话里宠物回复写入记忆，而不是走文件指令。"""
        if not any(k in msg for k in ("记忆", "记住", "记一下", "记入", "记到", "帮你记住")):
            return False
        vague = (
            "你查到的", "查到的资料", "刚才说的", "刚才", "上面", "之前", "这些资料",
            "这段", "以上内容", "前面", "刚说的", "你刚", "上一条", "上次说的", "那段",
        )
        if any(v in msg for v in vague):
            return True
        if any(k in msg for k in ("更新记忆库", "更新记忆", "添加到记忆", "加入记忆", "写入记忆库", "写入记忆")):
            return True
        return False

    def _is_vague_memory_text(self, content):
        """「记住你查到的资料」里被误切出来的短语，应改为摘录对话。"""
        t = (content or "").strip()
        if len(t) > 120:
            return False
        vague = (
            "你查到的", "查到的资料", "刚才说的", "刚才", "上面", "之前", "这些资料",
            "这些", "这段", "那句话", "这段对话", "上文", "刚说的", "你刚",
        )
        return any(v in t for v in vague)

    def _save_recent_assistant_to_memory(self, trigger_msg):
        """把最近几轮里宠物的长回复写入 MEMORY.md（用于「记住你查到的」类指令）。"""
        memory_path = r"c:\Users\zhuju\WorkBuddy\Claw\.workbuddy\memory\MEMORY.md"
        with self._chat_history_lock:
            hist = list(self.chat_history)
        chunks = []
        for item in reversed(hist):
            if item.get("role") != "assistant":
                continue
            c = (item.get("content") or "").strip()
            if len(c) < 50:
                continue
            chunks.append(c)
            total = sum(len(x) for x in chunks)
            if total >= 18000 or len(chunks) >= 4:
                break
        if not chunks:
            return None
        body = "\n\n---\n\n".join(reversed(chunks))
        stamp = time.strftime("%Y-%m-%d %H:%M")
        try:
            with open(memory_path, "a", encoding="utf-8") as f:
                f.write(f"\n## 从对话摘录存档（{stamp}）\n用户原话：{trigger_msg.strip()}\n\n{body[:20000]}\n")
            return f"✅ 已把最近几轮里爷爷的回复整理进记忆啦（约 {len(body)} 字），路径在 MEMORY.md"
        except Exception as e:
            return f"⚠️ 写入记忆失败：{str(e)}"

    def _workbuddy_reply(self, user_msg):
        """通过 codebuddy CLI 获取回复"""
        try:
            # 读取本地记忆
            memory_path = r"c:\Users\zhuju\WorkBuddy\Claw\.workbuddy\memory\MEMORY.md"
            memory_context = ""
            if os.path.exists(memory_path):
                try:
                    with open(memory_path, 'r', encoding='utf-8') as f:
                        memory_content = f.read()
                    # 明确区分宠物身份和用户信息
                    memory_context = ('\n\n=== 身份信息 ===\n'
                                    '[宠物] 我叫盖亚爷爷，最喜欢石破天惊。吾乃赛尔号之守护者，雷伊之兄！\n'
                                    '[用户] 请根据对话历史判断用户是谁，当用户问"叫什么名字"时：\n'
                                    '   - 问宠物名字 → 回答"盖亚爷爷"\n'
                                    '   - 问用户名字 → 从对话历史中推断或回答"不知道"\n\n'
                                    '[记忆文件内容]:\n' + 
                                    memory_content + '\n=== 身份信息结束 ===\n')
                except:
                    pass
            
            # 构建带记忆 + 多轮对话上下文的提示（当前句之前的对话在 chat_history 里）
            history_block = self._format_chat_history_for_prompt()
            prompt_with_context = (
                memory_context
                + history_block
                + "\n请根据以上对话记录与身份设定，回复下面用户这句话（不必复述整段历史）：\n用户说: "
                + user_msg
            )
            
            # 使用 base64 编码传递消息，避免所有引号问题
            import base64
            encoded = base64.b64encode(prompt_with_context.encode('utf-16le')).decode('ascii')
            
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                 f"$b = '{encoded}'; $p = [System.Text.Encoding]::Unicode.GetString([System.Convert]::FromBase64String($b)); codebuddy -p -y $p --output-format text"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=CODEBUDDY_TIMEOUT_SEC
            )

            if result.returncode == 0:
                reply = result.stdout.strip() if result.stdout else ""
                if reply:
                    return reply
                else:
                    return "（AI 暂无回复）"
            else:
                error = result.stderr.strip()
                if "Authentication required" in error:
                    return "⚠️ 请先在命令行运行 codebuddy /login 登录"
                elif "Connection" in error or "connect" in error.lower():
                    return "⚠️ 连接 AI 服务失败，请确保 codebuddy 已登录"
                else:
                    return f"AI 出错：{error[:100]}" if error else "（AI 返回空结果）"

        except subprocess.TimeoutExpired:
            return f"⏱️ AI 响应超时（{CODEBUDDY_TIMEOUT_SEC} 秒），请重试或缩短问题"
        except FileNotFoundError:
            return "⚠️ 找不到 codebuddy 命令，请确保已安装并配置好环境变量"
        except Exception as e:
            return f"出错啦：{str(e)}"

    # ===== 文件操作 =====
    
    def _parse_file_command(self, msg):
        """解析文件操作指令，返回 (操作类型, 路径, 内容)"""
        msg = msg.lower().strip()
        
        # 读取文件
        if any(k in msg for k in ["读取", "打开", "查看", "看看", "cat ", "read "]):
            # 提取文件路径
            for prefix in ["读取文件", "打开文件", "查看文件", "看看文件", "读取 ", "打开 ", "查看 ", "cat "]:
                if prefix in msg:
                    path = msg.split(prefix, 1)[1].strip().strip('"').strip("'")
                    return ("read", path, None)
            # "帮我读取XX" 格式
            if "读取" in msg or "打开" in msg or "查看" in msg:
                import re
                match = re.search(r'[读取打开查看]\s*[文件]?\s*[叫做]?\s*["\']?([^"\'\n]+)["\']?', msg)
                if match:
                    return ("read", match.group(1).strip(), None)
        
        # 写入文件
        if any(k in msg for k in ["写入", "写入文件", "保存", "创建文件", "写文件"]):
            # 提取文件名和内容
            import re
            match = re.search(r'["\']?([^"\'\n]+)["\'\s]*(?:内容|是|为|写|存入)[:：]?\s*(.+)', msg)
            if match:
                return ("write", match.group(1).strip(), match.group(2).strip())
            # 简单格式：文件名 + 内容
            match = re.search(r'(?:写入|保存|创建|写)\s*["\']?([^"\'\n]+)["\'\s]+(.+)', msg)
            if match:
                return ("write", match.group(1).strip(), match.group(2).strip())
        
        # 创建文件夹
        if any(k in msg for k in ["创建文件夹", "新建文件夹", "新建目录", "mkdir"]):
            import re
            match = re.search(r'[创建新建]\s*[文件(夹)?目录]?\s*["\']?([^"\'\n]+)["\']?', msg)
            if match:
                return ("mkdir", match.group(1).strip(), None)
        
        # 追加内容（排除「添加到记忆里」等语义，避免误解析成文件路径）
        if any(k in msg for k in ["追加", "添加到", "append"]):
            if "记忆" in msg or "记忆里" in msg:
                return (None, None, None)
            import re
            match = re.search(r'["\']?([^"\'\n]+)["\'\s]*(?:追加|添加)[:：]?\s*(.+)', msg)
            if match:
                path_token = match.group(1).strip()
                if not self._path_token_looks_like_file(path_token):
                    return (None, None, None)
                return ("append", path_token, match.group(2).strip())
        
        return (None, None, None)
    
    def _safe_path(self, path):
        """安全路径处理，防止目录遍历攻击"""
        # 转换相对路径为绝对路径
        if not os.path.isabs(path):
            path = os.path.expanduser(path)
        # 规范化路径
        path = os.path.normpath(path)
        
        # 禁止访问危险路径
        dangerous = ["../", "..\\", "/etc", "/System", "C:\\Windows", "C:\\Program Files"]
        for d in dangerous:
            if d in path:
                return None
        return path
    
    def _do_file_operation(self, op, path, content):
        """执行文件操作"""
        safe_path = self._safe_path(path)
        if safe_path is None:
            return "⚠️ 路径不安全，拒绝访问"
        
        try:
            if op == "read":
                if not os.path.exists(safe_path):
                    return f"📁 文件不存在：{path}"
                with open(safe_path, 'r', encoding='utf-8') as f:
                    data = f.read()
                if len(data) > 2000:
                    return f"📖 文件内容（部分）：\n{data[:2000]}\n\n...（共 {len(data)} 字符）"
                return f"📖 文件内容：\n{data}"
            
            elif op == "write":
                # 确保目录存在
                dir_path = os.path.dirname(safe_path)
                if dir_path and not os.path.exists(dir_path):
                    os.makedirs(dir_path, exist_ok=True)
                with open(safe_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                return f"✅ 已保存到：{path}"
            
            elif op == "mkdir":
                if os.path.exists(safe_path):
                    return f"📁 文件夹已存在：{path}"
                os.makedirs(safe_path, exist_ok=True)
                return f"✅ 已创建文件夹：{path}"
            
            elif op == "append":
                if not os.path.exists(safe_path):
                    return f"📁 文件不存在，请先创建：{path}"
                with open(safe_path, 'a', encoding='utf-8') as f:
                    f.write(content + "\n")
                return f"✅ 已追加到：{path}"
        
        except PermissionError:
            return f"⚠️ 无权限访问：{path}"
        except Exception as e:
            return f"❌ 操作失败：{str(e)}"

    def _check_file_command(self, msg):
        """检查是否是文件操作指令"""
        msg_lower = msg.lower().strip()
        import re
        
        # ========== 特殊处理：打开截图（明确说"截图"时才找截图）==========
        if any(k in msg_lower for k in ["截图", "截屏", "screen"]):
            import glob
            screenshot_dir = r"E:\index\日常模型\盖亚爷爷桌宠"
            screenshots = glob.glob(os.path.join(screenshot_dir, "*screenshot*.png"))
            if not screenshots:
                screenshots = glob.glob(os.path.join(screenshot_dir, "*截图*.png"))
            if screenshots:
                latest = max(screenshots, key=os.path.getmtime)
                self.root.after(0, lambda p=latest: subprocess.run(["start", "", p], shell=True))
                return f"🖼️ 正在打开截图..."
            else:
                return "📭 还没有截图文件"
        
        # ========== 特殊处理：打开文件（直接用系统程序打开）==========
        if any(k in msg_lower for k in ["打开", "开", "start"]):
            match = re.search(r'[打开开start]\s*["\']?([^"\'\n]+)["\']?', msg)
            if match:
                path = match.group(1).strip()
                
                # 尝试多种方式补全路径
                safe_path = None
                
                # 1. 如果是绝对路径，直接用
                if os.path.isabs(path):
                    safe_path = self._safe_path(path)
                # 2. 如果包含扩展名，尝试在桌宠目录找
                elif any(ext in path.lower() for ext in ['.png', '.jpg', '.jpeg', '.gif', '.pdf', '.doc', '.docx', '.xlsx', '.txt']):
                    full_path = os.path.join(r"E:\index\日常模型\盖亚爷爷桌宠", path)
                    safe_path = self._safe_path(full_path)
                # 3. 如果是软件名，尝试找到可执行文件
                else:
                    # 尝试常见软件位置
                    common_paths = [
                        os.path.join(os.environ.get('ProgramFiles', ''), path + ".exe"),
                        os.path.join(os.environ.get('ProgramFiles(x86)', ''), path + ".exe"),
                        os.path.join(os.environ.get('APPDATA', ''), "Microsoft", "Windows", "Start Menu", "Programs", path + ".lnk"),
                    ]
                    for p in common_paths:
                        if os.path.exists(p):
                            safe_path = p
                            break
                
                if safe_path and os.path.exists(safe_path):
                    self.root.after(0, lambda p=safe_path: subprocess.run(["start", "", p], shell=True))
                    return f"📂 正在打开：{os.path.basename(safe_path)}"
                else:
                    # 找不到，交给 AI 处理
                    return None
            else:
                # 没有提取到路径，交给 AI 处理
                return None
        
        op, path, content = self._parse_file_command(msg)
        if op:
            result = self._do_file_operation(op, path, content)
            self.root.after(0, lambda: self.show_bubble("文件操作完成", duration=2000))
            return result
        return None

    def _check_screen_command(self, msg):
        """检查是否是屏幕/窗口检测指令"""
        keywords = ["屏幕上", "屏幕里", "窗口", "开着", "当前窗口", "活动窗口",
                    "现在在看什么", "现在在用", "什么应用", "开了什么"]
        msg_lower = msg.lower()
        if any(k in msg_lower for k in keywords):
            title, class_name = get_active_window_info()
            return (f"🖥️ 当前活动窗口：\n"
                    f"标题：{title}\n"
                    f"类名：{class_name}")
        return None

    def _check_memory_command(self, msg):
        """检查是否是记忆保存指令"""
        msg_lower = msg.lower().strip()

        if self._should_snapshot_chat_into_memory(msg, msg_lower):
            snap = self._save_recent_assistant_to_memory(msg)
            if snap is not None:
                return snap
        
        # ========== 自动检测用户自我介绍（我叫XXX） ==========
        import re
        # 匹配"我叫XXX"或"我是XXX"或"名字叫XXX"
        name_match = re.search(r'(?:我(?:是|叫)|名字(?:叫|是))\s*([^\s，。！？]{2,10})', msg)
        if name_match:
            user_name = name_match.group(1).strip()
            # 保存用户名字到记忆文件
            memory_path = r"c:\Users\zhuju\WorkBuddy\Claw\.workbuddy\memory\MEMORY.md"
            try:
                # 读取现有内容
                existing_content = ""
                if os.path.exists(memory_path):
                    with open(memory_path, 'r', encoding='utf-8') as f:
                        existing_content = f.read()
                
                # 检查是否已有用户信息
                if "用户" in existing_content and "卡修斯" in existing_content:
                    pass  # 已经记录过
                else:
                    # 追加用户信息
                    with open(memory_path, 'a', encoding='utf-8') as f:
                        f.write(f"\n## 用户信息\n- 用户自称\"{user_name}\"  [{time.strftime('%Y-%m-%d')}]\n")
            except Exception as e:
                pass  # 保存失败不影响对话

        # ========== 学一下（读取Word文档写入记忆）==========
        if "学一下" in msg_lower and ("word" in msg_lower or ".docx" in msg_lower or "知识" in msg_lower):
            if not DOCX_AVAILABLE:
                return "⚠️ 需要先安装 python-docx：pip install python-docx"
            import re
            # 提取文件路径
            match = re.search(r'["\']?([A-Za-z]:[^"\'\n]+?\.docx)["\']?', msg)
            if not match:
                return "⚠️ 没找到 docx 文件路径，格式：学一下这篇word的知识\"C:\\xxx.docx\""
            file_path = match.group(1).strip().strip('"').strip("'")
            file_path = os.path.normpath(file_path)
            if not os.path.exists(file_path):
                return f"📭 文件不存在：{file_path}"
            try:
                doc = Document(file_path)
                paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
                content = "\n".join(paragraphs)
                if not content:
                    return "⚠️ Word 文档里没有文字内容"
                memory_path = r"c:\Users\zhuju\WorkBuddy\Claw\.workbuddy\memory\MEMORY.md"
                filename = os.path.basename(file_path)
                stamp = time.strftime("%Y-%m-%d")
                with open(memory_path, "a", encoding="utf-8") as f:
                    f.write(f"\n## {filename}（{stamp}）\n{content}\n")
                word_count = len(content)
                para_count = len(paragraphs)
                return f"✅ 已把《{filename}》的知识写入记忆库了（约 {word_count} 字，{para_count} 段）！"
            except Exception as e:
                return f"⚠️ 读取失败：{str(e)}"

        # 检测"记住"类指令 - 直接让 codebuddy 处理记忆保存
        if any(k in msg_lower for k in ["记住", "记一下", "帮我记住", "记作", "存为记忆", "添加到记忆", "加入记忆"]):
            # 提取"记住"前面的内容作为要记忆的内容
            # 匹配 "[内容]，记住了" 或 "记住了，[内容]" 格式
            match = re.search(r'(.+?)[，,]\s*(?:记住|记一下)', msg) or \
                    re.search(r'(?:记住|记一下)[：:]\s*(.+)', msg) or \
                    re.search(r'^(.{2,30})$', msg.replace("记住了", "").replace("记住", ""))
            
            if match:
                content = match.group(1).strip()
                if self._is_vague_memory_text(content):
                    snap = self._save_recent_assistant_to_memory(msg)
                    if snap is not None:
                        return snap
                    return None
                # 保存到记忆文件
                memory_path = r"c:\Users\zhuju\WorkBuddy\Claw\.workbuddy\memory\MEMORY.md"
                try:
                    with open(memory_path, 'a', encoding='utf-8') as f:
                        f.write(f"- {content}  [{time.strftime('%Y-%m-%d')}]\n")
                    return f"✅ 已记住：{content}"
                except Exception as e:
                    return f"⚠️ 保存失败：{str(e)}"
            # 如果正则匹配不到，返回 None 让 codebuddy 处理
            return None
        
        # 检测「读记忆文件」指令（不要用字面「兄弟」匹配，否则「你兄弟是谁」会误 dump MEMORY.md）
        memory_read_phrases = (
            "查看记忆", "有什么记忆", "列出记忆", "显示记忆", "给我看记忆",
            "记忆里有什么", "都有哪些记忆", "记忆库里有什么", "打开记忆", "查一下记忆",
            "记了什么", "记了啥", "你还记着啥",
        )
        is_read_memory = any(p in msg for p in memory_read_phrases)
        if not is_read_memory:
            is_read_memory = bool(
                re.search(r"记住了\s*(哪些|什么|啥)", msg)
                or re.search(r"记住\s*(了)?\s*(哪些|什么|啥)", msg)
            )
        if is_read_memory:
            memory_path = r"c:\Users\zhuju\WorkBuddy\Claw\.workbuddy\memory\MEMORY.md"
            try:
                if os.path.exists(memory_path):
                    with open(memory_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    if len(content) > 500:
                        return f"📝 记忆内容：\n{content[:500]}\n\n...（更多）"
                    return f"📝 记忆内容：\n{content}"
                return "📭 还没有记忆记录"
            except Exception as e:
                return f"⚠️ 读取失败：{str(e)}"
        
        return None

    def _local_reply(self, msg):
        """本地模拟回复（WORKBUDDY_MODE=False 时使用）"""
        if any(k in msg for k in ["你好", "hi", "hello", "嗨"]):
            replies = ["😤 免礼！本大爷知道了", "哼，愚蠢的人类，终于来了吗", "🤖 本大爷已恭候多时！"]
        elif any(k in msg for k in ["名字", "叫什么", "是谁"]):
            replies = ["😤 吾名盖亚爷爷！石破天惊便是本大爷！", "🤖 吾乃桌宠之王！滚烫的心，霸气的魂！"]
        elif any(k in msg for k in ["天气", "今天"]):
            replies = ["我不知道外面天气怎么样诶... 不过希望你今天开心！☀️", "不管天气怎样，有我在陪你就好啦~ 🌈"]
        elif any(k in msg for k in ["再见", "拜拜", "晚安"]):
            replies = ["好的，下次再聊哦~ 拜拜！👋", "晚安！好梦~ 🌙"]
        elif any(k in msg for k in ["喜欢", "爱", "可爱"]):
            replies = ["😤 哼，知道本大爷的魅力了吗", "🤖 凡人，这就是石破天惊的魅力！"]
        elif any(k in msg for k in ["无聊", "干嘛", "做啥"]):
            replies = ["无聊吗？来跟我聊天吧！或者去外面走走~ 🚶", "我们可以一起发呆呀~ 发呆也是一种生活方式嘛 😎"]
        elif any(k in msg for k in ["帮助", "help", "能做什么"]):
            replies = ["我能陪你聊天、在屏幕上走来走去、还能给你卖萌！够不够？🐾", "我的才艺：聊天 ✅ 卖萌 ✅ 到处乱跑 ✅"]
        # 音乐控制指令
        elif any(k in msg for k in ["播放", "继续", "放歌", "start"]):
            self.root.after(0, self.music_play_pause)
            return "好的，我来帮你播放/暂停音乐~ 🎵"
        elif any(k in msg for k in ["暂停", "stop"]):
            self.root.after(0, self.music_play_pause)
            return "好的，暂停播放~ ⏸️"
        elif any(k in msg for k in ["下一首", "下一曲", "next"]):
            self.root.after(0, self.music_next)
            return "切换到下一首~ ⏭️"
        elif any(k in msg for k in ["上一首", "上一曲", "上一曲", "prev"]):
            self.root.after(0, self.music_prev)
            return "回到上一首~ ⏮️"
        elif any(k in msg for k in ["音量大", "大声", "大声点"]):
            self.root.after(0, self.music_volume_up)
            return "调高音量~ 🔊"
        elif any(k in msg for k in ["音量小", "小声", "小声点"]):
            self.root.after(0, self.music_volume_down)
            return "调低音量~ 🔉"
        else:
            replies = ["嗯嗯，我在听！多说点~ 🤔", "有意思！然后呢？", "虽然我不太懂，但我会认真听的！💪",
                       "哈哈你说得对！继续继续~ 😆", "这个话题好深奥啊...不过我喜欢！🌟"]
        return random.choice(replies)

    def _show_reply(self, reply, user_msg_for_history=None):
        self.show_waiting(False)  # 隐藏等待动画
        self.append_chat("宠物", reply)
        if user_msg_for_history is not None:
            self._record_chat_turn(user_msg_for_history, reply)
        self.show_bubble(reply[:20] + ("..." if len(reply) > 20 else ""), duration=4000)
        # 语音合成
        self._speak(reply)

    def close_dialog(self):
        if self.dialog_window is not None:
            self.dialog_window.destroy()
            self.dialog_window = None

    # ===== 音乐控制 =====
    
    def _check_pyautogui(self):
        """检查 pyautogui 是否可用"""
        if not PYAUTOGUI_AVAILABLE:
            self.show_bubble("⚠️ 需要安装 pyautogui：pip install pyautogui", duration=3000)
            return False
        return True
    
    def music_play_pause(self):
        """播放/暂停"""
        if not self._check_pyautogui():
            return
        try:
            pyautogui.press('playpause')
            self.show_bubble("⏯️ 播放/暂停", duration=1500)
        except Exception as e:
            self.show_bubble(f"控制失败：{str(e)}", duration=2000)
    
    def music_next(self):
        """下一首"""
        if not self._check_pyautogui():
            return
        try:
            pyautogui.press('nexttrack')
            self.show_bubble("⏭️ 下一首", duration=1500)
        except Exception as e:
            self.show_bubble(f"控制失败：{str(e)}", duration=2000)
    
    def music_prev(self):
        """上一首"""
        if not self._check_pyautogui():
            return
        try:
            pyautogui.press('prevtrack')
            self.show_bubble("⏮️ 上一首", duration=1500)
        except Exception as e:
            self.show_bubble(f"控制失败：{str(e)}", duration=2000)
    
    def music_volume_up(self):
        """音量+"""
        if not self._check_pyautogui():
            return
        try:
            pyautogui.press('volumeup')
            self.show_bubble("🔊 音量+", duration=1500)
        except Exception as e:
            self.show_bubble(f"控制失败：{str(e)}", duration=2000)
    
    def music_volume_down(self):
        """音量-"""
        if not self._check_pyautogui():
            return
        try:
            pyautogui.press('volumedown')
            self.show_bubble("🔉 音量-", duration=1500)
        except Exception as e:
            self.show_bubble(f"控制失败：{str(e)}", duration=2000)

    # ===== 右键菜单 =====

    def show_menu(self, event):
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="💬 打开对话", command=lambda: self.open_dialog(None))
        
        # 音乐控制子菜单
        music_menu = tk.Menu(menu, tearoff=0)
        music_menu.add_command(label="▶️ 播放/暂停", command=self.music_play_pause)
        music_menu.add_command(label="⏭️ 下一首", command=self.music_next)
        music_menu.add_command(label="⏮️ 上一首", command=self.music_prev)
        music_menu.add_separator()
        music_menu.add_command(label="🔊 音量+", command=self.music_volume_up)
        music_menu.add_command(label="🔉 音量-", command=self.music_volume_down)
        menu.add_cascade(label="🎵 音乐控制", menu=music_menu)
        
        menu.add_separator()
        
        # 自启动选项
        import winreg
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_READ)
            winreg.QueryValueEx(key, "DesktopPet")
            winreg.CloseKey(key)
            auto_start_enabled = True
        except FileNotFoundError:
            auto_start_enabled = False
        except Exception:
            auto_start_enabled = False
        
        if auto_start_enabled:
            menu.add_command(label="⏰ 取消开机自启", command=self.toggle_auto_start)
        else:
            menu.add_command(label="⏰ 开机自启动", command=self.toggle_auto_start)
        
        if self.auto_move_enabled:
            menu.add_command(label="⏸️ 停止自动移动", command=self.toggle_auto_move)
        else:
            menu.add_command(label="▶️ 开始自动移动", command=self.toggle_auto_move)
        menu.add_separator()
        menu.add_command(label="📍 回到右下角", command=self.reset_position)
        menu.add_command(label="❌ 退出", command=self.quit_app)
        menu.tk_popup(event.x_root, event.y_root)

    def toggle_auto_start(self):
        """切换开机自启动"""
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "DesktopPet"
        project_dir = os.path.dirname(os.path.abspath(__file__))
        script_path = os.path.join(project_dir, "desktop_pet.pyw")
        # 优先使用 pythonw.exe，避免登录时弹出命令行窗口
        pythonw_path = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        if not os.path.exists(pythonw_path):
            pythonw_path = sys.executable
        launch_cmd = f'"{pythonw_path}" "{script_path}"'
        
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
            try:
                winreg.QueryValueEx(key, app_name)
                # 已存在，删除它
                winreg.DeleteValue(key, app_name)
                winreg.CloseKey(key)
                self.show_bubble("⏰ 已取消开机自启", duration=2000)
            except FileNotFoundError:
                # 不存在，添加它
                if not os.path.exists(script_path):
                    winreg.CloseKey(key)
                    self.show_bubble("⚠️ 启动脚本不存在，无法设置自启", duration=3000)
                    return
                if not os.path.exists(pythonw_path):
                    winreg.CloseKey(key)
                    self.show_bubble("⚠️ pythonw.exe 不存在，无法设置自启", duration=3000)
                    return
                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, launch_cmd)
                winreg.CloseKey(key)
                self.show_bubble("⏰ 已开启开机自启", duration=2000)
        except Exception as e:
            self.show_bubble(f"⚠️ 设置失败：{str(e)}", duration=3000)

    def toggle_auto_move(self):
        self.auto_move_enabled = not self.auto_move_enabled
        if self.auto_move_enabled:
            # 开启时设置随机移动方向
            self.dx = random.choice([-3, -2, -1, 1, 2, 3])
            self.dy = random.choice([-3, -2, -1, 1, 2, 3])
            status = "已开启"
        else:
            status = "已停止"
        self.show_bubble(f"自动移动{status}", duration=2000)

    def reset_position(self):
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        self.x = screen_w - self.pet_width - 50
        self.y = screen_h - self.canvas_height - 100
        self.root.geometry(f"+{self.x}+{self.y}")

    def quit_app(self):
        self.root.quit()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = DesktopPet(root)
    root.mainloop()
