"""截屏功能"""

from PIL import ImageGrab
import os
from datetime import datetime

def take_screenshot():
    """截取整个屏幕"""
    # 截取屏幕
    screenshot = ImageGrab.grab()
    
    # 生成文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"Gaia_screenshot_{timestamp}.png"
    
    # 保存到桌宠目录
    save_path = os.path.join(os.path.dirname(__file__), filename)
    screenshot.save(save_path, "PNG")
    
    print(f"截屏已保存: {save_path}")
    return save_path

if __name__ == "__main__":
    take_screenshot()