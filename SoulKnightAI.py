import cv2
import numpy as np
import subprocess
import time
import os
import logging
import random
import json
from typing import Tuple, Optional, Dict, List, Any
import tkinter as tk
from tkinter import messagebox, ttk, filedialog
import threading
import shutil
from pathlib import Path

class SoulKnightAI:
    def __init__(self, adb_paths: List[str] = None, 
                 emulator_addr: str = "127.0.0.1:16384",
                 save_file: str = "soul_knight_ai_state.json",
                 log_file: str = "soul_knight_ai.log",
                 ai_models_dir: str = "AIModels"):
        """初始化元气骑士AI"""
        # 基础配置
        self.adb_paths = adb_paths or ["adb"]
        self.emulator_addr = emulator_addr
        self.save_file = save_file
        self.ai_models_dir = ai_models_dir
        
        # 创建模型目录（如果不存在）
        self._ensure_directory_exists(self.ai_models_dir)
        
        # 初始化日志
        self._init_logger(log_file)
        
        # 模型配置
        self.models: Dict[str, Dict[str, Any]] = {}  # 格式: {模型名称: {版本: 版本数据}}
        self.current_model = None
        self.current_version = None
        
        # 加载保存的状态
        self.load_state()
        
        # 默认模型设置（如果没有加载任何模型）
        if not self.models:
            self.create_new_model("default_model", "v1.0.0", {
                "can_switch_weapon": True,
                "weapon_priority": ["shotgun", "sword", "pistol"],
                "move_speed": 1.0,
                "attack_threshold": 0.7,
                "enemy_detection_range": 300,
                "health_threshold": 0.3,
                "dodge_probability": 0.5,
                "skill_usage_threshold": 0.8
            })
            self.select_model("default_model", "v1.0.0")
    
    def _ensure_directory_exists(self, directory: str) -> None:
        """确保目录存在，如果不存在则创建"""
        try:
            os.makedirs(directory, exist_ok=True)
        except Exception as e:
            self.logger.error(f"创建目录 {directory} 失败: {str(e)}")
    
    def _init_logger(self, log_file: str) -> None:
        """初始化日志系统"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger("SoulKnightAI")
    
    def create_new_model(self, model_name: str, version_name: str = "v1.0.0", 
                         model_data: Optional[Dict[str, Any]] = None) -> None:
        """
        创建新的AI模型
        
        Args:
            model_name: 模型名称
            version_name: 版本名称
            model_data: 模型初始数据
        """
        if model_name in self.models:
            if version_name in self.models[model_name]:
                self.logger.warning(f"模型 {model_name} 的版本 {version_name} 已存在，将被覆盖")
        else:
            self.models[model_name] = {}
        
        # 设置默认数据（如果未提供）
        default_data = {
            "can_switch_weapon": True,
            "weapon_priority": ["shotgun", "sword", "pistol"],
            "move_speed": 1.0,
            "attack_threshold": 0.7,
            "enemy_detection_range": 300,
            "health_threshold": 0.3,
            "dodge_probability": 0.5,
            "skill_usage_threshold": 0.8
        }
        
        # 合并默认数据和用户提供的数据
        final_data = {**default_data, **(model_data or {})}
        
        # 保存模型
        self.models[model_name][version_name] = {
            "version": version_name,
            "data": final_data,
            "creation_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "update_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "author": os.getlogin()
        }
        
        self.logger.info(f"创建新模型 {model_name} (版本: {version_name})")
        
        # 如果没有当前模型，选择这个新模型
        if not self.current_model:
            self.select_model(model_name, version_name)
            
        # 保存模型到文件
        self.save_model(model_name, version_name)
    
    def select_model(self, model_name: str, version_name: str) -> bool:
        """
        选择要使用的AI模型
        
        Args:
            model_name: 模型名称
            version_name: 版本名称
            
        Returns:
            是否成功选择模型
        """
        if model_name in self.models and version_name in self.models[model_name]:
            self.current_model = model_name
            self.current_version = version_name
            self.logger.info(f"已选择模型 {model_name} (版本: {version_name})")
            return True
        else:
            self.logger.error(f"模型 {model_name} (版本: {version_name}) 不存在")
            return False
    
    def update_model_data(self, model_name: str, version_name: str, 
                         new_data: Dict[str, Any]) -> bool:
        """
        更新模型数据
        
        Args:
            model_name: 模型名称
            version_name: 版本名称
            new_data: 要更新的数据
            
        Returns:
            是否成功更新模型
        """
        if model_name in self.models and version_name in self.models[model_name]:
            model = self.models[model_name][version_name]
            model["data"].update(new_data)
            model["update_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
            
            # 如果更新的是当前模型，同步更新
            if model_name == self.current_model and version_name == self.current_version:
                self.models[self.current_model][self.current_version] = model
                
            self.logger.info(f"更新模型 {model_name} (版本: {version_name}) 的数据")
            
            # 保存模型到文件
            self.save_model(model_name, version_name)
            
            return True
        else:
            self.logger.error(f"模型 {model_name} (版本: {version_name}) 不存在")
            return False
    
    def set_can_switch_weapon(self, can_switch: bool, 
                             model_name: Optional[str] = None, 
                             version_name: Optional[str] = None) -> bool:
        """
        设置模型是否可以切换武器
        
        Args:
            can_switch: 是否允许切换武器
            model_name: 模型名称（默认为当前模型）
            version_name: 版本名称（默认为当前版本）
            
        Returns:
            是否成功设置
        """
        if model_name is None:
            model_name = self.current_model
        if version_name is None:
            version_name = self.current_version
            
        if not model_name or not version_name:
            self.logger.error("没有当前模型，请先选择一个模型")
            return False
            
        return self.update_model_data(model_name, version_name, {"can_switch_weapon": can_switch})
    
    def change_version_number(self, model_name: str, old_version: str, 
                             new_version: str) -> bool:
        """
        更改版本号
        
        Args:
            model_name: 模型名称
            old_version: 旧版本名称
            new_version: 新版本名称
            
        Returns:
            是否成功更改版本号
        """
        if model_name not in self.models or old_version not in self.models[model_name]:
            self.logger.error(f"模型 {model_name} (版本: {old_version}) 不存在")
            return False
            
        if new_version in self.models[model_name]:
            self.logger.error(f"版本 {new_version} 已存在")
            return False
            
        # 获取旧版本数据
        old_model = self.models[model_name][old_version]
        
        # 创建新版本数据
        new_model_data = {
            "version": new_version,
            "data": {**old_model["data"]},  # 复制数据
            "creation_time": old_model["creation_time"],  # 保留创建时间
            "update_time": time.strftime("%Y-%m-%d %H:%M:%S"),  # 更新更新时间
            "author": os.getlogin(),
            "previous_version": old_version,
        }
        
        # 添加到模型字典
        self.models[model_name][new_version] = new_model_data
        
        # 删除旧版本
        del self.models[model_name][old_version]
        
        # 如果当前选择的是旧版本，更新为新版本
        if self.current_model == model_name and self.current_version == old_version:
            self.current_version = new_version
            
        # 保存更改
        self.save_state()
        
        # 重命名模型文件
        old_model_file = os.path.join(self.ai_models_dir, f"{model_name}_{old_version}.json")
        new_model_file = os.path.join(self.ai_models_dir, f"{model_name}_{new_version}.json")
        
        if os.path.exists(old_model_file):
            os.rename(old_model_file, new_model_file)
            
        self.logger.info(f"将模型 {model_name} 的版本从 {old_version} 更改为 {new_version}")
        return True
    
    def get_model_info(self, model_name: str, version_name: str) -> Optional[Dict[str, Any]]:
        """
        获取模型信息
        
        Args:
            model_name: 模型名称
            version_name: 版本名称
            
        Returns:
            模型信息字典，如果不存在则返回None
        """
        if model_name in self.models and version_name in self.models[model_name]:
            return {
                "model_name": model_name,
                "version": version_name,
                "creation_time": self.models[model_name][version_name]["creation_time"],
                "update_time": self.models[model_name][version_name]["update_time"],
                "author": self.models[model_name][version_name]["author"],
                "data": self.models[model_name][version_name]["data"],
                "previous_version": self.models[model_name][version_name].get("previous_version"),
                "changes_description": self.models[model_name][version_name].get("changes_description")
            }
        return None
    
    def list_models(self) -> List[Dict[str, str]]:
        """列出所有可用模型及其版本"""
        result = []
        for model_name, versions in self.models.items():
            for version_name in versions:
                result.append({
                    "model_name": model_name,
                    "version": version_name,
                    "update_time": versions[version_name]["update_time"]
                })
        return result
    
    def save_state(self) -> None:
        """保存当前状态到文件"""
        state = {
            "models": self.models,
            "current_model": self.current_model,
            "current_version": self.current_version,
            "timestamp": time.time()
        }
        
        try:
            with open(self.save_file, 'w') as f:
                json.dump(state, f, indent=4)
            self.logger.info(f"状态已保存到 {self.save_file}")
        except Exception as e:
            self.logger.error(f"保存状态失败: {str(e)}")
    
    def load_state(self) -> None:
        """从文件加载保存的状态"""
        # 首先加载模型列表
        self.load_all_models()
        
        if os.path.exists(self.save_file):
            try:
                with open(self.save_file, 'r') as f:
                    state = json.load(f)
                
                self.models = state.get("models", {})
                self.current_model = state.get("current_model")
                self.current_version = state.get("current_version")
                self.logger.info(f"已从 {self.save_file} 加载状态")
            except Exception as e:
                self.logger.error(f"加载状态失败: {str(e)}")
        else:
            self.logger.info(f"保存文件 {self.save_file} 不存在，使用默认设置")
    
    def save_model(self, model_name: str, version_name: str) -> None:
        """
        将模型保存到文件
        
        Args:
            model_name: 模型名称
            version_name: 版本名称
        """
        if model_name in self.models and version_name in self.models[model_name]:
            model_data = self.models[model_name][version_name]
            model_file = os.path.join(self.ai_models_dir, f"{model_name}_{version_name}.json")
            
            try:
                # 确保目录存在
                self._ensure_directory_exists(self.ai_models_dir)
                
                with open(model_file, 'w') as f:
                    json.dump(model_data, f, indent=4)
                self.logger.info(f"模型 {model_name} (版本: {version_name}) 已保存到 {model_file}")
            except Exception as e:
                self.logger.error(f"保存模型失败: {str(e)}")
    
    def load_all_models(self) -> None:
        """从目录加载所有模型"""
        self.models = {}
        
        if not os.path.exists(self.ai_models_dir):
            self._ensure_directory_exists(self.ai_models_dir)
            return
            
        self.logger.info(f"从 {self.ai_models_dir} 加载模型")
        
        try:
            for filename in os.listdir(self.ai_models_dir):
                if filename.endswith(".json"):
                    try:
                        # 解析模型名称和版本
                        parts = filename[:-5].split('_')
                        if len(parts) < 2:
                            self.logger.warning(f"文件名格式不正确: {filename}，跳过")
                            continue
                            
                        model_name = '_'.join(parts[:-1])
                        version_name = parts[-1]
                        
                        # 读取模型文件
                        model_path = os.path.join(self.ai_models_dir, filename)
                        with open(model_path, 'r') as f:
                            model_data = json.load(f)
                            
                        # 验证基本结构
                        if not isinstance(model_data, dict):
                            self.logger.warning(f"模型文件 {filename} 格式不正确，跳过")
                            continue
                            
                        if "version" not in model_data or "data" not in model_data:
                            self.logger.warning(f"模型文件 {filename} 缺少必要字段，跳过")
                            continue
                            
                        # 确保版本号匹配
                        if model_data["version"] != version_name:
                            self.logger.warning(f"模型文件 {filename} 版本号不匹配（文件中: {model_data['version']}，文件名: {version_name}），跳过")
                            continue
                            
                        # 添加到模型字典
                        if model_name not in self.models:
                            self.models[model_name] = {}
                            
                        self.models[model_name][version_name] = model_data
                        self.logger.info(f"已加载模型: {model_name} (版本: {version_name})")
                        
                    except Exception as e:
                        self.logger.error(f"加载模型文件 {filename} 失败: {str(e)}")
        except Exception as e:
            self.logger.error(f"扫描模型目录 {self.ai_models_dir} 失败: {str(e)}")
    
    def run_adb_command(self, command: str) -> Tuple[bool, str]:
        """
        运行ADB命令
        
        Args:
            command: ADB命令
            
        Returns:
            命令执行是否成功，命令输出
        """
        for adb_path in self.adb_paths:
            try:
                full_command = f"{adb_path} -s {self.emulator_addr} {command}"
                result = subprocess.run(full_command, shell=True, capture_output=True, text=True)
                
                if result.returncode != 0:
                    self.logger.warning(f"ADB命令失败: {full_command}")
                    self.logger.warning(f"错误输出: {result.stderr}")
                    continue
                
                self.logger.debug(f"ADB命令成功: {full_command}")
                return True, result.stdout
            except Exception as e:
                self.logger.warning(f"使用ADB路径 {adb_path} 执行命令失败: {str(e)}")
        
        self.logger.error("所有ADB路径尝试失败")
        return False, ""
    
    def connect_emulator(self) -> bool:
        """连接到模拟器"""
        success, output = self.run_adb_command("connect")
        if success:
            self.logger.info(f"已连接到模拟器 {self.emulator_addr}")
            return True
        else:
            self.logger.error(f"连接模拟器失败: {output}")
            return False
    
    def capture_screen(self) -> Optional[np.ndarray]:
        """
        捕获模拟器屏幕
        
        Returns:
            屏幕图像的numpy数组，如果失败则返回None
        """
        success, output = self.run_adb_command("shell screencap -p /sdcard/screenshot.png")
        if not success:
            self.logger.error("截图失败")
            return None
            
        success, output = self.run_adb_command("pull /sdcard/screenshot.png .")
        if not success:
            self.logger.error("下载截图失败")
            return None
            
        try:
            img = cv2.imread("screenshot.png")
            return img
        except Exception as e:
            self.logger.error(f"读取截图失败: {str(e)}")
            return None
    
    def tap(self, x: int, y: int, duration: int = 50) -> bool:
        """
        点击屏幕上的指定位置
        
        Args:
            x: X坐标
            y: Y坐标
            duration: 点击持续时间（毫秒）
            
        Returns:
            是否成功执行点击
        """
        success, _ = self.run_adb_command(f"shell input swipe {x} {y} {x} {y} {duration}")
        if success:
            self.logger.debug(f"点击坐标 ({x}, {y})")
        return success
    
    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: int = 300) -> bool:
        """
        从一点滑动到另一点
        
        Args:
            x1: 起点X坐标
            y1: 起点Y坐标
            x2: 终点X坐标
            y2: 终点Y坐标
            duration: 滑动持续时间（毫秒）
            
        Returns:
            是否成功执行滑动
        """
        success, _ = self.run_adb_command(f"shell input swipe {x1} {y1} {x2} {y2} {duration}")
        if success:
            self.logger.debug(f"从 ({x1}, {y1}) 滑动到 ({x2}, {y2})，持续时间 {duration}ms")
        return success
    
    def detect_enemies(self, image: np.ndarray) -> List[Dict[str, Any]]:
        """
        检测图像中的敌人
        
        Args:
            image: 屏幕图像
            
        Returns:
            敌人信息列表，每个元素包含位置和类型
        """
        if image is None:
            return []
            
        # 这里应该是实际的目标检测算法
        # 简化版本，仅返回随机生成的"敌人"位置
        height, width = image.shape[:2]
        num_enemies = random.randint(0, 5)
        
        enemies = []
        for _ in range(num_enemies):
            x = random.randint(100, width - 100)
            y = random.randint(100, height - 100)
            enemy_type = random.choice(["普通敌人", "精英敌人", "BOSS"])
            
            enemies.append({
                "x": x,
                "y": y,
                "type": enemy_type,
                "confidence": round(random.uniform(0.6, 0.99), 2)
            })
            
        return enemies
    
    def detect_player(self, image: np.ndarray) -> Optional[Dict[str, int]]:
        """
        检测玩家位置
        
        Args:
            image: 屏幕图像
            
        Returns:
            玩家位置，如果未找到则返回None
        """
        if image is None:
            return None
            
        # 这里应该是实际的玩家检测算法
        # 简化版本，返回屏幕中心作为玩家位置
        height, width = image.shape[:2]
        
        return {
            "x": width // 2,
            "y": height // 2
        }
    
    def detect_weapon(self, image: np.ndarray) -> Optional[str]:
        """
        检测当前装备的武器
        
        Args:
            image: 屏幕图像
            
        Returns:
            武器类型，如果未找到则返回None
        """
        if image is None:
            return None
            
        # 这里应该是实际的武器检测算法
        # 简化版本，随机返回一种武器类型
        return random.choice(["pistol", "shotgun", "sword", "rifle", "magic wand"])
    
    def select_best_weapon(self, available_weapons: List[str]) -> Optional[str]:
        """
        根据武器优先级选择最佳武器
        
        Args:
            available_weapons: 可用武器列表
            
        Returns:
            最佳武器类型，如果没有可用武器则返回None
        """
        if not available_weapons or not self.current_model or not self.current_version:
            return None
            
        weapon_priority = self.models[self.current_model][self.current_version]["data"].get(
            "weapon_priority", ["shotgun", "sword", "pistol", "rifle", "magic wand"]
        )
        
        for weapon in weapon_priority:
            if weapon in available_weapons:
                return weapon
                
        # 如果没有匹配优先级的武器，返回第一个可用武器
        return available_weapons[0] if available_weapons else None
    
    def switch_weapon(self, target_weapon: str) -> bool:
        """
        切换到指定武器
        
        Args:
            target_weapon: 目标武器类型
            
        Returns:
            是否成功切换武器
        """
        if not self.current_model or not self.current_version:
            self.logger.error("没有选择模型，无法执行武器切换")
            return False
            
        can_switch = self.models[self.current_model][self.current_version]["data"].get(
            "can_switch_weapon", True
        )
        
        if not can_switch:
            self.logger.info("当前模型设置不允许切换武器")
            return False
            
        # 这里应该是实际的切换武器操作
        # 简化版本，模拟切换武器
        self.logger.info(f"尝试切换到武器: {target_weapon}")
        
        # 随机模拟切换成功或失败
        success = random.choice([True, False])
        
        if success:
            self.logger.info(f"成功切换到武器: {target_weapon}")
        else:
            self.logger.warning(f"切换武器失败: {target_weapon}")
            
        return success
    
    def attack_enemy(self, enemy_pos: Dict[str, int]) -> bool:
        """
        攻击指定位置的敌人
        
        Args:
            enemy_pos: 敌人位置
            
        Returns:
            是否成功执行攻击
        """
        x, y = enemy_pos.get("x", 0), enemy_pos.get("y", 0)
        success = self.tap(x, y)
        
        if success:
            self.logger.info(f"攻击敌人位置 ({x}, {y})")
        else:
            self.logger.warning(f"攻击失败: 位置 ({x}, {y})")
            
        return success
    
    def move_to(self, x: int, y: int, duration: int = 800) -> bool:
        """
        移动到指定位置
        
        Args:
            x: 目标X坐标
            y: 目标Y坐标
            duration: 移动持续时间（毫秒）
            
        Returns:
            是否成功执行移动
        """
        if not self.current_model or not self.current_version:
            self.logger.error("没有选择模型，无法执行移动")
            return False
            
        # 获取模型中的移动速度设置
        move_speed = self.models[self.current_model][self.current_version]["data"].get(
            "move_speed", 1.0
        )
        
        # 根据速度调整移动持续时间
        adjusted_duration = int(duration / move_speed)
        
        # 获取玩家当前位置
        screen = self.capture_screen()
        player = self.detect_player(screen)
        
        if not player:
            self.logger.warning("无法检测到玩家位置，使用屏幕中心作为默认位置")
            height, width = screen.shape[:2] if screen is not None else (640, 480)
            player = {"x": width // 2, "y": height // 2}
            
        # 模拟从玩家当前位置滑动到目标位置
        success = self.swipe(player["x"], player["y"], x, y, adjusted_duration)
        
        if success:
            self.logger.info(f"移动到位置 ({x}, {y})，速度: {move_speed}x")
        else:
            self.logger.warning(f"移动失败: 目标位置 ({x}, {y})")
            
        return success
    
    def use_skill(self) -> bool:
        """使用角色技能"""
        if not self.current_model or not self.current_version:
            self.logger.error("没有选择模型，无法使用技能")
            return False
            
        # 获取模型中的技能使用阈值设置
        skill_threshold = self.models[self.current_model][self.current_version]["data"].get(
            "skill_usage_threshold", 0.8
        )
        
        # 随机决定是否使用技能（模拟满足阈值条件）
        should_use = random.random() >= (1 - skill_threshold)
        
        if not should_use:
            self.logger.info(f"根据阈值 {skill_threshold}，决定不使用技能")
            return False
            
        # 模拟点击技能按钮
        screen = self.capture_screen()
        if screen is None:
            return False
            
        height, width = screen.shape[:2]
        
        # 假设技能按钮在屏幕右下角
        skill_x = width - 100
        skill_y = height - 100
        
        success = self.tap(skill_x, skill_y)
        
        if success:
            self.logger.info(f"使用角色技能，阈值: {skill_threshold}")
        else:
            self.logger.warning("技能使用失败")
            
        return success
    
    def run_battle(self) -> None:
        """运行战斗AI"""
        if not self.current_model or not self.current_version:
            self.logger.error("没有选择模型，无法运行战斗AI")
            return
            
        duration = 60  # 默认持续时间60秒
        
        self.logger.info(f"开始战斗AI，使用模型: {self.current_model} (版本: {self.current_version})")
        self.logger.info(f"战斗将持续 {duration} 秒")
        
        start_time = time.time()
        last_weapon_switch_time = 0
        weapon_switch_interval = 10  # 武器切换间隔（秒）
        
        while time.time() - start_time < duration:
            # 捕获屏幕
            screen = self.capture_screen()
            if screen is None:
                self.logger.warning("无法捕获屏幕，跳过此帧")
                time.sleep(0.5)
                continue
                
            # 检测玩家位置
            player = self.detect_player(screen)
            if not player:
                self.logger.warning("无法检测到玩家位置")
            
            # 检测敌人
            enemies = self.detect_enemies(screen)
            self.logger.debug(f"检测到 {len(enemies)} 个敌人")
            
            # 如果有敌人，选择最近的敌人攻击
            if enemies:
                closest_enemy = min(
                    enemies, 
                    key=lambda e: ((e["x"] - player["x"]) ** 2 + (e["y"] - player["y"]) ** 2) ** 0.5
                )
                
                # 检测当前武器
                current_weapon = self.detect_weapon(screen)
                self.logger.debug(f"当前武器: {current_weapon}")
                
                # 根据时间间隔决定是否尝试切换武器
                current_time = time.time()
                if current_time - last_weapon_switch_time > weapon_switch_interval:
                    # 获取模型中的武器优先级
                    weapon_priority = self.models[self.current_model][self.current_version]["data"].get(
                        "weapon_priority", ["shotgun", "sword", "pistol"]
                    )
                    
                    # 假设我们有所有类型的武器可用
                    available_weapons = ["pistol", "shotgun", "sword", "rifle", "magic wand"]
                    
                    # 选择最佳武器
                    best_weapon = self.select_best_weapon(available_weapons)
                    
                    if best_weapon and best_weapon != current_weapon:
                        self.switch_weapon(best_weapon)
                        last_weapon_switch_time = current_time
                
                # 移动到敌人附近
                move_x = closest_enemy["x"] + random.randint(-50, 50)
                move_y = closest_enemy["y"] + random.randint(-50, 50)
                self.move_to(move_x, move_y)
                
                # 攻击敌人
                self.attack_enemy(closest_enemy)
                
                # 有概率使用技能
                if random.random() < 0.2:
                    self.use_skill()
            
            # 随机移动（探索）
            if not enemies or random.random() < 0.3:
                screen = self.capture_screen()
                if screen is not None:
                    height, width = screen.shape[:2]
                    random_x = random.randint(100, width - 100)
                    random_y = random.randint(100, height - 100)
                    self.move_to(random_x, random_y)
            
            # 等待一段时间再继续下一帧
            time.sleep(0.5)
            
        self.logger.info("战斗AI已停止")


class SoulKnightAIGUI:
    def __init__(self, root: tk.Tk, ai: SoulKnightAI):
        """初始化元气骑士AI图形界面"""
        self.root = root
        self.root.title("元气骑士AI - 模型设置")
        self.root.geometry("800x600")
        
        self.ai = ai
        self.selected_model = tk.StringVar()
        self.selected_version = tk.StringVar()
        self.model_data_vars = {}
        
        # 创建主框架
        main_frame = ttk.Frame(root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 左侧面板 - 模型列表
        left_frame = ttk.LabelFrame(main_frame, text="模型列表", padding="10")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 模型选择下拉框
        ttk.Label(left_frame, text="选择模型:").pack(anchor=tk.W)
        self.model_combo = ttk.Combobox(left_frame, textvariable=self.selected_model, state="readonly")
        self.model_combo.pack(fill=tk.X, pady=5)
        self.model_combo.bind("<<ComboboxSelected>>", self.on_model_selected)
        
        # 版本选择下拉框
        ttk.Label(left_frame, text="选择版本:").pack(anchor=tk.W)
        self.version_combo = ttk.Combobox(left_frame, textvariable=self.selected_version, state="readonly")
        self.version_combo.pack(fill=tk.X, pady=5)
        self.version_combo.bind("<<ComboboxSelected>>", self.on_version_selected)
        
        # 模型操作按钮
        button_frame = ttk.Frame(left_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(button_frame, text="新建模型", command=self.create_new_model_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="更改版本号", command=self.change_version_number_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="应用模型", command=self.apply_model).pack(side=tk.LEFT, padx=5)
        
        # 刷新按钮
        ttk.Button(left_frame, text="刷新模型列表", command=self.refresh_model_list).pack(fill=tk.X, pady=5)
        
        # 右侧面板 - 模型设置
        right_frame = ttk.LabelFrame(main_frame, text="模型设置", padding="10")
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 设置滚动条
        canvas = tk.Canvas(right_frame)
        scrollbar = ttk.Scrollbar(right_frame, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(
                scrollregion=canvas.bbox("all")
            )
        )
        
        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # 底部按钮
        bottom_frame = ttk.Frame(root, padding="10")
        bottom_frame.pack(fill=tk.X)
        
        ttk.Button(bottom_frame, text="保存设置", command=self.save_settings).pack(side=tk.RIGHT, padx=5)
        ttk.Button(bottom_frame, text="运行战斗", command=self.run_battle).pack(side=tk.RIGHT, padx=5)
        
        # 初始化模型列表
        self.update_model_list()
        
        # 如果有模型，选择第一个
        if self.ai.models:
            first_model = list(self.ai.models.keys())[0]
            self.selected_model.set(first_model)
            self.on_model_selected(None)
            
            first_version = list(self.ai.models[first_model].keys())[0]
            self.selected_version.set(first_version)
            self.on_version_selected(None)
    
    def update_model_list(self) -> None:
        """更新模型和版本列表"""
        models = list(self.ai.models.keys())
        self.model_combo['values'] = models
        
        if self.selected_model.get() in models:
            self.model_combo.set(self.selected_model.get())
        elif models:
            self.model_combo.set(models[0])
            self.selected_model.set(models[0])
    
    def refresh_model_list(self) -> None:
        """刷新模型列表，从磁盘重新加载"""
        self.ai.load_all_models()
        self.update_model_list()
        messagebox.showinfo("成功", "模型列表已刷新")
    
    def on_model_selected(self, event) -> None:
        """模型选择变化时更新版本列表"""
        model_name = self.selected_model.get()
        if model_name in self.ai.models:
            versions = list(self.ai.models[model_name].keys())
            self.version_combo['values'] = versions
            
            if self.selected_version.get() in versions:
                self.version_combo.set(self.selected_version.get())
            elif versions:
                self.version_combo.set(versions[0])
                self.selected_version.set(versions[0])
                self.on_version_selected(None)
    
    def on_version_selected(self, event) -> None:
        """版本选择变化时更新设置面板"""
        model_name = self.selected_model.get()
        version_name = self.selected_version.get()
        
        if model_name and version_name and model_name in self.ai.models and version_name in self.ai.models[model_name]:
            # 清空设置面板
            for widget in self.scrollable_frame.winfo_children():
                widget.destroy()
            
            # 获取模型数据
            model_data = self.ai.models[model_name][version_name]["data"]
            
            # 创建设置项
            row = 0
            
            # 武器切换设置
            ttk.Label(self.scrollable_frame, text="允许切换武器:").grid(row=row, column=0, sticky=tk.W, pady=5)
            self.model_data_vars["can_switch_weapon"] = tk.BooleanVar(value=model_data.get("can_switch_weapon", True))
            ttk.Checkbutton(self.scrollable_frame, variable=self.model_data_vars["can_switch_weapon"]).grid(row=row, column=1, sticky=tk.W, pady=5)
            row += 1
    
    def create_new_model_dialog(self) -> None:
        """创建新模型对话框"""
        dialog = tk.Toplevel(self.root)
        dialog.title("创建新模型")
        dialog.geometry("300x200")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="模型名称:").pack(pady=10)
        model_name_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=model_name_var).pack(fill=tk.X, padx=20)
        
        ttk.Label(dialog, text="版本名称:").pack(pady=10)
        version_name_var = tk.StringVar(value="v1.0.0")
        ttk.Entry(dialog, textvariable=version_name_var).pack(fill=tk.X, padx=20)
        
        button_frame = ttk.Frame(dialog)
        button_frame.pack(fill=tk.X, pady=20, padx=20)
        
        def create_model():
            model_name = model_name_var.get().strip()
            version_name = version_name_var.get().strip()
            
            if not model_name:
                messagebox.showerror("错误", "模型名称不能为空")
                return
                
            self.ai.create_new_model(model_name, version_name)
            self.update_model_list()
            self.selected_model.set(model_name)
            self.on_model_selected(None)
            self.selected_version.set(version_name)
            self.on_version_selected(None)
            
            dialog.destroy()
        
        ttk.Button(button_frame, text="创建", command=create_model).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="取消", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)
    
    def change_version_number_dialog(self) -> None:
        """更改版本号对话框"""
        model_name = self.selected_model.get()
        version_name = self.selected_version.get()
        
        if not model_name or not version_name or model_name not in self.ai.models or version_name not in self.ai.models[model_name]:
            messagebox.showerror("错误", "请先选择一个模型和版本")
            return
            
        dialog = tk.Toplevel(self.root)
        dialog.title("更改版本号")
        dialog.geometry("300x150")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="当前版本:").pack(pady=10)
        ttk.Label(dialog, text=version_name).pack(pady=5)
        
        ttk.Label(dialog, text="新版本号:").pack(pady=10)
        new_version_var = tk.StringVar(value="v1.0.1")
        ttk.Entry(dialog, textvariable=new_version_var).pack(fill=tk.X, padx=20)
        
        button_frame = ttk.Frame(dialog)
        button_frame.pack(fill=tk.X, pady=20, padx=20)
        
        def change_version():
            new_version = new_version_var.get().strip()
            
            if not new_version:
                messagebox.showerror("错误", "版本名称不能为空")
                return
                
            if self.ai.change_version_number(model_name, version_name, new_version):
                self.on_model_selected(None)
                self.selected_version.set(new_version)
                self.on_version_selected(None)
                dialog.destroy()
            else:
                messagebox.showerror("错误", f"更改版本号失败，可能版本 {new_version} 已存在")
    
        ttk.Button(button_frame, text="更改", command=change_version).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="取消", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)
    
    def apply_model(self) -> None:
        """应用选中的模型"""
        model_name = self.selected_model.get()
        version_name = self.selected_version.get()
        
        if model_name and version_name and model_name in self.ai.models and version_name in self.ai.models[model_name]:
            if self.ai.select_model(model_name, version_name):
                messagebox.showinfo("成功", f"已应用模型: {model_name} (版本: {version_name})")
            else:
                messagebox.showerror("错误", f"应用模型失败: {model_name} (版本: {version_name})")
        else:
            messagebox.showerror("错误", "请选择有效的模型和版本")
    
    def save_settings(self) -> None:
        """保存模型设置"""
        model_name = self.selected_model.get()
        version_name = self.selected_version.get()
        
        if not model_name or not version_name or model_name not in self.ai.models or version_name not in self.ai.models[model_name]:
            messagebox.showerror("错误", "请先选择一个模型和版本")
            return
            
        # 收集设置数据
        new_data = {}
        
        # 收集布尔值设置
        if "can_switch_weapon" in self.model_data_vars:
            new_data["can_switch_weapon"] = self.model_data_vars["can_switch_weapon"].get()
            
        # 更新模型数据
        if self.ai.update_model_data(model_name, version_name, new_data):
            messagebox.showinfo("成功", "模型设置已保存")
        else:
            messagebox.showerror("错误", "保存模型设置失败")
    
    def run_battle(self) -> None:
        """运行战斗AI"""
        if not self.ai.current_model or not self.ai.current_version:
            messagebox.showerror("错误", "请先选择并应用一个模型")
            return
            
        # 在单独的线程中运行战斗AI
        battle_thread = threading.Thread(target=self.ai.run_battle)
        battle_thread.daemon = True
        battle_thread.start()


if __name__ == "__main__":
    # 创建AI实例
    ai = SoulKnightAI()
    
    # 创建GUI
    root = tk.Tk()
    app = SoulKnightAIGUI(root, ai)
    root.mainloop()    