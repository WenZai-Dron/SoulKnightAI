import cv2
import numpy as np
import subprocess
import time
import os
import logging
import random
import json
from typing import Tuple, Optional, Dict, List

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
        # 使用本地日志记录器，避免依赖尚未初始化的self.logger
        local_logger = logging.getLogger(__name__)
        local_logger.info("正在查找ADB工具...")
        
        for path in self.adb_paths:
            try:
                # 检查文件是否存在
                if not os.path.exists(path):
                    local_logger.warning(f"ADB路径不存在: {path}")
                    continue
                    
                result = subprocess.run([path, "version"], 
                                      check=True, capture_output=True, text=True)
                local_logger.info(f"找到ADB工具: {path}")
                local_logger.info(f"ADB版本: {result.stdout.strip()}")
                return path
            except subprocess.CalledProcessError as e:
                local_logger.warning(f"执行ADB命令失败: {e.stderr}, 路径: {path}")
            except Exception as e:
                local_logger.error(f"检查ADB路径时出错: {e}, 路径: {path}")
        
        local_logger.error("未找到可用的ADB工具，请检查路径配置")
        raise RuntimeError("未找到可用的ADB工具")

    def load_state(self) -> Dict:
        """加载保存的状态"""
        # 使用本地日志记录器，避免依赖尚未初始化的self.logger
        local_logger = logging.getLogger(__name__)
        
        try:
            # 确保保存目录存在
            save_dir = os.path.dirname(self.save_file)
            if save_dir and not os.path.exists(save_dir):
                os.makedirs(save_dir)
                local_logger.info(f"创建保存目录: {save_dir}")
                
            if os.path.exists(self.save_file):
                with open(self.save_file, 'r') as f:
                    state = json.load(f)
                    local_logger.info(f"从 {self.save_file} 加载状态成功")
                    return state
            else:
                local_logger.info(f"创建新状态文件: {self.save_file}")
                
        except Exception as e:
            local_logger.error(f"加载状态文件失败: {e}，使用默认状态")
            
        # 返回默认状态
        return {
            "explored_areas": [],
            "enemy_positions": {},
            "battles_won": 0,
            "battles_lost": 0,
            "total_kills": 0,
            "version": 1.0
        }

    def save_state(self) -> None:
        """保存当前状态"""
        try:
            # 确保保存目录存在
            save_dir = os.path.dirname(self.save_file)
            if save_dir and not os.path.exists(save_dir):
                os.makedirs(save_dir)
                self.logger.info(f"创建保存目录: {save_dir}")
                
            with open(self.save_file, 'w') as f:
                json.dump(self.state, f, indent=4)
            self.logger.info(f"状态已保存到 {self.save_file}")
        except Exception as e:
            self.logger.error(f"保存状态失败: {e}")

    def check_environment(self) -> None:
        """检查运行环境"""
        self.logger.info("正在检查运行环境...")
        
        # 检查ADB连接
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
            
        # 检查OpenCV是否正常工作
        try:
            img = np.zeros((100, 100, 3), dtype=np.uint8)
            cv2.imwrite("test.png", img)
            if os.path.exists("test.png"):
                os.remove("test.png")
                self.logger.info("OpenCV功能正常")
            else:
                self.logger.warning("无法写入测试图像，OpenCV可能存在问题")
        except Exception as e:
            self.logger.error(f"OpenCV测试失败: {e}")
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
                        
                        # 记录敌人位置
                        enemy_id = f"{cX}_{cY}"
                        if enemy_id not in self.state["enemy_positions"]:
                            self.state["enemy_positions"][enemy_id] = {
                                "position": (cX, cY),
                                "first_seen": time.time(),
                                "times_seen": 1
                            }
                        else:
                            self.state["enemy_positions"][enemy_id]["times_seen"] += 1
                        
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
                
            # 记录探索区域
            self.record_explored_area(target_x, target_y)
        except Exception as e:
            self.logger.error(f"移动操作失败: {e}")

    def record_explored_area(self, x: int, y: int) -> None:
        """记录已探索区域"""
        # 划分游戏区域为100x100的网格
        grid_size = 100
        grid_x = x // grid_size
        grid_y = y // grid_size
        
        grid_id = f"{grid_x}_{grid_y}"
        
        if grid_id not in self.state["explored_areas"]:
            self.state["explored_areas"].append(grid_id)
            self.logger.info(f"发现新区域: {grid_id}")
            self.save_state()

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
                    
            # 增加击杀计数
            self.state["total_kills"] += 1
            # 每击杀5次保存一次状态
            if self.state["total_kills"] % 5 == 0:
                self.save_state()
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
                    # 如果没有敌人，根据探索记录移动
                    self.explore_strategically()
                    
                # 短暂延迟，避免操作过快
                time.sleep(0.3)
            except KeyboardInterrupt:
                self.logger.info("用户手动中断")
                break
            except Exception as e:
                self.logger.error(f"主循环出错: {e}")
                time.sleep(1)  # 出错后等待一段时间
                
        # 战斗结束后保存状态
        self.state["battles_won"] += 1
        self.save_state()
        self.logger.info("战斗时间结束")

    def explore_strategically(self) -> None:
        """基于探索记录的策略性移动"""
        # 划分游戏区域为网格
        grid_size = 100
        total_grids_x = self.screen_width // grid_size
        total_grids_y = self.screen_height // grid_size
        
        # 统计每个网格的探索次数
        grid_counts = {}
        for grid_id in self.state["explored_areas"]:
            if grid_id in grid_counts:
                grid_counts[grid_id] += 1
            else:
                grid_counts[grid_id] = 1
                
        # 找出探索次数最少的网格
        unexplored_grids = []
        for x in range(total_grids_x):
            for y in range(total_grids_y):
                grid_id = f"{x}_{y}"
                # 排除屏幕边缘的网格
                if x < 1 or x >= total_grids_x - 1 or y < 1 or y >= total_grids_y - 1:
                    continue
                if grid_id not in grid_counts:
                    unexplored_grids.append((x, y))
                    
        # 如果有未探索的区域，优先前往
        if unexplored_grids:
            target_grid = random.choice(unexplored_grids)
            target_x = target_grid[0] * grid_size + grid_size // 2
            target_y = target_grid[1] * grid_size + grid_size // 2
            self.logger.info(f"前往未探索区域: {target_grid}")
            self.move_to(target_x, target_y)
            return
            
        # 如果所有区域都已探索，随机移动但倾向于探索次数少的区域
        min_count = min(grid_counts.values()) if grid_counts else 0
        least_explored = [grid_id for grid_id, count in grid_counts.items() if count == min_count]
        
        if least_explored:
            target_grid_id = random.choice(least_explored)
            x, y = map(int, target_grid_id.split('_'))
            target_x = x * grid_size + grid_size // 2
            target_y = y * grid_size + grid_size // 2
            self.logger.info(f"前往探索较少的区域: {target_grid_id}")
            self.move_to(target_x, target_y)
            return
            
        # 如果没有记录或无法确定，执行随机移动
        self.explore()

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
        print(f"已加载AI状态:")
        print(f"  已探索区域: {len(self.state['explored_areas'])}")
        print(f"  敌人记录: {len(self.state['enemy_positions'])}")
        print(f"  总击杀: {self.state['total_kills']}")
        print(f"  战斗胜利: {self.state['battles_won']}")
        
        for i in range(cycles):
            self.logger.info(f"===== 第 {i+1}/{cycles} 轮战斗 =====")
            
            try:
                # 开始战斗
                self.battle_loop(duration=240)  # 每轮战斗4分钟
                
                # 战斗结束后，等待用户操作
                print("\n本轮战斗结束")
                print(f"已探索区域: {len(self.state['explored_areas'])} | 总击杀: {self.state['total_kills']}")
                print("请手动处理结算界面，然后按Enter键继续下一轮...")
                input()
                
                # 小延迟后开始下一轮
                time.sleep(2)
            except KeyboardInterrupt:
                self.logger.info("用户手动终止程序")
                break
            except Exception as e:
                self.logger.error(f"轮次运行出错: {e}")
                self.state["battles_lost"] += 1
                self.save_state()
                print(f"第 {i+1} 轮出错，继续下一轮...")
                time.sleep(3)
                
        self.logger.info("元气骑士AI运行完成")
        print("\n===== AI统计 =====")
        print(f"总战斗轮数: {cycles}")
        print(f"胜利: {self.state['battles_won']} | 失败: {self.state['battles_lost']}")
        print(f"总击杀数: {self.state['total_kills']}")
        print(f"已探索区域: {len(self.state['explored_areas'])}")
        print(f"状态已保存到: {self.save_file}")
        print(f"详细日志已保存到: {self.log_file}")

if __name__ == "__main__":
    try:
        # 创建AI实例
        ai = SoulKnightAI()
        
        # 运行AI，进行3轮战斗
        ai.run(cycles=3)
    except Exception as e:
        # 确保日志文件存在并可写入
        log_dir = os.path.dirname("soul_knight_ai.log")
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        # 使用本地日志记录器记录错误
        local_logger = logging.getLogger(__name__)
        local_logger.error(f"程序启动失败: {str(e)}")
        
        # 将错误信息写入日志
        with open("soul_knight_ai.log", "a", encoding="utf-8") as f:
            f.write(f"程序启动失败: {str(e)}\n")
            
        print(f"程序启动失败: {e}")
        print("请检查以下事项:")
        print("1. ADB路径是否正确")
        print("2. 模拟器是否已启动并正确连接")
        print("3. 模拟器分辨率是否为1280x720")
        print(f"详细错误信息已记录到 soul_knight_ai.log")
        exit(1)    