# 盖亚爷爷桌宠 (Gaia Grandpa Desktop Pet)

一个运行在桌面上的赛尔号战神联盟盖亚爷爷桌面宠物。

## 📥 下载安装

### 方式一：直接下载（推荐）

[![Download ZIP](https://img.shields.io/badge/Download-ZIP%20文件-blue?style=for-the-badge&logo=github)](https://github.com/Zhulina985/DesktopPet/archive/refs/heads/main.zip)

点击上方按钮下载最新版本，解压后运行 `启动桌宠.bat` 即可。

### 方式二：Git 克隆

```bash
git clone https://github.com/Zhulina985/DesktopPet.git
cd DesktopPet
python desktop_pet.py
```

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 运行桌宠

```bash
# 方式1：命令行运行
python desktop_pet.py

# 方式2：双击运行（无窗口版本）
desktop_pet.pyw

# 方式3：Windows 用户直接双击
启动桌宠.bat
```

## ✨ 功能特性

| 功能 | 说明 |
|------|------|
| 🎭 **多角色切换** | 支持 6 种精灵：盖亚、谱尼、混元天尊、战神盖亚、索伦森、王之哈莫 |
| 💬 **AI 对话** | 支持 codebuddy / GLM-5.1 / OpenRouter API |
| 🖥️ **窗口检测** | 询问"屏幕上是什么"可检测当前活动窗口 |
| 🎨 **深色主题** | 对话框采用 #1e1e2e 深色背景 |
| 🖱️ **鼠标交互** | 右键菜单、滚轮切换角色、双击打开对话 |
| ⚙️ **开机自启** | 右键菜单可设置开机自动启动 |

## 🎮 使用技巧

- **滚轮切换**：鼠标滚轮滚动切换不同精灵角色
- **AI 对话**：按 `Ctrl+Enter` 发送消息
- **屏幕检测**：输入"现在屏幕上是什么"查看当前活动窗口
- **记忆功能**：说"记住 XXX"可将信息保存到记忆库

## 🛠️ 技术栈

- Python 3.7+
- tkinter（GUI）
- PIL/Pillow（图像处理）
- ctypes（Windows API）
- codebuddy CLI（AI 对话）
- OpenRouter API（备用 AI）

## 📁 文件说明

```
DesktopPet/
├── desktop_pet.py          # 主程序（带控制台）
├── desktop_pet.pyw         # 主程序（无窗口版本）
├── spirits_config.py       # 精灵配置
├── screenshot.py           # 截屏功能
├── requirements.txt        # 依赖列表
├── 启动桌宠.bat            # Windows 启动脚本
└── Lib_GIF/                # 精灵动画资源
    ├── 1.盖亚/
    ├── 2.谱尼/
    ├── 3.混元天尊/
    ├── 4.战神盖亚/
    ├── 5.索伦森/
    └── 6.王之哈莫/
```

## 👨‍💻 作者

- **Zhu Junyu** — 202483920031
- GitHub: [@Zhulina985](https://github.com/Zhulina985)

---

⭐ 觉得好用的话，点个 Star 支持一下吧！
