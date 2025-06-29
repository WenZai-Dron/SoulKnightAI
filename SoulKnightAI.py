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
from tkinter import messagebox, ttk, filedialog
import threading

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
        self.adb = self._find_adb()
        self.model_data = {
            "name": "DefaultModel",
            "version": "1.0",
            "training_data": [],
            "settings": {
                "sensitivity": 0.8,
                "move_speed": 1.0,
                "fire_rate": 0.5
            },
            "stats": {
                "battles": 0,
                "wins": 0,
                "kill_count": 0,
                "death_count": 0
            }
        }
        self.current_model_path = None
        self.is_running = False
        self.ai_thread = None
        
        # 创建模型保存目录
        self.models_dir = "AIModels"
        os.makedirs(self.models_dir, exist_ok=True)
        
        # 配置日志
        logging.basicConfig(filename=log_file, level=logging.INFO,
                            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger("SoulKnightAI")
        
        # 加载保存的状态
        self.save_file = save_file
        self.load_state()
        
        # 创建GUI
        self.create_gui()
    
    def _find_adb(self) -> Optional[str]:
        """查找可用的ADB路径"""
        for adb_path in self.adb_paths:
            try:
                subprocess.run([adb_path, "version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
                return adb_path
            except (subprocess.SubprocessError, FileNotFoundError):
                continue
        messagebox.showerror("错误", "未找到ADB，请检查路径配置")
        return None
    
    def adb_command(self, command: List[str]) -> Tuple[bool, str]:
        """执行ADB命令"""
        if not self.adb:
            return False, "ADB未初始化"
        
        try:
            result = subprocess.run([self.adb, "-s", self.emulator_addr] + command, 
                                    stdout=subprocess.PIPE, 
                                    stderr=subprocess.PIPE, 
                                    text=True,
                                    check=True)
            return True, result.stdout
        except subprocess.SubprocessError as e:
            self.logger.error(f"ADB命令执行失败: {e.stderr}")
            return False, e.stderr
    
    def capture_screen(self) -> Optional[np.ndarray]:
        """捕获模拟器屏幕"""
        success, _ = self.adb_command(["shell", "screencap -p /sdcard/screenshot.png"])
        if not success:
            return None
            
        success, _ = self.adb_command(["pull", "/sdcard/screenshot.png", "./screenshot.png"])
        if not success:
            return None
            
        try:
            img = cv2.imread("./screenshot.png")
            return cv2.cvtColor(img, cv2.COLOR_BGR2RGB) if img is not None else None
        except Exception as e:
            self.logger.error(f"读取屏幕截图失败: {e}")
            return None
    
    def tap(self, x: int, y: int, duration: int = 50) -> bool:
        """点击屏幕指定位置"""
        success, _ = self.adb_command(["shell", f"input tap {x} {y}"])
        return success
    
    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: int = 300) -> bool:
        """从(x1,y1)滑动到(x2,y2)"""
        success, _ = self.adb_command(["shell", f"input swipe {x1} {y1} {x2} {y2} {duration}"])
        return success
    
    def find_template(self, source: np.ndarray, template_path: str, threshold: float = 0.8) -> Optional[Tuple[int, int]]:
        """在源图像中查找模板图像"""
        if source is None:
            return None
            
        try:
            template = cv2.imread(template_path, cv2.IMREAD_COLOR)
            if template is None:
                self.logger.error(f"无法加载模板图像: {template_path}")
                return None
                
            template = cv2.cvtColor(template, cv2.COLOR_BGR2RGB)
            result = cv2.matchTemplate(source, template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            
            if max_val >= threshold:
                h, w = template.shape[:2]
                center_x = max_loc[0] + w // 2
                center_y = max_loc[1] + h // 2
                return center_x, center_y
            else:
                return None
        except Exception as e:
            self.logger.error(f"模板匹配失败: {e}")
            return None
    
    def save_model(self, model_name: str = None) -> bool:
        """保存当前AI模型"""
        if not model_name:
            model_name = self.model_data.get("name", f"Model_{int(time.time())}")
        
        # 更新模型名称
        self.model_data["name"] = model_name
        
        # 构建保存路径
        model_path = os.path.join(self.models_dir, f"{model_name}.json")
        
        try:
            with open(model_path, 'w') as f:
                json.dump(self.model_data, f, indent=4)
            self.current_model_path = model_path
            self.status_var.set(f"模型已保存: {model_path}")
            self.logger.info(f"模型保存成功: {model_path}")
            self.refresh_model_list()
            return True
        except Exception as e:
            self.status_var.set(f"保存模型失败: {str(e)}")
            self.logger.error(f"保存模型失败: {e}")
            return False
    
    def load_model(self, model_path: str) -> bool:
        """加载指定AI模型"""
        if not os.path.exists(model_path):
            self.status_var.set(f"模型文件不存在: {model_path}")
            return False
            
        try:
            with open(model_path, 'r') as f:
                self.model_data = json.load(f)
            self.current_model_path = model_path
            self.status_var.set(f"模型已加载: {model_path}")
            self.logger.info(f"模型加载成功: {model_path}")
            self.model_name_var.set(self.model_data.get("name", "Unnamed Model"))
            self.refresh_model_list()
            return True
        except Exception as e:
            self.status_var.set(f"加载模型失败: {str(e)}")
            self.logger.error(f"加载模型失败: {e}")
            return False
    
    def create_new_model(self) -> None:
        """创建新的AI模型"""
        model_name = self.model_name_var.get().strip()
        if not model_name:
            model_name = f"NewModel_{int(time.time())}"
            self.model_name_var.set(model_name)
            
        # 确认是否覆盖现有模型
        model_path = os.path.join(self.models_dir, f"{model_name}.json")
        if os.path.exists(model_path):
            if not messagebox.askyesno("确认", f"模型 '{model_name}' 已存在，是否覆盖?"):
                return
        
        # 创建新模型数据
        self.model_data = {
            "name": model_name,
            "version": "1.0",
            "training_data": [],
            "settings": {
                "sensitivity": 0.8,
                "move_speed": 1.0,
                "fire_rate": 0.5
            },
            "stats": {
                "battles": 0,
                "wins": 0,
                "kill_count": 0,
                "death_count": 0
            }
        }
        
        self.current_model_path = None
        self.status_var.set(f"新模型已创建: {model_name}")
        self.refresh_model_list()
    
    def refresh_model_list(self) -> None:
        """刷新模型列表"""
        # 清空现有列表
        for item in self.model_list.get_children():
            self.model_list.delete(item)
            
        # 添加所有模型文件
        try:
            for filename in os.listdir(self.models_dir):
                if filename.endswith(".json"):
                    model_name = os.path.splitext(filename)[0]
                    self.model_list.insert("", "end", values=(model_name,))
        except Exception as e:
            self.status_var.set(f"刷新模型列表失败: {str(e)}")
            self.logger.error(f"刷新模型列表失败: {e}")
    
    def select_model_from_list(self, event) -> None:
        """从列表中选择模型"""
        selection = self.model_list.selection()
        if not selection:
            return
            
        model_name = self.model_list.item(selection[0])["values"][0]
        model_path = os.path.join(self.models_dir, f"{model_name}.json")
        self.model_name_var.set(model_name)
        self.load_model(model_path)
    
    def train_model(self) -> None:
        """训练AI模型"""
        if self.is_running:
            self.status_var.set("AI正在运行，请先停止")
            return
            
        self.status_var.set("开始训练模型...")
        # 这里是训练模型的逻辑
        # 在实际应用中，这可能涉及收集游戏数据、运行强化学习算法等
        
        # 模拟训练过程
        self.model_data["stats"]["battles"] += 1
        if random.random() > 0.3:  # 70%的胜率
            self.model_data["stats"]["wins"] += 1
            self.model_data["stats"]["kill_count"] += random.randint(10, 50)
            self.status_var.set("训练完成: 胜利")
        else:
            self.model_data["stats"]["death_count"] += 1
            self.status_var.set("训练完成: 失败")
        
        # 保存训练数据
        training_entry = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "result": "win" if self.model_data["stats"]["battles"] > self.model_data["stats"]["wins"] else "loss",
            "kills": self.model_data["stats"]["kill_count"],
            "settings": self.model_data["settings"].copy()
        }
        self.model_data["training_data"].append(training_entry)
        
        # 自动保存模型
        if self.current_model_path:
            self.save_model()
    
    def start_ai(self) -> None:
        """启动AI运行"""
        if self.is_running:
            return
            
        self.is_running = True
        self.ai_thread = threading.Thread(target=self.run_ai, daemon=True)
        self.ai_thread.start()
        self.status_var.set("AI已启动")
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
    
    def stop_ai(self) -> None:
        """停止AI运行"""
        self.is_running = False
        if self.ai_thread:
            self.ai_thread.join(timeout=1.0)
        self.status_var.set("AI已停止")
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
    
    def run_ai(self) -> None:
        """AI主循环"""
        while self.is_running:
            try:
                # AI运行逻辑
                # 这里应该是AI在游戏中执行操作的代码
                # 例如：捕获屏幕、分析游戏状态、做出决策、执行操作
                
                # 模拟AI运行
                screen = self.capture_screen()
                if screen is not None:
                    # 简单示例：随机点击屏幕
                    x = random.randint(100, self.screen_width - 100)
                    y = random.randint(100, self.screen_height - 100)
                    self.tap(x, y)
                    
                    # 显示当前状态
                    self.status_var.set(f"AI运行中: 点击位置 ({x}, {y})")
                
                # 控制循环速度
                time.sleep(0.5)
                
            except Exception as e:
                self.logger.error(f"AI运行错误: {e}")
                self.status_var.set(f"AI运行错误: {str(e)}")
                self.is_running = False
    
    def load_state(self) -> None:
        """加载保存的状态"""
        if os.path.exists(self.save_file):
            try:
                with open(self.save_file, 'r') as f:
                    state = json.load(f)
                    if "model_path" in state and state["model_path"]:
                        self.load_model(state["model_path"])
            except Exception as e:
                self.logger.error(f"加载保存状态失败: {e}")
    
    def save_state(self) -> None:
        """保存当前状态"""
        try:
            state = {"model_path": self.current_model_path}
            with open(self.save_file, 'w') as f:
                json.dump(state, f)
        except Exception as e:
            self.logger.error(f"保存状态失败: {e}")
    
    def create_gui(self) -> None:
        """创建图形用户界面"""
        self.root = tk.Tk()
        self.root.title("元气骑士AI模型管理器")
        self.root.geometry("800x600")
        
        # 创建主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 模型管理部分
        model_frame = ttk.LabelFrame(main_frame, text="模型管理", padding="10")
        model_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(model_frame, text="模型名称:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.model_name_var = tk.StringVar(value=self.model_data.get("name", "DefaultModel"))
        model_name_entry = ttk.Entry(model_frame, textvariable=self.model_name_var, width=30)
        model_name_entry.grid(row=0, column=1, sticky=tk.W, pady=5)
        
        button_frame = ttk.Frame(model_frame)
        button_frame.grid(row=0, column=2, sticky=tk.W, pady=5)
        
        self.create_button = ttk.Button(button_frame, text="创建新模型", command=self.create_new_model)
        self.create_button.pack(side=tk.LEFT, padx=5)
        
        self.save_button = ttk.Button(button_frame, text="保存当前模型", command=lambda: self.save_model(self.model_name_var.get()))
        self.save_button.pack(side=tk.LEFT, padx=5)
        
        # 模型列表
        list_frame = ttk.LabelFrame(main_frame, text="已保存的模型", padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        columns = ("模型名称",)
        self.model_list = ttk.Treeview(list_frame, columns=columns, show="headings", height=10)
        self.model_list.heading("模型名称", text="模型名称")
        self.model_list.column("模型名称", width=200, anchor=tk.W)
        self.model_list.pack(fill=tk.BOTH, expand=True)
        
        # 绑定选择事件
        self.model_list.bind("<Double-1>", self.select_model_from_list)
        
        # 添加滚动条
        scrollbar = ttk.Scrollbar(self.model_list, orient=tk.VERTICAL, command=self.model_list.yview)
        self.model_list.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # AI控制部分
        control_frame = ttk.LabelFrame(main_frame, text="AI控制", padding="10")
        control_frame.pack(fill=tk.X, pady=5)
        
        self.start_button = ttk.Button(control_frame, text="启动AI", command=self.start_ai)
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = ttk.Button(control_frame, text="停止AI", command=self.stop_ai, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        self.train_button = ttk.Button(control_frame, text="训练模型", command=self.train_model)
        self.train_button.pack(side=tk.LEFT, padx=5)
        
        # 状态显示
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.X, pady=5)
        
        self.status_var = tk.StringVar(value="就绪")
        status_label = ttk.Label(status_frame, textvariable=self.status_var, anchor=tk.W)
        status_label.pack(fill=tk.X)
        
        # 刷新模型列表
        self.refresh_model_list()
        
        # 窗口关闭时保存状态
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def on_closing(self) -> None:
        """窗口关闭时的处理"""
        self.stop_ai()
        self.save_state()
        self.root.destroy()
    
    def run(self) -> None:
        """运行主循环"""
        if self.adb:
            self.root.mainloop()
        else:
            messagebox.showerror("错误", "ADB未找到，无法启动")

if __name__ == "__main__":
    ai = SoulKnightAI()
    ai.run()    