import cv2
import numpy as np
import subprocess
import time
import os
import logging
import random
from typing import Tuple, Optional

class SoulKnightAI:
    def __init__(self, adb_paths: list = [
                    r"D:\MuMuPlayer\shell\.\adb.exe", 
                    r"D:\YXArkNights-12.0\shell\.\adb.exe",
                    r"C:\Program Files\Nox\bin\adb.exe"
                 ], 
                 emulator_addr: str = "127.0.0.1:16384"):
        """初始化元气骑士AI"""
        self.adb_paths = adb_paths
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
        self.initialize_logging()
        self.find_valid_adb()
        self.check_environment()

    def initialize_logging(self) -> None:
        """初始化日志系统"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler("soul_knight_ai.log"),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def find_valid_adb(self) -> None:
        """查找有效的ADB路径"""
        self.logger.info(f"尝试查找有效的ADB路径，候选路径: {self.adb_paths}")
        
        for adb_path in self.adb_paths:
            try:
                result = subprocess.run([adb_path, "version"], 
                                      check=True, capture_output=True, text=True)
                self.logger.info(f"找到有效ADB路径: {adb_path}")
                self.logger.info(f"ADB版本: {result.stdout.strip()}")
                self.adb_path = adb_path
                return
            except FileNotFoundError:
                self.logger.warning(f"ADB路径不存在: {adb_path}")
            except subprocess.CalledProcessError as e:
                self.logger.warning(f"执行ADB命令失败: {e.stderr}, 路径: {adb_path}")
        
        self.logger.error("未找到有效的ADB路径，请检查配置")
        raise RuntimeError("未找到有效的ADB路径")

    def check_environment(self) -> None:
        """检查运行环境"""
        self.logger.info("正在检查运行环境...")
        
        # 尝试连接模拟器
        try:
            result = subprocess.run([self.adb_path, "connect", self.emulator_addr], 
                                  check=True, capture_output=True, text=True)
            if "connected" in result.stdout:
                self.logger.info(f"已连接到模拟器: {self.emulator_addr}")
            else:
                self.logger.warning(f"连接模拟器结果: {result.stdout.strip()}")
        except subprocess.CalledProcessError as e:
            self.logger.error(f"连接模拟器失败: {e.stderr}")
            raise
            
        # 检查模拟器是否返回屏幕
        screen = self.capture_screen()
        if screen is None or screen.size == 0:
            self.logger.error("无法获取模拟器屏幕，请确保模拟器已启动并正确连接")
            raise RuntimeError("无法获取模拟器屏幕")
        else:
            self.logger.info(f"成功获取屏幕，尺寸: {screen.shape[1]}x{screen.shape[0]}")
            
        self.logger.info("环境检查完成")

    def capture_screen(self) -> np.ndarray:
        """捕获模拟器屏幕"""
        try:
            # 使用ADB命令截图并保存到本地
            subprocess.run([self.adb_path, "-s", self.emulator_addr, "shell", 
                           "screencap -p /sdcard/screenshot.png"], 
                           check=True, capture_output=True)
            subprocess.run([self.adb_path, "-s", self.emulator_addr, "pull", 
                           "/sdcard/screenshot.png", "./screenshot.png"], 
                           check=True, capture_output=True)
            # 读取截图
            img = cv2.imread("./screenshot.png")
            if img is None:
                self.logger.warning("截图为空，尝试再次截图")
                # 尝试备用方法
                result = subprocess.run([self.adb_path, "-s", self.emulator_addr, "exec-out", "screencap -p"], 
                                      check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                img = cv2.imdecode(np.frombuffer(result.stdout, np.uint8), cv2.IMREAD_COLOR)
                if img is None:
                    self.logger.error("两种截图方法均失败")
                    return np.zeros((self.screen_height, self.screen_width, 3), dtype=np.uint8)
            return img
        except Exception as e:
            self.logger.error(f"截图失败: {e}")
            return np.zeros((self.screen_height, self.screen_width, 3), dtype=np.uint8)

    def detect_enemies(self, image: np.ndarray) -> Optional[Tuple[int, int]]:
        """检测敌人位置"""
        try:
            # 转换到HSV色彩空间
            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
            
            # 创建红色掩码（处理红色的两个范围）
            mask1 = cv2.inRange(hsv, self.enemy_color_lower, self.enemy_color_upper)
            mask2 = cv2.inRange(hsv, self.enemy_color_lower2, self.enemy_color_upper2)
            enemy_mask = mask1 + mask2
            
            # 查找轮廓
            contours, _ = cv2.findContours(enemy_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if contours:
                # 找到最大的轮廓
                largest_contour = max(contours, key=cv2.contourArea)
                area = cv2.contourArea(largest_contour)
                
                # 如果轮廓面积足够大，认为是敌人
                if area > 100:  # 可调整的阈值
                    M = cv2.moments(largest_contour)
                    if M["m00"] != 0:
                        cX = int(M["m10"] / M["m00"])
                        cY = int(M["m01"] / M["m00"])
                        self.logger.debug(f"检测到敌人，坐标: ({cX}, {cY})，面积: {area}")
                        return (cX, cY)
        except Exception as e:
            self.logger.error(f"敌人检测出错: {e}")
        return None

    def detect_danger(self, image: np.ndarray) -> Optional[Tuple[int, int]]:
        """检测危险区域"""
        try:
            # 转换到HSV色彩空间
            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
            
            # 创建黄色掩码（代表危险区域）
            danger_mask = cv2.inRange(hsv, self.danger_color_lower, self.danger_color_upper)
            
            # 查找轮廓
            contours, _ = cv2.findContours(danger_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if contours:
                # 找到最大的轮廓
                largest_contour = max(contours, key=cv2.contourArea)
                area = cv2.contourArea(largest_contour)
                
                # 如果轮廓面积足够大，认为是危险区域
                if area > 200:  # 可调整的阈值
                    M = cv2.moments(largest_contour)
                    if M["m00"] != 0:
                        cX = int(M["m10"] / M["m00"])
                        cY = int(M["m01"] / M["m00"])
                        self.logger.info(f"检测到危险，坐标: ({cX}, {cY})，面积: {area}")
                        return (cX, cY)
        except Exception as e:
            self.logger.error(f"危险检测出错: {e}")
        return None

    def click(self, x: int, y: int, duration: int = 100) -> None:
        """模拟点击操作"""
        # 确保坐标在屏幕范围内
        x = max(0, min(x, self.screen_width - 1))
        y = max(0, min(y, self.screen_height - 1))
        
        try:
            subprocess.run([self.adb_path, "-s", self.emulator_addr, "shell", 
                           f"input swipe {x} {y} {x} {y} {duration}"], 
                           check=True, capture_output=True)
            self.logger.info(f"点击坐标: ({x}, {y})")
            time.sleep(0.1)  # 等待操作生效
        except Exception as e:
            self.logger.error(f"点击操作失败: {e}")

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: int = 300) -> None:
        """模拟滑动操作"""
        # 确保坐标在屏幕范围内
        x1 = max(0, min(x1, self.screen_width - 1))
        y1 = max(0, min(y1, self.screen_height - 1))
        x2 = max(0, min(x2, self.screen_width - 1))
        y2 = max(0, min(y2, self.screen_height - 1))
        
        try:
            subprocess.run([self.adb_path, "-s", self.emulator_addr, "shell", 
                           f"input swipe {x1} {y1} {x2} {y2} {duration}"], 
                           check=True, capture_output=True)
            self.logger.info(f"滑动: 从({x1}, {y1})到({x2}, {y2})")
            time.sleep(0.2)  # 等待操作生效
        except Exception as e:
            self.logger.error(f"滑动操作失败: {e}")

    def move_to(self, target_x: int, target_y: int) -> None:
        """移动到目标位置"""
        try:
            # 计算移动方向和距离
            dx = target_x - self.center_x
            dy = target_y - self.center_y
            
            # 计算移动距离
            distance = np.sqrt(dx**2 + dy**2)
            
            # 如果距离太近，不移动
            if distance < 50:
                return
                
            # 计算移动终点（距离中心点一定距离）
            move_distance = min(300, int(distance * 0.8))  # 最大移动距离
            angle = np.arctan2(dy, dx)
            end_x = self.center_x + int(move_distance * np.cos(angle))
            end_y = self.center_y + int(move_distance * np.sin(angle))
            
            # 执行滑动操作（模拟移动）
            self.swipe(self.center_x, self.center_y, end_x, end_y)
            
            # 记录移动方向
            if dx > 0:
                self.last_direction = "right"
            elif dx < 0:
                self.last_direction = "left"
        except Exception as e:
            self.logger.error(f"移动操作失败: {e}")

    def attack(self, target_x: int, target_y: int) -> None:
        """攻击目标"""
        try:
            # 点击目标位置进行攻击
            self.click(target_x, target_y)
            
            # 随机移动，避免被攻击
            if random.random() < 0.3:  # 30%的概率移动
                move_direction = random.choice(["up", "down", "left", "right"])
                if move_direction == "up":
                    self.swipe(self.center_x, self.center_y, self.center_x, self.center_y - 200)
                elif move_direction == "down":
                    self.swipe(self.center_x, self.center_y, self.center_x, self.center_y + 200)
                elif move_direction == "left":
                    self.swipe(self.center_x, self.center_y, self.center_x - 200, self.center_y)
                else:  # right
                    self.swipe(self.center_x, self.center_y, self.center_x + 200, self.center_y)
        except Exception as e:
            self.logger.error(f"攻击操作失败: {e}")

    def avoid_danger(self, danger_x: int, danger_y: int) -> None:
        """躲避危险区域"""
        self.logger.info(f"开始躲避危险，坐标: ({danger_x}, {danger_y})")
        
        try:
            # 计算远离危险的方向
            dx = danger_x - self.center_x
            dy = danger_y - self.center_y
            
            # 向相反方向滑动
            target_x = self.center_x - dx * 2
            target_y = self.center_y - dy * 2
            
            # 确保目标位置在屏幕内
            target_x = max(100, min(target_x, self.screen_width - 100))
            target_y = max(100, min(target_y, self.screen_height - 100))
            
            # 执行躲避滑动
            self.swipe(self.center_x, self.center_y, target_x, target_y, duration=200)
            
            # 小范围随机移动，增加躲避效果
            for _ in range(2):
                rand_x = self.center_x + random.randint(-100, 100)
                rand_y = self.center_y + random.randint(-100, 100)
                self.swipe(self.center_x, self.center_y, rand_x, rand_y, duration=150)
        except Exception as e:
            self.logger.error(f"躲避危险失败: {e}")

    def battle_loop(self, duration: int = 300) -> None:
        """战斗主循环"""
        self.logger.info(f"开始战斗，预计持续时间: {duration}秒")
        start_time = time.time()
        
        # 提示用户手动开始游戏
        print("\n请确保模拟器已启动并进入元气骑士游戏战斗场景")
        print("AI将在5秒后开始自动操作...")
        time.sleep(5)
        
        while time.time() - start_time < duration:
            try:
                # 捕获当前屏幕
                screen = self.capture_screen()
                if screen is None or screen.size == 0:
                    self.logger.warning("屏幕捕获失败，跳过当前帧")
                    time.sleep(0.5)
                    continue
                    
                # 检测危险区域
                danger_pos = self.detect_danger(screen)
                if danger_pos:
                    self.avoid_danger(danger_pos[0], danger_pos[1])
                    continue
                    
                # 检测敌人
                enemy_pos = self.detect_enemies(screen)
                if enemy_pos:
                    # 攻击敌人
                    self.attack(enemy_pos[0], enemy_pos[1])
                else:
                    # 如果没有敌人，随机移动探索
                    self.explore()
                    
                # 短暂延迟，避免操作过快
                time.sleep(0.3)
            except KeyboardInterrupt:
                self.logger.info("用户手动中断")
                break
            except Exception as e:
                self.logger.error(f"主循环出错: {e}")
                time.sleep(1)  # 出错后等待一段时间
                
        self.logger.info("战斗时间结束")

    def explore(self) -> None:
        """随机探索地图"""
        directions = ["up", "down", "left", "right"]
        
        # 增加继续上次方向的概率
        if self.last_direction and random.random() < 0.6:
            directions.remove(self.last_direction)
            direction = random.choice([self.last_direction] * 3 + directions)
        else:
            direction = random.choice(directions)
            
        self.logger.debug(f"随机探索方向: {direction}")
        
        try:
            if direction == "up":
                self.swipe(self.center_x, self.center_y, self.center_x, self.center_y - 300)
            elif direction == "down":
                self.swipe(self.center_x, self.center_y, self.center_x, self.center_y + 300)
            elif direction == "left":
                self.swipe(self.center_x, self.center_y, self.center_x - 300, self.center_y)
            else:  # right
                self.swipe(self.center_x, self.center_y, self.center_x + 300, self.center_y)
                
            self.last_direction = direction
        except Exception as e:
            self.logger.error(f"探索移动失败: {e}")

    def run(self, cycles: int = 3) -> None:
        """运行AI主循环"""
        self.logger.info(f"开始运行元气骑士AI，计划进行 {cycles} 轮战斗")
        
        for i in range(cycles):
            self.logger.info(f"===== 第 {i+1}/{cycles} 轮战斗 =====")
            
            try:
                # 开始战斗
                self.battle_loop(duration=240)  # 每轮战斗4分钟
                
                # 战斗结束后，等待用户操作
                print("\n本轮战斗结束")
                print("请手动处理结算界面，然后按Enter键继续下一轮...")
                input()
                
                # 小延迟后开始下一轮
                time.sleep(2)
            except KeyboardInterrupt:
                self.logger.info("用户手动终止程序")
                break
            except Exception as e:
                self.logger.error(f"轮次运行出错: {e}")
                print(f"第 {i+1} 轮出错，继续下一轮...")
                time.sleep(3)
                
        self.logger.info("元气骑士AI运行完成")

if __name__ == "__main__":
    try:
        # 创建AI实例，指定多个ADB候选路径
        ai = SoulKnightAI(adb_paths=[
            r"D:\MuMuPlayer\shell\.\adb.exe",
            r"D:\YXArkNights-12.0\shell\.\adb.exe",
            r"C:\Program Files\Nox\bin\adb.exe",
            # 可添加更多候选路径
        ])
        
        # 运行AI，进行3轮战斗
        ai.run(cycles=3)
    except Exception as e:
        print(f"程序启动失败: {e}")
        print("请检查以下事项:")
        print("1. 所有ADB候选路径是否正确")
        print("2. 模拟器是否已启动并正确连接")
        print("3. 模拟器分辨率是否为1280x720")
        print("详细错误信息已记录到 soul_knight_ai.log")
        exit(1)    