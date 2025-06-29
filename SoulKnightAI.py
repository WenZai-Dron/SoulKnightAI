import cv2
import numpy as np
import subprocess
import time
import os
import logging
import random
import json
from typing import Tuple, Optional, Dict, List
import tkinter as tk
from tkinter import scrolledtext, ttk, messagebox
import threading
import queue
import PIL.Image
import PIL.ImageTk


class SoulKnightAI:
    def __init__(self, adb_paths: List[str] = None,
                 emulator_addr: str = "127.0.0.1:16384",
                 save_file: str = "soul_knight_ai_state.json",
                 log_file: str = "soul_knight_ai.log"):
        """初始化元气骑士AI"""
        self.adb_paths = adb_paths or [
            r"D:\MuMuPlayer\shell\.\adb.exe",
            r"D:\YXArkNights-12.0\shell\.\adb.exe",
            r"C:\Program Files\Nox\bin\adb.exe"
        ]
        self.emulator_addr = emulator_addr
        self.screen_width = 1280
        self.screen_height = 720
        self.center_x = self.screen_width // 2
        self.center_y = self.screen_height // 2
        self.enemy_color_lower = np.array([0, 100, 100])  # 红色敌人的HSV下界
        self.enemy_color_upper = np.array([10, 255, 255])  # 红色敌人的HSV上界
        self.enemy_color_lower2 = np.array([160, 100, 100])  # 红色的另一个HSV范围
        self.enemy_color_upper2 = np.array([180, 255, 255])
        self.danger_color_lower = np.array([20, 100, 100])  # 黄色危险的HSV下界
        self.danger_color_upper = np.array([40, 255, 255])  # 黄色危险的HSV上界
        self.last_direction = None
        self.save_file = save_file
        self.log_file = log_file
        self.state = self.load_state()
        # 确保日志系统首先初始化
        self.initialize_logging()
        self.adb_path = self.find_adb()
        self.check_environment()
        self.running = False
        self.vision_enabled = True
        self.control_enabled = True
        self.thread = None
        self.command_queue = queue.Queue()
        self.status = "就绪"
        self.current_screen = None
        self.detection_result = None

    def initialize_logging(self) -> None:
        """初始化日志系统"""
        # 确保日志目录存在
        log_dir = os.path.dirname(self.log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)

        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        self.logger.info("日志系统初始化成功")

    def find_adb(self) -> str:
        """查找可用的ADB路径"""
        self.logger.info("正在查找ADB工具...")

        for path in self.adb_paths:
            try:
                # 检查文件是否存在
                if not os.path.exists(path):
                    self.logger.warning(f"ADB路径不存在: {path}")
                    continue

                result = subprocess.run([path, "version"], capture_output=True, text=True, timeout=5)
                if "Android Debug Bridge" in result.stdout:
                    self.logger.info(f"找到ADB工具: {path}")
                    return path
                else:
                    self.logger.warning(f"无效的ADB工具: {path}")
            except Exception as e:
                self.logger.error(f"检查ADB工具时出错: {e}")

        self.logger.error("未找到可用的ADB工具，请检查路径配置")
        return ""

    def check_environment(self) -> bool:
        """检查运行环境"""
        self.logger.info("检查运行环境...")
        
        if not self.adb_path:
            self.logger.error("ADB工具未找到，环境检查失败")
            return False
        
        try:
            # 尝试连接模拟器
            self.logger.info(f"尝试连接模拟器: {self.emulator_addr}")
            subprocess.run([self.adb_path, "connect", self.emulator_addr], 
                          capture_output=True, text=True, check=True, timeout=10)
            
            # 检查设备是否连接
            result = subprocess.run([self.adb_path, "devices"], 
                                   capture_output=True, text=True, check=True, timeout=5)
            if self.emulator_addr in result.stdout:
                self.logger.info(f"成功连接到模拟器: {self.emulator_addr}")
                return True
            else:
                self.logger.error(f"无法连接到模拟器: {self.emulator_addr}")
                return False
        except subprocess.CalledProcessError as e:
            self.logger.error(f"连接模拟器时出错: {e.stderr}")
            return False
        except Exception as e:
            self.logger.error(f"环境检查时出错: {e}")
            return False

    def load_state(self) -> Dict:
        """加载保存的状态"""
        try:
            if os.path.exists(self.save_file):
                with open(self.save_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            self.logger.error(f"加载保存状态时出错: {e}")
        return {"battles": 0, "wins": 0, "losses": 0, "last_run": None}

    def save_state(self) -> None:
        """保存当前状态"""
        try:
            with open(self.save_file, 'w', encoding='utf-8') as f:
                json.dump(self.state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"保存状态时出错: {e}")

    def take_screenshot(self) -> Optional[np.ndarray]:
        """截取模拟器屏幕"""
        try:
            # 使用ADB命令截图并获取输出
            result = subprocess.run(
                [self.adb_path, "-s", self.emulator_addr, "exec-out", "screencap -p"],
                capture_output=True, check=True, timeout=5
            )
            
            # 将输出转换为图像
            img_array = np.frombuffer(result.stdout, np.uint8)
            img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            
            # 保存当前屏幕用于显示
            self.current_screen = img
            
            return img
        except subprocess.CalledProcessError as e:
            self.logger.error(f"截图时出错: {e.stderr}")
            return None
        except Exception as e:
            self.logger.error(f"截图时发生未知错误: {e}")
            return None

    def find_enemies(self, image: np.ndarray) -> List[Tuple[int, int, int]]:
        """在图像中查找敌人"""
        if image is None:
            return []
            
        try:
            # 转换到HSV颜色空间
            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
            
            # 创建红色掩码（考虑到红色在HSV中分为两个范围）
            mask1 = cv2.inRange(hsv, self.enemy_color_lower, self.enemy_color_upper)
            mask2 = cv2.inRange(hsv, self.enemy_color_lower2, self.enemy_color_upper2)
            mask = cv2.bitwise_or(mask1, mask2)
            
            # 查找轮廓
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            enemies = []
            for contour in contours:
                # 计算轮廓面积，过滤小面积区域
                area = cv2.contourArea(contour)
                if area > 50:  # 忽略过小的区域
                    # 计算轮廓的中心点
                    M = cv2.moments(contour)
                    if M["m00"] != 0:
                        cx = int(M["m10"] / M["m00"])
                        cy = int(M["m01"] / M["m00"])
                        enemies.append((cx, cy, int(area)))
            
            # 保存检测结果用于显示
            detection_result = image.copy()
            for (cx, cy, area) in enemies:
                cv2.circle(detection_result, (cx, cy), 10, (0, 255, 0), 2)
                cv2.putText(detection_result, f"Enemy: {area}", (cx-20, cy-20), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            self.detection_result = detection_result
            
            return enemies
        except Exception as e:
            self.logger.error(f"查找敌人时出错: {e}")
            return []

    def find_danger(self, image: np.ndarray) -> List[Tuple[int, int, int]]:
        """在图像中查找危险区域（如子弹、陷阱等）"""
        if image is None:
            return []
            
        try:
            # 转换到HSV颜色空间
            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
            
            # 创建黄色掩码（表示危险）
            mask = cv2.inRange(hsv, self.danger_color_lower, self.danger_color_upper)
            
            # 查找轮廓
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            danger_areas = []
            for contour in contours:
                # 计算轮廓面积，过滤小面积区域
                area = cv2.contourArea(contour)
                if area > 30:  # 忽略过小的区域
                    # 计算轮廓的中心点
                    M = cv2.moments(contour)
                    if M["m00"] != 0:
                        cx = int(M["m10"] / M["m00"])
                        cy = int(M["m01"] / M["m00"])
                        danger_areas.append((cx, cy, int(area)))
            
            return danger_areas
        except Exception as e:
            self.logger.error(f"查找危险区域时出错: {e}")
            return []

    def move(self, direction: str, duration: float = 0.1) -> None:
        """控制游戏角色移动"""
        if not self.control_enabled:
            return
            
        # 方向映射到屏幕坐标（基于屏幕中心）
        directions = {
            "up": (self.center_x, self.center_y - 100),
            "down": (self.center_x, self.center_y + 100),
            "left": (self.center_x - 100, self.center_y),
            "right": (self.center_x + 100, self.center_y),
            "up_left": (self.center_x - 70, self.center_y - 70),
            "up_right": (self.center_x + 70, self.center_y - 70),
            "down_left": (self.center_x - 70, self.center_y + 70),
            "down_right": (self.center_x + 70, self.center_y + 70)
        }
        
        if direction in directions:
            x, y = directions[direction]
            try:
                # 按下
                subprocess.run([self.adb_path, "-s", self.emulator_addr, 
                               "shell", f"input touchscreen press {x} {y}"], 
                              capture_output=True, check=True)
                # 保持按下一段时间
                time.sleep(duration)
                # 松开
                subprocess.run([self.adb_path, "-s", self.emulator_addr, 
                               "shell", "input touchscreen release"], 
                              capture_output=True, check=True)
                self.logger.info(f"移动方向: {direction}")
                self.last_direction = direction
            except Exception as e:
                self.logger.error(f"移动时出错: {e}")

    def attack(self, x: int, y: int) -> None:
        """控制游戏角色攻击指定位置"""
        if not self.control_enabled:
            return
            
        try:
            # 点击指定位置进行攻击
            subprocess.run([self.adb_path, "-s", self.emulator_addr, 
                           "shell", f"input tap {x} {y}"], 
                          capture_output=True, check=True)
            self.logger.info(f"攻击位置: ({x}, {y})")
        except Exception as e:
            self.logger.error(f"攻击时出错: {e}")

    def use_skill(self) -> None:
        """使用角色技能"""
        if not self.control_enabled:
            return
            
        try:
            # 假设技能按钮在屏幕右上角
            skill_x = self.screen_width - 100
            skill_y = 100
            subprocess.run([self.adb_path, "-s", self.emulator_addr, 
                           "shell", f"input tap {skill_x} {skill_y}"], 
                          capture_output=True, check=True)
            self.logger.info("使用技能")
        except Exception as e:
            self.logger.error(f"使用技能时出错: {e}")

    def start_battle(self) -> bool:
        """开始一场战斗"""
        self.logger.info("准备开始战斗...")
        
        # 假设开始战斗的按钮位置
        start_x = self.center_x
        start_y = self.center_y + 200
        
        try:
            # 点击开始战斗按钮
            subprocess.run([self.adb_path, "-s", self.emulator_addr, 
                           "shell", f"input tap {start_x} {start_y}"], 
                          capture_output=True, check=True)
            self.logger.info("已点击开始战斗按钮")
            
            # 等待战斗加载
            time.sleep(3)
            
            # 更新战斗计数
            self.state["battles"] = self.state.get("battles", 0) + 1
            self.save_state()
            
            return True
        except Exception as e:
            self.logger.error(f"开始战斗时出错: {e}")
            return False

    def is_battle_over(self, image: np.ndarray) -> bool:
        """判断战斗是否结束"""
        if image is None:
            return False
            
        # 简单实现：检测图像中是否有"胜利"或"失败"的文字
        # 实际应用中应该使用模板匹配或OCR识别
        # 这里仅作示例，使用颜色检测来模拟
        try:
            # 检查图像底部区域是否有特定颜色（表示胜利/失败界面）
            bottom_region = image[int(self.screen_height * 0.8):, :]
            
            # 检查红色（失败）
            red_mask = cv2.inRange(bottom_region, np.array([0, 0, 100]), np.array([100, 100, 255]))
            red_pixels = cv2.countNonZero(red_mask)
            
            # 检查绿色（胜利）
            green_mask = cv2.inRange(bottom_region, np.array([0, 100, 0]), np.array([100, 255, 100]))
            green_pixels = cv2.countNonZero(green_mask)
            
            # 如果红色或绿色像素超过一定数量，认为战斗结束
            if red_pixels > 10000:
                self.logger.info("战斗失败")
                self.state["losses"] = self.state.get("losses", 0) + 1
                self.save_state()
                return True
            elif green_pixels > 10000:
                self.logger.info("战斗胜利")
                self.state["wins"] = self.state.get("wins", 0) + 1
                self.save_state()
                return True
                
            return False
        except Exception as e:
            self.logger.error(f"判断战斗是否结束时出错: {e}")
            return False

    def main_loop(self) -> None:
        """主循环，控制整个游戏流程"""
        self.logger.info("元气骑士AI开始运行...")
        self.running = True
        self.status = "运行中"
        
        try:
            while self.running:
                # 检查是否有命令需要处理
                while not self.command_queue.empty():
                    command = self.command_queue.get()
                    if command == "stop":
                        self.running = False
                        self.status = "已停止"
                        self.logger.info("收到停止命令，AI将停止运行")
                        return
                    elif command == "pause":
                        self.status = "已暂停"
                        self.logger.info("AI已暂停")
                        # 等待恢复命令
                        while True:
                            cmd = self.command_queue.get()
                            if cmd == "resume":
                                self.status = "运行中"
                                self.logger.info("AI已恢复运行")
                                break
                            elif cmd == "stop":
                                self.running = False
                                self.status = "已停止"
                                self.logger.info("收到停止命令，AI将停止运行")
                                return
                    elif command == "use_skill":
                        self.use_skill()
                
                # 截图
                screenshot = self.take_screenshot()
                if screenshot is None:
                    self.logger.warning("无法获取屏幕截图，等待重试")
                    time.sleep(1)
                    continue
                
                # 检查战斗是否结束
                if self.is_battle_over(screenshot):
                    self.logger.info("战斗结束，准备下一场")
                    time.sleep(2)  # 等待结算界面
                    self.start_battle()
                    time.sleep(3)  # 等待下一场战斗开始
                    continue
                
                # 查找敌人
                if self.vision_enabled:
                    enemies = self.find_enemies(screenshot)
                    
                    if enemies:
                        # 攻击最近的敌人
                        closest_enemy = min(enemies, key=lambda e: 
                                          (e[0] - self.center_x)**2 + (e[1] - self.center_y)**2)
                        enemy_x, enemy_y, _ = closest_enemy
                        self.attack(enemy_x, enemy_y)
                        
                        # 根据敌人位置移动
                        dx = enemy_x - self.center_x
                        dy = enemy_y - self.center_y
                        
                        if abs(dx) > 100 or abs(dy) > 100:  # 如果敌人较远，移动靠近
                            if dx < -50:
                                if dy < -50:
                                    self.move("up_left")
                                elif dy > 50:
                                    self.move("down_left")
                                else:
                                    self.move("left")
                            elif dx > 50:
                                if dy < -50:
                                    self.move("up_right")
                                elif dy > 50:
                                    self.move("down_right")
                                else:
                                    self.move("right")
                            else:
                                if dy < -50:
                                    self.move("up")
                                elif dy > 50:
                                    self.move("down")
                    else:
                        # 没有敌人，随机移动
                        directions = ["up", "down", "left", "right", "up_left", "up_right", "down_left", "down_right"]
                        self.move(random.choice(directions), 0.2)
                
                # 查找危险并躲避
                if self.vision_enabled:
                    dangers = self.find_danger(screenshot)
                    if dangers:
                        # 计算危险区域的加权中心
                        avg_x = sum(d[0] * d[2] for d in dangers) / sum(d[2] for d in dangers)
                        avg_y = sum(d[1] * d[2] for d in dangers) / sum(d[2] for d in dangers)
                        
                        # 根据危险中心位置决定躲避方向
                        dx = avg_x - self.center_x
                        dy = avg_y - self.center_y
                        
                        if dx < 0 and dy < 0:
                            self.move("down_right")  # 危险在左上方，向右下方移动
                        elif dx < 0 and dy > 0:
                            self.move("up_right")  # 危险在左下方，向右上方移动
                        elif dx > 0 and dy < 0:
                            self.move("down_left")  # 危险在右上方，向左下方移动
                        else:
                            self.move("up_left")  # 危险在右下方，向左上方移动
                
                # 控制循环速度
                time.sleep(0.1)
                
        except Exception as e:
            self.logger.error(f"主循环出错: {e}")
        finally:
            self.running = False
            self.status = "已停止"
            self.logger.info("元气骑士AI已停止运行")

    def start(self) -> None:
        """启动AI线程"""
        if not self.running:
            self.thread = threading.Thread(target=self.main_loop)
            self.thread.daemon = True
            self.thread.start()

    def stop(self) -> None:
        """停止AI运行"""
        self.command_queue.put("stop")

    def pause(self) -> None:
        """暂停AI运行"""
        self.command_queue.put("pause")

    def resume(self) -> None:
        """恢复AI运行"""
        self.command_queue.put("resume")

    def toggle_vision(self) -> None:
        """切换视觉检测功能"""
        self.vision_enabled = not self.vision_enabled
        self.logger.info(f"视觉检测已{'启用' if self.vision_enabled else '禁用'}")

    def toggle_control(self) -> None:
        """切换游戏控制功能"""
        self.control_enabled = not self.control_enabled
        self.logger.info(f"游戏控制已{'启用' if self.control_enabled else '禁用'}")

    def trigger_skill(self) -> None:
        """触发技能使用"""
        self.command_queue.put("use_skill")


class SoulKnightAIGUI:
    def __init__(self, root: tk.Tk):
        """初始化元气骑士AI图形界面"""
        self.root = root
        self.root.title("元气骑士AI - 界面化管理")
        self.root.geometry("1000x700")
        self.root.resizable(True, True)
        
        # 创建AI实例
        self.ai = SoulKnightAI()
        
        # 创建主框架
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建顶部控制区
        self.control_frame = ttk.LabelFrame(self.main_frame, text="控制区", padding="10")
        self.control_frame.pack(fill=tk.X, pady=5)
        
        # 创建状态显示
        self.status_var = tk.StringVar(value=f"状态: {self.ai.status}")
        self.status_label = ttk.Label(self.control_frame, textvariable=self.status_var, font=("Arial", 12, "bold"))
        self.status_label.pack(side=tk.LEFT, padx=10)
        
        # 创建控制按钮
        self.start_btn = ttk.Button(self.control_frame, text="启动", command=self.start_ai)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        
        self.stop_btn = ttk.Button(self.control_frame, text="停止", command=self.stop_ai, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        
        self.pause_btn = ttk.Button(self.control_frame, text="暂停", command=self.pause_ai, state=tk.DISABLED)
        self.pause_btn.pack(side=tk.LEFT, padx=5)
        
        self.resume_btn = ttk.Button(self.control_frame, text="恢复", command=self.resume_ai, state=tk.DISABLED)
        self.resume_btn.pack(side=tk.LEFT, padx=5)
        
        self.skill_btn = ttk.Button(self.control_frame, text="使用技能", command=self.use_skill)
        self.skill_btn.pack(side=tk.LEFT, padx=5)
        
        # 创建功能开关
        self.vision_var = tk.BooleanVar(value=self.ai.vision_enabled)
        self.vision_check = ttk.Checkbutton(self.control_frame, text="视觉检测", 
                                          variable=self.vision_var, command=self.toggle_vision)
        self.vision_check.pack(side=tk.LEFT, padx=10)
        
        self.control_var = tk.BooleanVar(value=self.ai.control_enabled)
        self.control_check = ttk.Checkbutton(self.control_frame, text="游戏控制", 
                                           variable=self.control_var, command=self.toggle_control)
        self.control_check.pack(side=tk.LEFT, padx=10)
        
        # 创建中间显示区
        self.display_frame = ttk.LabelFrame(self.main_frame, text="视觉反馈", padding="10")
        self.display_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # 创建屏幕显示区域
        self.screen_label = ttk.Label(self.display_frame)
        self.screen_label.pack(fill=tk.BOTH, expand=True)
        
        # 创建底部信息区
        self.info_frame = ttk.LabelFrame(self.main_frame, text="统计信息", padding="10")
        self.info_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # 创建统计信息
        self.stats_frame = ttk.Frame(self.info_frame)
        self.stats_frame.pack(fill=tk.X, side=tk.LEFT, padx=5, pady=5)
        
        self.battles_var = tk.StringVar(value=f"战斗次数: {self.ai.state.get('battles', 0)}")
        self.battles_label = ttk.Label(self.stats_frame, textvariable=self.battles_var, font=("Arial", 10))
        self.battles_label.pack(anchor=tk.W)
        
        self.wins_var = tk.StringVar(value=f"胜利次数: {self.ai.state.get('wins', 0)}")
        self.wins_label = ttk.Label(self.stats_frame, textvariable=self.wins_var, font=("Arial", 10))
        self.wins_label.pack(anchor=tk.W)
        
        self.losses_var = tk.StringVar(value=f"失败次数: {self.ai.state.get('losses', 0)}")
        self.losses_label = ttk.Label(self.stats_frame, textvariable=self.losses_var, font=("Arial", 10))
        self.losses_label.pack(anchor=tk.W)
        
        # 创建日志显示区域
        self.log_frame = ttk.LabelFrame(self.info_frame, text="日志")
        self.log_frame.pack(fill=tk.BOTH, expand=True, side=tk.RIGHT, padx=5, pady=5)
        
        self.log_text = scrolledtext.ScrolledText(self.log_frame, wrap=tk.WORD, width=40, height=10)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.config(state=tk.DISABLED)
        
        # 配置日志处理器
        self.log_handler = TextHandler(self.log_text)
        self.log_handler.setLevel(logging.INFO)
        self.ai.logger.addHandler(self.log_handler)
        
        # 启动界面更新
        self.update_display()
        
    def start_ai(self) -> None:
        """启动AI"""
        if not self.ai.running:
            if self.ai.check_environment():
                self.ai.start()
                self.start_btn.config(state=tk.DISABLED)
                self.stop_btn.config(state=tk.NORMAL)
                self.pause_btn.config(state=tk.NORMAL)
                self.resume_btn.config(state=tk.DISABLED)
                self.update_status()
            else:
                messagebox.showerror("错误", "环境检查失败，无法启动AI")
    
    def stop_ai(self) -> None:
        """停止AI"""
        if self.ai.running:
            self.ai.stop()
            self.start_btn.config(state=tk.NORMAL)
            self.stop_btn.config(state=tk.DISABLED)
            self.pause_btn.config(state=tk.DISABLED)
            self.resume_btn.config(state=tk.DISABLED)
            self.update_status()
    
    def pause_ai(self) -> None:
        """暂停AI"""
        if self.ai.running and self.ai.status == "运行中":
            self.ai.pause()
            self.pause_btn.config(state=tk.DISABLED)
            self.resume_btn.config(state=tk.NORMAL)
            self.update_status()
    
    def resume_ai(self) -> None:
        """恢复AI"""
        if self.ai.running and self.ai.status == "已暂停":
            self.ai.resume()
            self.pause_btn.config(state=tk.NORMAL)
            self.resume_btn.config(state=tk.DISABLED)
            self.update_status()
    
    def use_skill(self) -> None:
        """使用技能"""
        if self.ai.running:
            self.ai.trigger_skill()
    
    def toggle_vision(self) -> None:
        """切换视觉检测"""
        self.ai.vision_enabled = self.vision_var.get()
        self.ai.logger.info(f"视觉检测已{'启用' if self.ai.vision_enabled else '禁用'}")
    
    def toggle_control(self) -> None:
        """切换游戏控制"""
        self.ai.control_enabled = self.control_var.get()
        self.ai.logger.info(f"游戏控制已{'启用' if self.ai.control_enabled else '禁用'}")
    
    def update_status(self) -> None:
        """更新状态显示"""
        self.status_var.set(f"状态: {self.ai.status}")
        
        # 更新统计信息
        self.battles_var.set(f"战斗次数: {self.ai.state.get('battles', 0)}")
        self.wins_var.set(f"胜利次数: {self.ai.state.get('wins', 0)}")
        self.losses_var.set(f"失败次数: {self.ai.state.get('losses', 0)}")
    
    def update_display(self) -> None:
        """更新界面显示"""
        # 更新状态
        self.update_status()
        
        # 更新屏幕显示
        if self.ai.detection_result is not None:
            # 调整图像大小以适应显示区域
            display_width = self.screen_label.winfo_width() - 20
            display_height = self.screen_label.winfo_height() - 20
            
            if display_width > 10 and display_height > 10:
                # 调整图像大小
                resized_img = cv2.resize(self.ai.detection_result, (display_width, display_height))
                
                # 转换为RGB格式
                rgb_img = cv2.cvtColor(resized_img, cv2.COLOR_BGR2RGB)
                
                # 转换为PhotoImage
                photo_img = PIL.ImageTk.PhotoImage(image=PIL.Image.fromarray(rgb_img))
                
                # 更新显示
                self.screen_label.config(image=photo_img)
                self.screen_label.image = photo_img
        
        # 安排下一次更新
        self.root.after(100, self.update_display)


class TextHandler(logging.Handler):
    """日志处理器，将日志输出到Text控件"""
    def __init__(self, text_widget):
        logging.Handler.__init__(self)
        self.text_widget = text_widget
    
    def emit(self, record):
        msg = self.format(record)
        def append():
            self.text_widget.config(state=tk.NORMAL)
            self.text_widget.insert(tk.END, msg + '\n')
            self.text_widget.config(state=tk.DISABLED)
            self.text_widget.yview(tk.END)
        # 确保在主线程中更新UI
        self.text_widget.after(0, append)


if __name__ == "__main__":
    root = tk.Tk()
    app = SoulKnightAIGUI(root)
    root.mainloop()    