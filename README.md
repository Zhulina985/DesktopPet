# 🐾 桌面宠物 - DesktopPet

> 一款基于 Python Tkinter 的智能桌面宠物，支持 AI 对话、音乐控制、文件操作等功能！

![Python](https://img.shields.io/badge/Python-3.7+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

## ✨ 功能特性

### 🖼️ 宠物展示
- **GIF 动画**：支持任意 GIF 格式的动画图片
- **透明背景**：支持透明 PNG 效果
- **位置移动**：鼠标拖拽、右键菜单定位

### 🤖 AI 对话
- **WorkBuddy 大模型**：接入 AI 智能对话
- **本地模式**：离线关键词回复
- **记忆功能**：保存和读取对话上下文

### 🎵 音乐控制
- **播放/暂停**、**切歌**、**音量调节**
- 支持 Spotify、网易云音乐、QQ音乐等主流播放器

### 📁 文件操作
- **读取文件**：直接读取本地文件内容
- **写入文件**：保存内容到本地
- **创建文件夹**：新建目录

### ⚙️ 其他功能
- **开机自启动**：设置后开机自动运行
- **自动漫游**：宠物可在桌面自动移动
- **右键菜单**：快捷操作

## 🚀 快速开始

### 安装依赖

```bash
pip install pillow requests pyautogui
```

### 运行程序

```bash
python desktop_pet.py
```

## 📖 使用说明

### 基本操作

| 操作 | 说明 |
|------|------|
| 单击宠物 | 显示随机语句 |
| 双击宠物 | 打开对话窗口 |
| 拖拽宠物 | 移动位置 |
| 右键点击 | 显示菜单 |

### 对话指令

- **直接输入**：在底部输入框输入消息
- **AI 对话**：在对话框中与 AI 聊天
- **记住内容**：说"记住了，XXX"保存记忆
- **查看记忆**：说"查看记忆"查看已保存内容

### 音乐控制

直接在对话框或输入框中说：
- "播放" / "暂停" - 控制播放
- "下一首" / "上一首" - 切歌
- "音量大" / "音量小" - 调节音量

### 文件操作

| 指令格式 | 说明 |
|---------|------|
| "读取文件 C:\test.txt" | 读取文件 |
| "写入文件 test.txt 内容是 hello" | 写入文件 |
| "创建文件夹 newdir" | 新建目录 |

## ⚙️ 配置

编辑代码顶部的配置区：

```python
# GIF 图片路径
GIF_PATH = r"E:\path\to\your\gif.gif"

# 对话模式
WORKBUDDY_MODE = True  # True: AI模式 / False: 本地模式

# WorkBuddy 地址
WORKBUDDY_HOST = "127.0.0.1"
WORKBUDDY_PORT = 8080
```

### 接入 WorkBuddy AI

1. 启动 WorkBuddy 服务：
   ```bash
   codebuddy --serve --port 8080
   ```

2. 确保已登录 codebuddy：
   ```bash
   codebuddy /login
   ```

3. 设置 `WORKBUDDY_MODE = True`

## 📁 项目结构

```
DesktopPet/
├── desktop_pet.py          # 主程序（带详细注释）
├── desktop_pet.pyw         # 无窗口版（后台运行）
├── README.md              # 说明文档
└── myGIF.gif              # 宠物动画图片（需自行准备）
```

## 🛠️ 技术栈

- **GUI**：Tkinter (Python 内置)
- **图像处理**：Pillow
- **网络请求**：requests
- **音乐控制**：pyautogui
- **AI 对接**：WorkBuddy / CodeBuddy

## 📝 License

MIT License - 自由使用、修改和分发

---

**享受你的桌面宠物吧！** 🐾
