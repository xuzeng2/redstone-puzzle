#!/usr/bin/env python3
"""
红石电路模拟器 - 关卡设计工具
用于可视化设计和测试红石电路，并导出为关卡JSON
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import threading
from typing import List, Dict, Any, Optional, Tuple

# ============================================================
# 常量定义
# ============================================================
CELL = 44
TICK_MS = 120

DIRECTIONS = [
    {"dx": 1, "dy": 0},   # 0: 右
    {"dx": 0, "dy": 1},   # 1: 下
    {"dx": -1, "dy": 0},  # 2: 左
    {"dx": 0, "dy": -1},  # 3: 上
]

DIR_NAMES = ["→", "↓", "←", "↑"]

COMP_NAMES = {
    'dust': '红石粉',
    'block': '红石块',
    'torch': '红石火把',
    'repeater': '中继器',
    'comparator': '比较器',
    'observer': '侦测器',
}

ALL_COMPONENTS = ['dust', 'block', 'torch', 'repeater', 'comparator', 'observer']
PLACEABLE_COMPONENTS = ALL_COMPONENTS


class CircuitSimulator:
    """红石电路模拟器核心"""
    
    def __init__(self, cols: int = 14, rows: int = 9):
        self.cols = cols
        self.rows = rows
        self.grid: List[List[Dict]] = []
        self.signals: List[List[int]] = []
        self.tick = 0
        self.running = False
        self.timer = None
        self.input_active = False
        self.input_remaining = 0
        self.input_states = []
        self.output_powered = False
        self.output_arrival_tick = -1
        self.output_departure_tick = -1
        self.output_delay = -1
        self.output_duration = 0
        self.output_max_strength = 0
        self.signal_callback = None
        self.input_config = None
        self.inputs_config = None
        self.output_config = None
        self.target_delay = 0
        self.target_duration = 0
        self.target_strength = None
        self.anim_frame = 0
        self._init_grid()
    
    def _init_grid(self):
        self.grid = []
        self.signals = []
        for x in range(self.cols):
            self.grid.append([])
            self.signals.append([])
            for y in range(self.rows):
                self.grid[x].append({
                    'type': 'empty',
                    'direction': 0,
                    'delay': 1,
                    'mode': 'compare',
                    'output_active': False,
                    'prev_input': False,
                    'event_queue': [],
                    'extinguished': False,
                    'pulsing': False,
                    'pulse_timer': 0,
                    'prev_front_signal': 0,
                    'output_strength': 0,
                    'cooldown': 0,
                })
                self.signals[x].append(0)
    
    def set_input(self, x: int, y: int, duration: int = 10, strength: int = 15):
        self.input_config = {'x': x, 'y': y, 'duration': duration, 'strength': strength}
        self.inputs_config = None
        self.grid[x][y]['type'] = 'input'
    
    def set_inputs(self, inputs: List[Dict]):
        self.inputs_config = inputs
        self.input_config = None
        self.input_states = []
        for inp in inputs:
            self.grid[inp['x']][inp['y']]['type'] = 'input'
            self.input_states.append({
                'x': inp['x'],
                'y': inp['y'],
                'duration': inp['duration'],
                'delay': inp.get('delay', 0),
                'orig_delay': inp.get('delay', 0),
                'strength': inp.get('strength', 15),
                'remaining': 0,
                'active': False,
            })
    
    def set_output(self, x: int, y: int):
        self.output_config = {'x': x, 'y': y}
        self.grid[x][y]['type'] = 'output'
    
    def set_target(self, delay: int, duration: int, strength: int = None):
        self.target_delay = delay
        self.target_duration = duration
        self.target_strength = strength
    
    def place_component(self, x: int, y: int, comp_type: str, direction: int = 0, delay: int = 1, mode: str = 'compare'):
        if x < 0 or x >= self.cols or y < 0 or y >= self.rows:
            return False
        if self.grid[x][y]['type'] not in ['empty']:
            return False
        self.grid[x][y]['type'] = comp_type
        self.grid[x][y]['direction'] = direction
        self.grid[x][y]['delay'] = delay
        self.grid[x][y]['mode'] = mode
        self.grid[x][y]['output_active'] = False
        self.grid[x][y]['prev_input'] = False
        self.grid[x][y]['event_queue'] = []
        self.grid[x][y]['extinguished'] = False
        self.grid[x][y]['pulsing'] = False
        self.grid[x][y]['pulse_timer'] = 0
        self.grid[x][y]['prev_front_signal'] = 0
        self.grid[x][y]['output_strength'] = 0
        self.grid[x][y]['cooldown'] = 0
        return True
    
    def remove_component(self, x: int, y: int):
        if x < 0 or x >= self.cols or y < 0 or y >= self.rows:
            return False
        if self.grid[x][y]['type'] in ['input', 'output']:
            return False
        self.grid[x][y]['type'] = 'empty'
        self.grid[x][y]['direction'] = 0
        self.grid[x][y]['delay'] = 1
        self.grid[x][y]['mode'] = 'compare'
        return True
    
    def clear_all(self):
        for x in range(self.cols):
            for y in range(self.rows):
                if self.grid[x][y]['type'] not in ['input', 'output']:
                    self.grid[x][y]['type'] = 'empty'
                    self.grid[x][y]['direction'] = 0
                    self.grid[x][y]['delay'] = 1
                    self.grid[x][y]['mode'] = 'compare'
    
    def get_layout(self) -> List[Dict]:
        layout = []
        for x in range(self.cols):
            for y in range(self.rows):
                cell = self.grid[x][y]
                if cell['type'] not in ['empty', 'input', 'output']:
                    layout.append({
                        'x': x, 'y': y,
                        'type': cell['type'],
                        'direction': cell['direction'],
                        'delay': cell['delay'],
                        'mode': cell['mode'],
                    })
        return layout
    
    def apply_layout(self, layout: List[Dict]):
        for x in range(self.cols):
            for y in range(self.rows):
                if self.grid[x][y]['type'] not in ['input', 'output']:
                    self.grid[x][y]['type'] = 'empty'
                    self.grid[x][y]['direction'] = 0
                    self.grid[x][y]['delay'] = 1
                    self.grid[x][y]['mode'] = 'compare'
        
        for item in layout:
            self.place_component(
                item['x'], item['y'],
                item['type'],
                item.get('direction', 0),
                item.get('delay', 1),
                item.get('mode', 'compare')
            )
    
    # ============================================================
    # 信号传播逻辑
    # ============================================================
    
    def _is_signal_source(self, cell):
        return cell['type'] in ['block', 'torch', 'repeater', 'comparator', 'observer', 'input']
    
    def _is_conductive(self, cell):
        return cell['type'] in ['dust', 'block', 'torch', 'repeater', 'comparator', 'observer', 'input']
    
    def _is_directional_source(self, cell):
        return cell['type'] in ['repeater', 'comparator', 'observer', 'torch']
    
    def _get_output_dir(self, cell):
        d = DIRECTIONS[cell['direction']]
        if cell['type'] == 'observer':
            return {'dx': -d['dx'], 'dy': -d['dy']}
        return d
    
    def _get_neighbor_signal(self, nx: int, ny: int, x: int, y: int) -> int:
        if nx < 0 or nx >= self.cols or ny < 0 or ny >= self.rows:
            return 0
        n = self.grid[nx][ny]
        if not self._is_conductive(n):
            return 0
        if self._is_directional_source(n):
            o = self._get_output_dir(n)
            if nx + o['dx'] != x or ny + o['dy'] != y:
                return 0
        return self.signals[nx][ny]
    
    def _get_input_signal(self, x: int, y: int, dir_vec: Dict) -> int:
        ix = x - dir_vec['dx']
        iy = y - dir_vec['dy']
        if ix < 0 or ix >= self.cols or iy < 0 or iy >= self.rows:
            return 0
        n = self.grid[ix][iy]
        if not self._is_conductive(n):
            return 0
        if self._is_directional_source(n):
            o = self._get_output_dir(n)
            if ix + o['dx'] != x or iy + o['dy'] != y:
                return 0
        return self.signals[ix][iy]
    
    def _get_output_power(self, cell, x: int, y: int) -> int:
        t = cell['type']
        if t == 'block':
            return 15
        if t == 'input':
            if self.input_states:
                for s in self.input_states:
                    if s['x'] == x and s['y'] == y:
                        return s['strength'] if s['active'] else 0
                return 0
            return self.input_config['strength'] if self.input_active else 0
        if t == 'torch':
            return 0 if cell['extinguished'] else 15
        if t == 'repeater':
            return 15 if cell['output_active'] else 0
        if t == 'comparator':
            return cell['output_strength'] if cell['output_active'] else 0
        if t == 'observer':
            return 15 if cell['pulsing'] else 0
        return 0
    
    def tick_update(self):
        self.anim_frame += 1
        
        if self.input_states:
            for s in self.input_states:
                if s['delay'] > 0:
                    s['delay'] -= 1
                    s['active'] = False
                elif s['remaining'] > 0:
                    s['active'] = True
                    s['remaining'] -= 1
                else:
                    s['active'] = False
            self.input_active = any(s['active'] for s in self.input_states)
        else:
            if self.input_remaining > 0:
                self.input_active = True
                self.input_remaining -= 1
            else:
                self.input_active = False
        
        for x in range(self.cols):
            for y in range(self.rows):
                cell = self.grid[x][y]
                t = cell['type']
                
                if t == 'repeater':
                    d = DIRECTIONS[cell['direction']]
                    ip = self._get_input_signal(x, y, d) > 0
                    if ip and not cell['prev_input']:
                        cell['event_queue'].append({'tick': self.tick + cell['delay'], 'state': True})
                    if not ip and cell['prev_input']:
                        cell['event_queue'].append({'tick': self.tick + cell['delay'], 'state': False})
                    cell['prev_input'] = ip
                    while cell['event_queue'] and cell['event_queue'][0]['tick'] <= self.tick:
                        cell['output_active'] = cell['event_queue'].pop(0)['state']
                
                elif t == 'torch':
                    d = DIRECTIONS[cell['direction']]
                    cell['extinguished'] = self._get_input_signal(x, y, d) > 0
                
                elif t == 'comparator':
                    d = DIRECTIONS[cell['direction']]
                    mp = self._get_input_signal(x, y, d)
                    sp = 0
                    side_dirs = [
                        {'dx': d['dy'], 'dy': d['dx']},
                        {'dx': -d['dy'], 'dy': -d['dx']},
                    ]
                    for p in side_dirs:
                        sx = x + p['dx']
                        sy = y + p['dy']
                        if 0 <= sx < self.cols and 0 <= sy < self.rows:
                            ns = self._get_neighbor_signal(sx, sy, x, y)
                            if ns > sp:
                                sp = ns
                    if cell['mode'] == 'compare':
                        if mp >= sp and mp > 0:
                            cell['output_active'] = True
                            cell['output_strength'] = mp
                        else:
                            cell['output_active'] = False
                            cell['output_strength'] = 0
                    else:
                        r = max(0, mp - sp)
                        cell['output_active'] = r > 0
                        cell['output_strength'] = r
                
                elif t == 'observer':
                    d = DIRECTIONS[cell['direction']]
                    fx = x + d['dx']
                    fy = y + d['dy']
                    fs = 0
                    if 0 <= fx < self.cols and 0 <= fy < self.rows:
                        fs = self.signals[fx][fy] or 0
                    if fs > 0 and cell['prev_front_signal'] == 0:
                        cell['pulsing'] = True
                        cell['pulse_timer'] = 2
                    elif cell['pulse_timer'] > 0:
                        cell['pulse_timer'] -= 1
                        if cell['pulse_timer'] <= 0:
                            cell['pulsing'] = False
                    cell['prev_front_signal'] = fs
        
        new_sig = []
        for x in range(self.cols):
            new_sig.append([])
            for y in range(self.rows):
                new_sig[x].append(0)
                cell = self.grid[x][y]
                
                if self._is_signal_source(cell):
                    new_sig[x][y] = self._get_output_power(cell, x, y)
                
                elif cell['type'] == 'dust':
                    prev_sig = self.signals[x][y]
                    if cell['cooldown'] > 0:
                        cell['cooldown'] -= 1
                        new_sig[x][y] = 0
                    elif prev_sig > 0:
                        mx = 0
                        for i in range(4):
                            d = DIRECTIONS[i]
                            nx = x + d['dx']
                            ny = y + d['dy']
                            if 0 <= nx < self.cols and 0 <= ny < self.rows:
                                s = self._get_neighbor_signal(nx, ny, x, y)
                                if s > mx:
                                    mx = s
                        if mx > prev_sig:
                            new_sig[x][y] = mx - 1
                        else:
                            new_sig[x][y] = 0
                            cell['cooldown'] = 2
                    else:
                        mx = 0
                        for i in range(4):
                            d = DIRECTIONS[i]
                            nx = x + d['dx']
                            ny = y + d['dy']
                            if 0 <= nx < self.cols and 0 <= ny < self.rows:
                                s = self._get_neighbor_signal(nx, ny, x, y)
                                if s > mx:
                                    mx = s
                        new_sig[x][y] = mx - 1 if mx > 0 else 0
        
        self.signals = new_sig
        self._check_output()
        self.tick += 1
        
        if self.input_config:
            max_duration = self.input_config['duration']
        else:
            max_duration = max(s['duration'] + s.get('delay', 0) for s in self.input_states) if self.input_states else 0
        
        if not self.input_active and self.tick > max_duration + 10:
            any_signal = any(self.signals[x][y] > 0 for x in range(self.cols) for y in range(self.rows))
            any_event = any(self.grid[x][y]['event_queue'] for x in range(self.cols) for y in range(self.rows))
            if not any_signal and not any_event and not self.output_powered:
                self.stop()
        
        if self.tick > max_duration + 50:
            self.stop()
    
    def _check_output(self):
        if not self.output_config:
            return
        out = self.output_config
        has_signal = False
        max_str = 0
        for d in DIRECTIONS:
            nx = out['x'] + d['dx']
            ny = out['y'] + d['dy']
            if 0 <= nx < self.cols and 0 <= ny < self.rows:
                if self.signals[nx][ny] > 0:
                    has_signal = True
                    if self.signals[nx][ny] > max_str:
                        max_str = self.signals[nx][ny]
        
        if has_signal and not self.output_powered:
            self.output_powered = True
            self.output_arrival_tick = self.tick
            self.output_delay = self.tick
            self.output_max_strength = max_str
        
        if has_signal and self.output_powered and max_str > self.output_max_strength:
            self.output_max_strength = max_str
        
        if not has_signal and self.output_powered:
            self.output_powered = False
            self.output_departure_tick = self.tick
            self.output_duration = self.output_departure_tick - self.output_arrival_tick
    
    def start(self):
        if self.running:
            return
        if self.tick == 0:
            if self.input_states:
                for s in self.input_states:
                    s['remaining'] = s['duration']
                    s['delay'] = s.get('orig_delay', 0)
                    s['active'] = False
            else:
                self.input_remaining = self.input_config['duration']
        self.running = True
        self._run_tick()
    
    def _run_tick(self):
        if not self.running:
            return
        self.tick_update()
        if self.signal_callback:
            self.signal_callback(self.signals, self.output_powered, self.output_delay, self.output_duration, self.output_max_strength)
        self.timer = threading.Timer(TICK_MS / 1000.0, self._run_tick)
        self.timer.daemon = True
        self.timer.start()
    
    def stop(self):
        self.running = False
        if self.timer:
            self.timer.cancel()
            self.timer = None
    
    def reset(self):
        self.stop()
        self.tick = 0
        self.input_active = False
        self.input_remaining = 0
        for s in self.input_states:
            s['remaining'] = 0
            s['active'] = False
            s['delay'] = 0
        self.output_powered = False
        self.output_arrival_tick = -1
        self.output_departure_tick = -1
        self.output_delay = -1
        self.output_duration = 0
        self.output_max_strength = 0
        self.anim_frame = 0
        for x in range(self.cols):
            for y in range(self.rows):
                self.signals[x][y] = 0
                cell = self.grid[x][y]
                cell['output_active'] = False
                cell['prev_input'] = False
                cell['event_queue'] = []
                cell['extinguished'] = False
                cell['pulsing'] = False
                cell['pulse_timer'] = 0
                cell['prev_front_signal'] = 0
                cell['output_strength'] = 0
                cell['cooldown'] = 0
    
    def step(self):
        if self.tick == 0:
            if self.input_states:
                for s in self.input_states:
                    s['remaining'] = s['duration']
                    s['delay'] = s.get('orig_delay', 0)
                    s['active'] = False
            else:
                self.input_remaining = self.input_config['duration']
        self.tick_update()
        if self.signal_callback:
            self.signal_callback(self.signals, self.output_powered, self.output_delay, self.output_duration, self.output_max_strength)
    
    def get_result(self) -> Dict:
        return {
            'delay': self.output_delay,
            'duration': self.output_duration,
            'strength': self.output_max_strength,
            'powered': self.output_powered,
            'tick': self.tick,
        }


class LevelData:
    """关卡数据管理"""
    def __init__(self):
        self.levels: List[Dict] = []
        self.current_index: int = 0
        self.filepath: Optional[str] = None
        self.modified: bool = False
    
    def add_level(self, level_data: Dict):
        self.levels.append(level_data)
        self.modified = True
    
    def insert_level(self, index: int, level_data: Dict):
        self.levels.insert(index, level_data)
        self.modified = True
    
    def remove_level(self, index: int):
        if len(self.levels) <= 1:
            return False
        self.levels.pop(index)
        if self.current_index >= len(self.levels):
            self.current_index = len(self.levels) - 1
        self.modified = True
        return True
    
    def get_level(self, index: int) -> Optional[Dict]:
        if 0 <= index < len(self.levels):
            return self.levels[index]
        return None
    
    def set_level(self, index: int, level_data: Dict):
        if 0 <= index < len(self.levels):
            self.levels[index] = level_data
            self.modified = True
    
    def load_from_file(self, filepath: str):
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if 'levels' in data:
            self.levels = data['levels']
        else:
            self.levels = [data]
        self.filepath = filepath
        self.modified = False
        self.current_index = 0
    
    def save_to_file(self, filepath: str):
        level_data = {'levels': self.levels}
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(level_data, f, ensure_ascii=False, indent=2)
        self.filepath = filepath
        self.modified = False
    
    def to_json(self) -> str:
        return json.dumps({'levels': self.levels}, ensure_ascii=False, indent=2)


class ComponentLimitDialog:
    """元件限制编辑对话框"""
    def __init__(self, parent, components: List[str], limits: Dict[str, int]):
        self.parent = parent
        self.components = components
        self.limits = limits.copy()
        self.result = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("元件限制设置")
        self.dialog.geometry("320x400")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self._create_ui()
    
    def _create_ui(self):
        main_frame = ttk.Frame(self.dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="设置每个元件的最大使用数量（0=禁用）", font=('', 10)).pack(pady=(0, 10))
        
        canvas_frame = ttk.Frame(main_frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        canvas = tk.Canvas(canvas_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)
        
        scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        self.entries = {}
        for comp in self.components:
            row = ttk.Frame(scroll_frame)
            row.pack(fill=tk.X, pady=3)
            
            label = ttk.Label(row, text=COMP_NAMES.get(comp, comp), width=10)
            label.pack(side=tk.LEFT, padx=2)
            
            var = tk.StringVar(value=str(self.limits.get(comp, 99)))
            entry = ttk.Entry(row, width=8, textvariable=var)
            entry.pack(side=tk.LEFT, padx=2)
            self.entries[comp] = var
            
            ttk.Button(row, text="∞", width=3, 
                      command=lambda c=comp: self.entries[c].set("99")).pack(side=tk.LEFT, padx=1)
            ttk.Button(row, text="0", width=3,
                      command=lambda c=comp: self.entries[c].set("0")).pack(side=tk.LEFT, padx=1)
        
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(btn_frame, text="全部启用 (99)", 
                  command=self.set_all_99).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="全部禁用 (0)",
                  command=self.set_all_0).pack(side=tk.LEFT, padx=2)
        
        btn_frame2 = ttk.Frame(main_frame)
        btn_frame2.pack(fill=tk.X)
        
        ttk.Button(btn_frame2, text="确定", command=self.on_ok, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame2, text="取消", command=self.on_cancel, width=10).pack(side=tk.LEFT, padx=5)
        
        self.dialog.bind('<Return>', lambda e: self.on_ok())
        self.dialog.bind('<Escape>', lambda e: self.on_cancel())
        
        self.dialog.update_idletasks()
        x = self.parent.winfo_x() + (self.parent.winfo_width() - self.dialog.winfo_width()) // 2
        y = self.parent.winfo_y() + (self.parent.winfo_height() - self.dialog.winfo_height()) // 2
        self.dialog.geometry(f"+{x}+{y}")
    
    def set_all_99(self):
        for var in self.entries.values():
            var.set("99")
    
    def set_all_0(self):
        for var in self.entries.values():
            var.set("0")
    
    def on_ok(self):
        try:
            result = {}
            for comp, var in self.entries.items():
                val = int(var.get())
                if val < 0:
                    val = 0
                if val > 999:
                    val = 999
                result[comp] = val
            self.result = result
            self.dialog.destroy()
        except ValueError:
            messagebox.showerror("错误", "请输入有效的数字")
    
    def on_cancel(self):
        self.dialog.destroy()
    
    def get_result(self) -> Optional[Dict[str, int]]:
        return self.result


class MultiInputDialog:
    """多输入点配置对话框 - 直接应用到当前设置"""
    def __init__(self, parent, input_points: List[Tuple], input_delays: Dict[int, int]):
        self.parent = parent
        self.input_points = input_points.copy()
        self.input_delays = input_delays.copy()
        self.result = None
        self.result_delays = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("多输入点配置")
        self.dialog.geometry("500x480")  # 增加高度
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self._create_ui()
    
    def _create_ui(self):
        main_frame = ttk.Frame(self.dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 标题
        title_frame = ttk.Frame(main_frame)
        title_frame.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(title_frame, text="配置每个输入点的参数", font=('', 11, 'bold')).pack()
        ttk.Label(title_frame, text="延迟：第二个输入相对第一个的偏移量", font=('', 9), foreground='#888').pack()
        
        # 表格头部
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=2)
        ttk.Label(header_frame, text="输入点", width=10, font=('', 9, 'bold')).pack(side=tk.LEFT, padx=2)
        ttk.Label(header_frame, text="持续(tick)", width=10, font=('', 9, 'bold')).pack(side=tk.LEFT, padx=2)
        ttk.Label(header_frame, text="强度", width=8, font=('', 9, 'bold')).pack(side=tk.LEFT, padx=2)
        ttk.Label(header_frame, text="延迟(tick)", width=8, font=('', 9, 'bold')).pack(side=tk.LEFT, padx=2)
        
        # 分隔线
        ttk.Separator(main_frame, orient='horizontal').pack(fill=tk.X, pady=4)
        
        # 滚动区域 - 限制高度，不占满全部空间
        canvas_frame = ttk.Frame(main_frame, height=180)
        canvas_frame.pack(fill=tk.BOTH, expand=True, pady=4)
        canvas_frame.pack_propagate(False)
        
        canvas = tk.Canvas(canvas_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)
        
        scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # 每个输入点的配置
        self.entries = []
        self.delay_entries = []
        self.row_frames = []
        for i, (x, y, dur, strength) in enumerate(self.input_points):
            row = ttk.Frame(scroll_frame)
            row.pack(fill=tk.X, pady=3)
            self.row_frames.append(row)
            
            # 输入点标签
            label_text = f"({x},{y})"
            if i == 0:
                label_text += " (A)"
            elif i == 1:
                label_text += " (B)"
            else:
                label_text += f" ({chr(ord('A')+i)})"
            
            label = ttk.Label(row, text=label_text, width=10)
            label.pack(side=tk.LEFT, padx=2)
            
            # 持续时间
            dur_var = tk.StringVar(value=str(dur))
            dur_entry = ttk.Entry(row, width=10, textvariable=dur_var)
            dur_entry.pack(side=tk.LEFT, padx=2)
            
            # 强度
            str_var = tk.StringVar(value=str(strength))
            str_entry = ttk.Entry(row, width=8, textvariable=str_var)
            str_entry.pack(side=tk.LEFT, padx=2)
            
            # 延迟
            delay_default = self.input_delays.get(i, 0 if i == 0 else 5)
            delay_var = tk.StringVar(value=str(delay_default))
            delay_entry = tk.Entry(row, width=8, textvariable=delay_var)
            delay_entry.pack(side=tk.LEFT, padx=2)
            
            self.entries.append((dur_var, str_var))
            self.delay_entries.append(delay_var)
            
            # 如果是第一个输入，延迟不可修改（固定为0）
            if i == 0:
                delay_entry.config(state='disabled', bg='#2a2a3a', fg='#888')
                ttk.Label(row, text="(基准)", font=('', 8), foreground='#888').pack(side=tk.LEFT, padx=2)
        
        # 重置默认按钮
        reset_frame = ttk.Frame(main_frame)
        reset_frame.pack(fill=tk.X, pady=4)
        ttk.Button(reset_frame, text="🔄 重置为默认值 (持续15, 强度15)", 
                  command=self.reset_defaults, width=30).pack()
        
        # 分隔线
        ttk.Separator(main_frame, orient='horizontal').pack(fill=tk.X, pady=4)
        
        # 按钮区域 - 固定在底部
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=8)
        
        # 确认按钮
        save_btn = tk.Button(
            btn_frame,
            text="✅ 确认并应用设置",
            command=self.on_ok,
            bg='#0f3460',
            fg='#ffffff',
            font=('', 11, 'bold'),
            relief=tk.RAISED,
            padx=20,
            pady=6,
            cursor="hand2"
        )
        save_btn.pack(pady=4)
        save_btn.bind('<Enter>', lambda e: save_btn.config(bg='#1a4a8a'))
        save_btn.bind('<Leave>', lambda e: save_btn.config(bg='#0f3460'))
        
        # 提示信息
        ttk.Label(main_frame, text="💡 点击「确认并应用设置」将配置保存到当前关卡", 
                 font=('', 8), foreground='#4ecca3').pack(pady=(0, 2))
        
        self.dialog.bind('<Escape>', lambda e: self.on_cancel())
        
        self.dialog.update_idletasks()
        x = self.parent.winfo_x() + (self.parent.winfo_width() - self.dialog.winfo_width()) // 2
        y = self.parent.winfo_y() + (self.parent.winfo_height() - self.dialog.winfo_height()) // 2
        self.dialog.geometry(f"+{x}+{y}")
    
    def reset_defaults(self):
        """重置为默认配置"""
        if not messagebox.askyesno("确认", "确定要重置所有配置为默认值吗？"):
            return
        
        for i, (dur_var, str_var) in enumerate(self.entries):
            dur_var.set("15")
            str_var.set("15")
            if i == 0:
                self.delay_entries[i].set("0")
            else:
                self.delay_entries[i].set("5")
    
    def on_ok(self):
        try:
            result = []
            result_delays = {}
            for i, (dur_var, str_var) in enumerate(self.entries):
                duration = int(dur_var.get())
                strength = int(str_var.get())
                delay = int(self.delay_entries[i].get())
                x, y, _, _ = self.input_points[i]
                result.append((x, y, duration, strength))
                result_delays[i] = delay
            self.result = result
            self.result_delays = result_delays
            self.dialog.destroy()
        except ValueError:
            messagebox.showerror("错误", "请输入有效的数字")
    
    def on_cancel(self):
        self.dialog.destroy()
    
    def get_result(self) -> Optional[Tuple[List[Tuple], Dict[int, int]]]:
        if self.result is not None:
            return self.result, self.result_delays
        return None

class CircuitDesigner:
    """电路设计器主窗口"""
    
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("红石电路设计器 - Redstone Circuit Designer")
        self.root.geometry("1200x880")
        self.root.resizable(True, True)
        
        self.level_data = LevelData()
        default_level = self._create_empty_level("新关卡", "描述你的关卡", "提示信息")
        self.level_data.levels = [default_level]
        self.level_data.current_index = 0
        
        self.cols = 14
        self.rows = 9
        self.selected_comp = 'dust'
        self.selected_rotate = 0
        self.mode = 'place'
        self.hover_x = -1
        self.hover_y = -1
        
        self.input_points = []  # [(x, y, duration, strength)]
        self.input_delays = {}  # {index: delay}
        self.output_point = None
        self.target_delay = 10
        self.target_duration = 10
        self.target_strength = None
        self.use_target_strength = False
        
        self.available_components = ['dust']
        self.component_limits: Dict[str, int] = {}
        
        self.sim = CircuitSimulator(self.cols, self.rows)
        self.sim.signal_callback = self.on_signal_update
        self.saved_layout = []
        
        self.level_name = tk.StringVar(value="新关卡")
        self.level_desc = tk.StringVar(value="描述你的关卡")
        self.level_hint = tk.StringVar(value="提示信息")
        
        self._temp_available = []
        self._temp_limits = {}
        
        self._create_ui()
        self._load_current_level()
        self._redraw()
    
    def _create_empty_level(self, name: str, desc: str, hint: str) -> Dict:
        return {
            'name': name,
            'desc': desc,
            'cols': 14,
            'rows': 9,
            'input': {'x': 2, 'y': 4, 'duration': 15, 'strength': 15},
            'output': {'x': 11, 'y': 4},
            'target': {'delay': 10, 'duration': 10},
            'components': ['dust'],
            'limits': {},
            'hint': hint,
            'par': 5,
            'preplaced': []
        }
    
    def _create_ui(self):
        main_frame = ttk.Frame(self.root, padding="4")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 顶部：关卡切换和操作
        top_frame = ttk.Frame(main_frame)
        top_frame.pack(fill=tk.X, pady=2)
        
        ttk.Label(top_frame, text="关卡:").pack(side=tk.LEFT, padx=2)
        
        self.level_combo = ttk.Combobox(top_frame, width=20, state='readonly')
        self.level_combo.pack(side=tk.LEFT, padx=2)
        self.level_combo.bind('<<ComboboxSelected>>', self.on_level_selected)
        
        ttk.Button(top_frame, text="◀", command=self.prev_level, width=3).pack(side=tk.LEFT, padx=1)
        ttk.Button(top_frame, text="▶", command=self.next_level, width=3).pack(side=tk.LEFT, padx=1)
        
        ttk.Separator(top_frame, orient='vertical').pack(side=tk.LEFT, padx=6, fill='y')
        
        ttk.Button(top_frame, text="➕ 新增关卡", command=self.add_new_level, width=10).pack(side=tk.LEFT, padx=2)
        ttk.Button(top_frame, text="🗑️ 删除关卡", command=self.delete_current_level, width=10).pack(side=tk.LEFT, padx=2)
        
        ttk.Separator(top_frame, orient='vertical').pack(side=tk.LEFT, padx=6, fill='y')
        
        ttk.Button(top_frame, text="💾 保存", command=self.save_current, width=8).pack(side=tk.LEFT, padx=2)
        ttk.Button(top_frame, text="📤 导出JSON", command=self.export_json, width=10).pack(side=tk.LEFT, padx=2)
        ttk.Button(top_frame, text="📥 导入JSON", command=self.import_json, width=10).pack(side=tk.LEFT, padx=2)
        
        self.modified_label = ttk.Label(top_frame, text="", foreground='#e94560')
        self.modified_label.pack(side=tk.LEFT, padx=6)
        
        # 主内容区域
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # 左侧：绘图区域
        left_frame = ttk.Frame(content_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 信息栏
        info_frame = ttk.Frame(left_frame)
        info_frame.pack(fill=tk.X, pady=2)
        
        ttk.Label(info_frame, text="名称:").pack(side=tk.LEFT, padx=2)
        self.name_entry = ttk.Entry(info_frame, textvariable=self.level_name, width=14)
        self.name_entry.pack(side=tk.LEFT, padx=2)
        self.name_entry.bind('<KeyRelease>', self.on_field_changed)
        
        ttk.Label(info_frame, text="描述:").pack(side=tk.LEFT, padx=2)
        self.desc_entry = ttk.Entry(info_frame, textvariable=self.level_desc, width=22)
        self.desc_entry.pack(side=tk.LEFT, padx=2)
        self.desc_entry.bind('<KeyRelease>', self.on_field_changed)
        
        ttk.Label(info_frame, text="提示:").pack(side=tk.LEFT, padx=2)
        self.hint_entry = ttk.Entry(info_frame, textvariable=self.level_hint, width=25)
        self.hint_entry.pack(side=tk.LEFT, padx=2)
        self.hint_entry.bind('<KeyRelease>', self.on_field_changed)
        
        # 画布
        canvas_frame = ttk.Frame(left_frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        self.canvas = tk.Canvas(
            canvas_frame,
            bg='#0d1117',
            highlightthickness=2,
            highlightbackground='#0f3460',
            width=self.cols * CELL + 2,
            height=self.rows * CELL + 2,
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        self.canvas.bind('<Motion>', self.on_mouse_move)
        self.canvas.bind('<Leave>', self.on_mouse_leave)
        self.canvas.bind('<Button-1>', self.on_left_click)
        self.canvas.bind('<Button-3>', self.on_right_click)
        self.canvas.bind('<B1-Motion>', self.on_drag)
        
        # 底栏
        bottom_frame = ttk.Frame(left_frame)
        bottom_frame.pack(fill=tk.X, pady=2)
        
        self.status_label = ttk.Label(bottom_frame, text="就绪", foreground='#888')
        self.status_label.pack(side=tk.LEFT, padx=4)
        
        self.result_label = ttk.Label(bottom_frame, text="延迟: -  持续: -  强度: -", foreground='#888')
        self.result_label.pack(side=tk.LEFT, padx=10)
        
        ttk.Button(bottom_frame, text="▶ 运行", command=self.run_simulation, width=8).pack(side=tk.LEFT, padx=2)
        ttk.Button(bottom_frame, text="⏹ 停止", command=self.stop_simulation, width=8).pack(side=tk.LEFT, padx=2)
        ttk.Button(bottom_frame, text="⏭ 单步", command=self.step_simulation, width=8).pack(side=tk.LEFT, padx=2)
        ttk.Button(bottom_frame, text="↺ 重置", command=self.reset_simulation, width=8).pack(side=tk.LEFT, padx=2)
        
        # 右侧：控制面板 - 带滚动条
        right_frame = ttk.Frame(content_frame, padding="0")
        right_frame.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 创建滚动画布
        right_canvas = tk.Canvas(right_frame, highlightthickness=0, width=280)
        right_scrollbar = ttk.Scrollbar(right_frame, orient="vertical", command=right_canvas.yview)
        right_scrollable = ttk.Frame(right_canvas)
        
        right_scrollable.bind(
            "<Configure>",
            lambda e: right_canvas.configure(scrollregion=right_canvas.bbox("all"))
        )
        
        right_canvas.create_window((0, 0), window=right_scrollable, anchor="nw")
        right_canvas.configure(yscrollcommand=right_scrollbar.set)
        
        right_canvas.pack(side="left", fill="both", expand=True)
        right_scrollbar.pack(side="right", fill="y")
        
        # 鼠标滚轮支持
        def on_mousewheel(event):
            right_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        right_canvas.bind_all("<MouseWheel>", on_mousewheel)
        
        # 右侧内容
        right_inner = right_scrollable
        
        # 模式选择
        mode_frame = ttk.LabelFrame(right_inner, text="编辑模式", padding="4")
        mode_frame.pack(fill=tk.X, pady=2)
        
        self.mode_var = tk.StringVar(value='place')
        ttk.Radiobutton(mode_frame, text="✏️ 放置元件", variable=self.mode_var, 
                       value='place', command=self.set_mode_place).pack(anchor='w')
        ttk.Radiobutton(mode_frame, text="🔵 设置输入点", variable=self.mode_var,
                       value='set_input', command=self.set_mode_input).pack(anchor='w')
        ttk.Radiobutton(mode_frame, text="🔴 设置输出点", variable=self.mode_var,
                       value='set_output', command=self.set_mode_output).pack(anchor='w')
        
        # 可用元件配置
        comp_config_frame = ttk.LabelFrame(right_inner, text="可用元件配置", padding="4")
        comp_config_frame.pack(fill=tk.X, pady=2)
        
        self.comp_config_text = tk.Text(comp_config_frame, height=4, width=25, bg='#1a1a2e', fg='#e0e0e0')
        self.comp_config_text.pack(fill=tk.X, pady=2)
        
        config_btn_frame = ttk.Frame(comp_config_frame)
        config_btn_frame.pack(fill=tk.X, pady=2)
        ttk.Button(config_btn_frame, text="📝 编辑限制", command=self.edit_limits, width=12).pack(side=tk.LEFT, padx=2)
        ttk.Button(config_btn_frame, text="✅ 应用配置", command=self.apply_comp_config, width=12).pack(side=tk.LEFT, padx=2)
        
        ttk.Label(comp_config_frame, text="格式: 元件名:数量, 用逗号分隔", font=('', 8), foreground='#888').pack()
        ttk.Label(comp_config_frame, text="例: dust:10, repeater:3, torch:0", font=('', 8), foreground='#888').pack()
        
        # 元件选择
        comp_frame = ttk.LabelFrame(right_inner, text="元件", padding="4")
        comp_frame.pack(fill=tk.X, pady=2)
        
        comp_grid = ttk.Frame(comp_frame)
        comp_grid.pack()
        
        self.comp_buttons = {}
        for i, comp in enumerate(PLACEABLE_COMPONENTS):
            btn = tk.Button(
                comp_grid,
                text=COMP_NAMES.get(comp, comp),
                width=8,
                relief=tk.RAISED,
                bg='#1a1a2e',
                fg='#e0e0e0',
                activebackground='#0f3460',
                state='disabled'
            )
            btn.grid(row=i // 3, column=i % 3, padx=2, pady=2, sticky='ew')
            btn.bind('<Button-1>', lambda e, c=comp: self.select_component(c))
            self.comp_buttons[comp] = btn
        
        self.erase_btn = tk.Button(
            comp_grid,
            text="❌ 擦除",
            width=8,
            relief=tk.RAISED,
            bg='#1a1a2e',
            fg='#e94560',
            activebackground='#0f3460',
        )
        self.erase_btn.grid(row=2, column=2, padx=2, pady=2, sticky='ew')
        self.erase_btn.bind('<Button-1>', lambda e: self.select_component('erase'))
        
        dir_frame = ttk.Frame(comp_frame)
        dir_frame.pack(pady=4)
        self.dir_label = ttk.Label(dir_frame, text=f"方向: {DIR_NAMES[self.selected_rotate]}", foreground='#888')
        self.dir_label.pack(side=tk.LEFT, padx=4)
        ttk.Button(dir_frame, text="↻ R", command=self.rotate_selected, width=4).pack(side=tk.LEFT)
        
        # 输入/输出配置
        io_frame = ttk.LabelFrame(right_inner, text="输入/输出配置", padding="4")
        io_frame.pack(fill=tk.X, pady=2)
        
        ttk.Label(io_frame, text="输入点:").pack(anchor='w')
        self.input_label = ttk.Label(io_frame, text="未设置", foreground='#888')
        self.input_label.pack(anchor='w', pady=1)
        
        ttk.Label(io_frame, text="输入持续 (tick):").pack(anchor='w', pady=(4,0))
        self.input_duration_entry = ttk.Entry(io_frame, width=8)
        self.input_duration_entry.pack(anchor='w', pady=1)
        self.input_duration_entry.insert(0, "15")
        self.input_duration_entry.bind('<KeyRelease>', self.on_field_changed)
        
        ttk.Label(io_frame, text="输入强度:").pack(anchor='w', pady=(4,0))
        self.input_strength_entry = ttk.Entry(io_frame, width=8)
        self.input_strength_entry.pack(anchor='w', pady=1)
        self.input_strength_entry.insert(0, "15")
        self.input_strength_entry.bind('<KeyRelease>', self.on_field_changed)
        
        # 多输入配置按钮
        multi_btn_frame = ttk.Frame(io_frame)
        multi_btn_frame.pack(fill=tk.X, pady=2)
        ttk.Button(multi_btn_frame, text="📋 配置多个输入点", command=self.configure_multi_input, width=18).pack(pady=2)
        
        ttk.Button(io_frame, text="更新输入参数", command=self.update_input_params, width=14).pack(pady=2)
        
        ttk.Label(io_frame, text="输出点:").pack(anchor='w', pady=(4,0))
        self.output_label = ttk.Label(io_frame, text="未设置", foreground='#888')
        self.output_label.pack(anchor='w', pady=1)
        
        # 目标配置
        target_frame = ttk.LabelFrame(io_frame, text="目标配置", padding="4")
        target_frame.pack(fill=tk.X, pady=4)
        
        ttk.Label(target_frame, text="目标延迟 (tick):").pack(anchor='w', pady=(2,0))
        self.target_delay_entry = ttk.Entry(target_frame, width=8)
        self.target_delay_entry.pack(anchor='w', pady=1)
        self.target_delay_entry.insert(0, "10")
        self.target_delay_entry.bind('<KeyRelease>', self.on_field_changed)
        
        ttk.Label(target_frame, text="目标持续 (tick):").pack(anchor='w', pady=(2,0))
        self.target_duration_entry = ttk.Entry(target_frame, width=8)
        self.target_duration_entry.pack(anchor='w', pady=1)
        self.target_duration_entry.insert(0, "10")
        self.target_duration_entry.bind('<KeyRelease>', self.on_field_changed)
        
        # 目标强度
        self.use_strength_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(target_frame, text="启用目标强度", variable=self.use_strength_var,
                       command=self.toggle_target_strength).pack(anchor='w', pady=(4,0))
        
        self.strength_frame = ttk.Frame(target_frame)
        self.strength_frame.pack(fill=tk.X, pady=2)
        ttk.Label(self.strength_frame, text="目标强度:").pack(side=tk.LEFT)
        self.target_strength_entry = ttk.Entry(self.strength_frame, width=8)
        self.target_strength_entry.pack(side=tk.LEFT, padx=4)
        self.target_strength_entry.insert(0, "15")
        self.target_strength_entry.bind('<KeyRelease>', self.on_field_changed)
        self.strength_frame.pack_forget()
        
        btn_frame = ttk.Frame(io_frame)
        btn_frame.pack(fill=tk.X, pady=4)
        ttk.Button(btn_frame, text="清除所有元件", command=self.clear_components, width=12).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="清空输入输出", command=self.clear_io, width=12).pack(side=tk.LEFT, padx=2)
        
        help_frame = ttk.LabelFrame(right_inner, text="操作提示", padding="4")
        help_frame.pack(fill=tk.X, pady=2)
        
        help_text = """
        左键: 放置/设置
        右键: 移除元件
        R键: 旋转方向
        点击已有元件修改属性
        """
        ttk.Label(help_frame, text=help_text, foreground='#888', justify=tk.LEFT).pack(anchor='w')
        
        self.select_component('dust')
        self._update_level_list()
    
    def configure_multi_input(self):
        """配置多输入点参数"""
        if len(self.input_points) < 2:
            messagebox.showwarning("警告", "需要至少2个输入点才能配置。请先添加多个输入点。")
            return
        
        dialog = MultiInputDialog(self.root, self.input_points, self.input_delays)
        self.root.wait_window(dialog.dialog)
        
        result = dialog.get_result()
        if result is not None:
            new_points, new_delays = result
            self.input_points = new_points
            self.input_delays = new_delays
            
            self._update_input_label()
            self._configure_simulator()
            self.level_data.modified = True
            self._update_modified_status()
            self._redraw()
            self.status_label.config(text=f"✅ 已更新 {len(self.input_points)} 个输入点", foreground='#4ecca3')
    
    def toggle_target_strength(self):
        if self.use_strength_var.get():
            self.strength_frame.pack(fill=tk.X, pady=2)
            self.target_strength = int(self.target_strength_entry.get()) if self.target_strength_entry.get().isdigit() else 15
        else:
            self.strength_frame.pack_forget()
            self.target_strength = None
        self.level_data.modified = True
        self._update_modified_status()
    
    def _update_comp_config_display(self):
        parts = []
        for comp in ALL_COMPONENTS:
            limit = self.component_limits.get(comp, 0)
            if limit > 0:
                parts.append(f"{comp}:{limit}")
            else:
                parts.append(f"{comp}:禁用")
        self.comp_config_text.delete('1.0', tk.END)
        self.comp_config_text.insert('1.0', ', '.join(parts))
        
        for comp, btn in self.comp_buttons.items():
            if comp in self.available_components and self.component_limits.get(comp, 0) > 0:
                btn.config(state='normal', bg='#1a1a2e', fg='#e0e0e0')
            else:
                btn.config(state='disabled', bg='#1a1a2e', fg='#444444')
        
        if self.selected_comp not in self.available_components or self.component_limits.get(self.selected_comp, 0) == 0:
            for comp in self.available_components:
                if self.component_limits.get(comp, 0) > 0:
                    self.select_component(comp)
                    break
            else:
                self.select_component('dust')
    
    def edit_limits(self):
        dialog = ComponentLimitDialog(self.root, ALL_COMPONENTS, self.component_limits)
        self.root.wait_window(dialog.dialog)
        
        result = dialog.get_result()
        if result is not None:
            self._temp_limits = result
            self._temp_available = [c for c in ALL_COMPONENTS if result.get(c, 0) > 0]
            if not self._temp_available:
                self._temp_available = ['dust']
                self._temp_limits['dust'] = 99
            
            parts = []
            for comp in ALL_COMPONENTS:
                limit = self._temp_limits.get(comp, 0)
                if limit > 0:
                    parts.append(f"{comp}:{limit}")
                else:
                    parts.append(f"{comp}:禁用")
            self.comp_config_text.delete('1.0', tk.END)
            self.comp_config_text.insert('1.0', ', '.join(parts))
            
            self.status_label.config(text="⏳ 配置已修改，点击'应用配置'保存", foreground='#e94560')
    
    def apply_comp_config(self):
        text = self.comp_config_text.get('1.0', tk.END).strip()
        if not text:
            messagebox.showwarning("警告", "配置不能为空")
            return
        
        available = []
        limits = {}
        parts = [p.strip() for p in text.split(',') if p.strip()]
        for part in parts:
            if ':' in part:
                name, limit = part.split(':', 1)
                name = name.strip()
                limit_str = limit.strip()
                if limit_str == '禁用':
                    limit_val = 0
                else:
                    try:
                        limit_val = int(limit_str)
                    except ValueError:
                        continue
                
                if name in COMP_NAMES:
                    if limit_val > 0:
                        available.append(name)
                        limits[name] = limit_val
                    else:
                        limits[name] = 0
        
        if not available:
            messagebox.showwarning("警告", "没有可用的元件，至少保留一个")
            return
        
        self.available_components = available
        self.component_limits = limits
        
        self._update_comp_config_display()
        self.level_data.modified = True
        self._update_modified_status()
        self._redraw()
        self.status_label.config(text="✅ 元件配置已应用", foreground='#4ecca3')
    
    def _update_level_list(self):
        names = []
        for i, level in enumerate(self.level_data.levels):
            name = level.get('name', f'关卡{i+1}')
            names.append(f"{i+1}. {name}")
        self.level_combo['values'] = names
        if 0 <= self.level_data.current_index < len(names):
            self.level_combo.current(self.level_data.current_index)
    
    def _load_current_level(self):
        level = self.level_data.get_level(self.level_data.current_index)
        if not level:
            return
        
        self.input_points = []
        self.input_delays = {}
        self.output_point = None
        
        self.level_name.set(level.get('name', '新关卡'))
        self.level_desc.set(level.get('desc', ''))
        self.level_hint.set(level.get('hint', ''))
        
        self.cols = level.get('cols', 14)
        self.rows = level.get('rows', 9)
        self.canvas.config(width=self.cols * CELL + 2, height=self.rows * CELL + 2)
        
        components = level.get('components', ['dust'])
        limits = level.get('limits', {})
        
        self.available_components = []
        self.component_limits = {}
        for comp in ALL_COMPONENTS:
            if comp in components:
                self.available_components.append(comp)
                self.component_limits[comp] = limits.get(comp, 99)
            else:
                self.component_limits[comp] = 0
        
        if not self.available_components:
            self.available_components = ['dust']
            self.component_limits['dust'] = 99
        
        self._update_comp_config_display()
        
        self.sim = CircuitSimulator(self.cols, self.rows)
        self.sim.signal_callback = self.on_signal_update
        
        if 'input' in level:
            inp = level['input']
            self.input_points = [(inp['x'], inp['y'], inp['duration'], inp['strength'])]
            self.input_duration_entry.delete(0, tk.END)
            self.input_duration_entry.insert(0, str(inp['duration']))
            self.input_strength_entry.delete(0, tk.END)
            self.input_strength_entry.insert(0, str(inp['strength']))
        elif 'inputs' in level:
            self.input_points = []
            for i, inp in enumerate(level['inputs']):
                self.input_points.append((inp['x'], inp['y'], inp['duration'], inp['strength']))
                self.input_delays[i] = inp.get('delay', 0 if i == 0 else 5)
            if self.input_points:
                self.input_duration_entry.delete(0, tk.END)
                self.input_duration_entry.insert(0, str(self.input_points[0][2]))
                self.input_strength_entry.delete(0, tk.END)
                self.input_strength_entry.insert(0, str(self.input_points[0][3]))
        self._update_input_label()
        
        if 'output' in level:
            out = level['output']
            self.output_point = (out['x'], out['y'])
            self.output_label.config(text=f"({out['x']}, {out['y']})", foreground='#4ecca3')
        
        if 'target' in level:
            target = level['target']
            self.target_delay = target.get('delay', 10)
            self.target_duration = target.get('duration', 10)
            self.target_delay_entry.delete(0, tk.END)
            self.target_delay_entry.insert(0, str(self.target_delay))
            self.target_duration_entry.delete(0, tk.END)
            self.target_duration_entry.insert(0, str(self.target_duration))
            
            if 'strength' in target:
                self.target_strength = target['strength']
                self.use_strength_var.set(True)
                self.target_strength_entry.delete(0, tk.END)
                self.target_strength_entry.insert(0, str(self.target_strength))
                self.strength_frame.pack(fill=tk.X, pady=2)
            else:
                self.target_strength = None
                self.use_strength_var.set(False)
                self.strength_frame.pack_forget()
        
        if 'preplaced' in level:
            for p in level['preplaced']:
                self.sim.place_component(
                    p['x'], p['y'],
                    p['type'],
                    p.get('direction', 0),
                    p.get('delay', 1),
                    p.get('mode', 'compare')
                )
        
        self._save_layout()
        self._configure_simulator()
        self._update_level_list()
        self._update_modified_status()
        self._redraw()
    
    def _save_current_level(self):
        level = self._get_level_data()
        if level:
            self.level_data.set_level(self.level_data.current_index, level)
            self._update_level_list()
            self._update_modified_status()
    
    def _get_level_data(self) -> Optional[Dict]:
        if not self.input_points:
            messagebox.showerror("错误", "请先设置输入点")
            return None
        
        if not self.output_point:
            messagebox.showerror("错误", "请先设置输出点")
            return None
        
        if len(self.input_points) == 1:
            x, y, d, s = self.input_points[0]
            input_config = {'x': x, 'y': y, 'duration': d, 'strength': s}
            inputs_config = None
        else:
            input_config = None
            inputs_config = []
            for i, (x, y, d, s) in enumerate(self.input_points):
                delay = self.input_delays.get(i, 0 if i == 0 else 5)
                inputs_config.append({
                    'x': x, 'y': y, 'duration': d, 'strength': s,
                    'delay': delay
                })
        
        components = list(self.available_components)
        
        preplaced = []
        for x in range(self.cols):
            for y in range(self.rows):
                cell = self.sim.grid[x][y]
                if cell['type'] not in ['empty', 'input', 'output']:
                    preplaced.append({
                        'x': x, 'y': y,
                        'type': cell['type'],
                        'direction': cell['direction'],
                        'delay': cell['delay'],
                        'mode': cell['mode'],
                    })
        
        target = {'delay': self.target_delay, 'duration': self.target_duration}
        if self.use_strength_var.get() and self.target_strength is not None:
            target['strength'] = self.target_strength
        
        level = {
            'name': self.level_name.get(),
            'desc': self.level_desc.get(),
            'cols': self.cols,
            'rows': self.rows,
            'output': {'x': self.output_point[0], 'y': self.output_point[1]},
            'target': target,
            'components': components if components else ['dust'],
            'limits': {k: v for k, v in self.component_limits.items() if v > 0 and v != 99},
            'hint': self.level_hint.get(),
            'par': sum(1 for x in range(self.cols) for y in range(self.rows) if self.sim.grid[x][y]['type'] not in ['empty', 'input', 'output']) + 5,
            'preplaced': preplaced,
        }
        
        if input_config:
            level['input'] = input_config
        if inputs_config:
            level['inputs'] = inputs_config
        
        return level
    
    def _update_modified_status(self):
        if self.level_data.modified:
            self.modified_label.config(text="⚠ 已修改")
        else:
            self.modified_label.config(text="")
    
    # ============================================================
    # 关卡操作
    # ============================================================
    
    def on_level_selected(self, event=None):
        idx = self.level_combo.current()
        if idx >= 0 and idx != self.level_data.current_index:
            self._save_current_level()
            self.level_data.current_index = idx
            self._load_current_level()
            self._redraw()
    
    def prev_level(self):
        if self.level_data.current_index > 0:
            self._save_current_level()
            self.level_data.current_index -= 1
            self._load_current_level()
            self._redraw()
    
    def next_level(self):
        if self.level_data.current_index < len(self.level_data.levels) - 1:
            self._save_current_level()
            self.level_data.current_index += 1
            self._load_current_level()
            self._redraw()
    
    def add_new_level(self):
        self._save_current_level()
        new_level = self._create_empty_level(
            f"新关卡{len(self.level_data.levels) + 1}",
            "描述你的关卡",
            "提示信息"
        )
        new_level['components'] = self.available_components.copy()
        new_level['limits'] = self.component_limits.copy()
        self.level_data.add_level(new_level)
        self.level_data.current_index = len(self.level_data.levels) - 1
        self._load_current_level()
        self._redraw()
        self.status_label.config(text="✅ 已新增关卡", foreground='#4ecca3')
    
    def delete_current_level(self):
        if len(self.level_data.levels) <= 1:
            messagebox.showwarning("警告", "至少保留一个关卡")
            return
        
        if messagebox.askyesno("确认删除", f"确定要删除关卡 {self.level_data.current_index + 1} 吗？"):
            self.level_data.remove_level(self.level_data.current_index)
            self._load_current_level()
            self._redraw()
            self.status_label.config(text="✅ 已删除关卡", foreground='#4ecca3')
    
    def save_current(self):
        self._save_current_level()
        if self.level_data.filepath:
            try:
                self.level_data.save_to_file(self.level_data.filepath)
                self.status_label.config(text="✅ 已保存", foreground='#4ecca3')
                self._update_modified_status()
            except Exception as e:
                messagebox.showerror("错误", f"保存失败: {e}")
        else:
            self.export_json()
    
    def on_field_changed(self, event=None):
        self.level_data.modified = True
        self._update_modified_status()
    
    # ============================================================
    # 编辑模式
    # ============================================================
    
    def set_mode_place(self):
        self.mode = 'place'
        self.status_label.config(text="模式: 放置元件", foreground='#888')
        self._redraw()
    
    def set_mode_input(self):
        self.mode = 'set_input'
        self.status_label.config(text="模式: 点击网格设置输入点", foreground='#4ecca3')
        self._redraw()
    
    def set_mode_output(self):
        self.mode = 'set_output'
        self.status_label.config(text="模式: 点击网格设置输出点", foreground='#3498db')
        self._redraw()
    
    def select_component(self, comp: str):
        if self.mode != 'place':
            self.mode_var.set('place')
            self.mode = 'place'
        
        if comp != 'erase':
            if comp not in self.available_components or self.component_limits.get(comp, 0) == 0:
                self.status_label.config(text=f"⚠ {COMP_NAMES.get(comp, comp)} 不可用", foreground='#e94560')
                return
        
        self.selected_comp = comp
        
        for c, btn in self.comp_buttons.items():
            if c in self.available_components and self.component_limits.get(c, 0) > 0:
                btn.config(relief=tk.RAISED, bg='#1a1a2e', fg='#e0e0e0')
            else:
                btn.config(relief=tk.RAISED, bg='#1a1a2e', fg='#444444')
        self.erase_btn.config(relief=tk.RAISED, bg='#1a1a2e')
        
        if comp == 'erase':
            self.erase_btn.config(relief=tk.SUNKEN, bg='#3a1a2e')
        else:
            btn = self.comp_buttons.get(comp)
            if btn:
                btn.config(relief=tk.SUNKEN, bg='#0f3460')
        self._redraw()
    
    def rotate_selected(self):
        self.selected_rotate = (self.selected_rotate + 1) % 4
        self.dir_label.config(text=f"方向: {DIR_NAMES[self.selected_rotate]}")
        self._redraw()
    
    def update_input_params(self):
        if not self.input_points:
            messagebox.showwarning("警告", "没有已设置的输入点")
            return
        
        try:
            duration = int(self.input_duration_entry.get())
            strength = int(self.input_strength_entry.get())
        except ValueError:
            messagebox.showerror("错误", "请输入有效的数字")
            return
        
        new_points = []
        for x, y, _, _ in self.input_points:
            new_points.append((x, y, duration, strength))
        self.input_points = new_points
        
        self._update_input_label()
        self._configure_simulator()
        self.level_data.modified = True
        self._update_modified_status()
        self._redraw()
        self.status_label.config(text=f"输入参数已更新: 持续={duration}, 强度={strength}", foreground='#4ecca3')
    
    def _get_grid_pos(self, event) -> Tuple[int, int]:
        x = event.x // CELL
        y = event.y // CELL
        if 0 <= x < self.cols and 0 <= y < self.rows:
            return x, y
        return -1, -1
    
    def on_mouse_move(self, event):
        x, y = self._get_grid_pos(event)
        self.hover_x, self.hover_y = x, y
        self._redraw()
    
    def on_mouse_leave(self, event):
        self.hover_x, self.hover_y = -1, -1
        self._redraw()
    
    def on_left_click(self, event):
        x, y = self._get_grid_pos(event)
        if x < 0 or y < 0:
            return
        
        if self.mode == 'set_input':
            self._set_input_point(x, y)
            return
        elif self.mode == 'set_output':
            self._set_output_point(x, y)
            return
        
        cell = self.sim.grid[x][y]
        
        if cell['type'] not in ['empty', 'input', 'output']:
            if cell['type'] == 'repeater':
                cell['delay'] = (cell['delay'] % 4) + 1
                self.status_label.config(text=f"中继器档位: {cell['delay']}", foreground='#4ecca3')
            elif cell['type'] == 'comparator':
                cell['mode'] = 'subtract' if cell['mode'] == 'compare' else 'compare'
                self.status_label.config(text=f"比较器模式: {'减法' if cell['mode'] == 'subtract' else '比较'}", foreground='#4ecca3')
            else:
                cell['direction'] = (cell['direction'] + 1) % 4
            self._save_layout()
            self.level_data.modified = True
            self._update_modified_status()
            self._redraw()
            return
        
        if self.selected_comp != 'erase':
            if self.selected_comp not in self.available_components:
                self.status_label.config(text=f"⚠ {COMP_NAMES.get(self.selected_comp, self.selected_comp)} 不可用", foreground='#e94560')
                return
            limit = self.component_limits.get(self.selected_comp, 99)
            if limit > 0:
                count = 0
                for gx in range(self.cols):
                    for gy in range(self.rows):
                        if self.sim.grid[gx][gy]['type'] == self.selected_comp:
                            count += 1
                if count >= limit:
                    self.status_label.config(text=f"⚠ {COMP_NAMES.get(self.selected_comp, self.selected_comp)} 已达上限 {limit}", foreground='#e94560')
                    return
            
            if cell['type'] == 'empty':
                self.sim.place_component(x, y, self.selected_comp, self.selected_rotate, 1, 'compare')
                self._save_layout()
                self.level_data.modified = True
                self._update_modified_status()
                self._redraw()
        else:
            self._remove_at(x, y)
    
    def on_right_click(self, event):
        x, y = self._get_grid_pos(event)
        if x < 0 or y < 0:
            return
        self._remove_at(x, y)
    
    def on_drag(self, event):
        if self.selected_comp == 'erase' or self.mode != 'place':
            return
        x, y = self._get_grid_pos(event)
        if x < 0 or y < 0:
            return
        if self.selected_comp not in self.available_components:
            return
        
        cell = self.sim.grid[x][y]
        if cell['type'] == 'empty':
            limit = self.component_limits.get(self.selected_comp, 99)
            if limit > 0:
                count = 0
                for gx in range(self.cols):
                    for gy in range(self.rows):
                        if self.sim.grid[gx][gy]['type'] == self.selected_comp:
                            count += 1
                if count >= limit:
                    return
            
            self.sim.place_component(x, y, self.selected_comp, self.selected_rotate, 1, 'compare')
            self._save_layout()
            self.level_data.modified = True
            self._update_modified_status()
            self._redraw()
    
    def _remove_at(self, x: int, y: int):
        if self.sim.remove_component(x, y):
            self._save_layout()
            self.level_data.modified = True
            self._update_modified_status()
            self._redraw()
    
    def _save_layout(self):
        self.saved_layout = self.sim.get_layout()
    
    def _restore_layout(self):
        self.sim.apply_layout(self.saved_layout)
    
    def _set_input_point(self, x: int, y: int):
        try:
            duration = int(self.input_duration_entry.get())
            strength = int(self.input_strength_entry.get())
        except ValueError:
            messagebox.showerror("错误", "请输入有效的数字")
            return
        
        for i, (ix, iy, _, _) in enumerate(self.input_points):
            if ix == x and iy == y:
                self.input_points.pop(i)
                # 清理延迟记录
                if i in self.input_delays:
                    del self.input_delays[i]
                # 重新索引延迟
                new_delays = {}
                for j, (_, _, _, _) in enumerate(self.input_points):
                    if j in self.input_delays:
                        new_delays[j] = self.input_delays[j]
                    else:
                        new_delays[j] = 0 if j == 0 else 5
                self.input_delays = new_delays
                
                self.sim.grid[x][y]['type'] = 'empty'
                self._update_input_label()
                self._configure_simulator()
                self.level_data.modified = True
                self._update_modified_status()
                self._redraw()
                return
        
        self.input_points.append((x, y, duration, strength))
        # 自动分配延迟
        idx = len(self.input_points) - 1
        if idx == 0:
            self.input_delays[idx] = 0
        else:
            self.input_delays[idx] = 5
        
        self._update_input_label()
        self._configure_simulator()
        self.level_data.modified = True
        self._update_modified_status()
        self._redraw()
        self.status_label.config(text=f"输入点已设置: ({x}, {y}) 持续={duration} 强度={strength}", foreground='#4ecca3')
    
    def _set_output_point(self, x: int, y: int):
        if self.output_point:
            ox, oy = self.output_point
            if ox == x and oy == y:
                self.output_point = None
                self.sim.grid[x][y]['type'] = 'empty'
                self.output_label.config(text="未设置", foreground='#888')
                self._configure_simulator()
                self.level_data.modified = True
                self._update_modified_status()
                self._redraw()
                return
        
        self.output_point = (x, y)
        self.sim.grid[x][y]['type'] = 'output'
        self.output_label.config(text=f"({x}, {y})", foreground='#4ecca3')
        self._configure_simulator()
        self.level_data.modified = True
        self._update_modified_status()
        self._redraw()
        self.status_label.config(text=f"输出点已设置: ({x}, {y})", foreground='#3498db')
    
    def _update_input_label(self):
        if self.input_points:
            texts = []
            for i, (x, y, d, s) in enumerate(self.input_points):
                delay = self.input_delays.get(i, 0 if i == 0 else 5)
                label = 'A' if i == 0 else chr(ord('A') + i) if i < 26 else str(i)
                texts.append(f"{label}({x},{y}) d={d} s={s} del={delay}")
            self.input_label.config(text=", ".join(texts), foreground='#4ecca3')
        else:
            self.input_label.config(text="未设置", foreground='#888')
    
    def _configure_simulator(self):
        for x in range(self.cols):
            for y in range(self.rows):
                if self.sim.grid[x][y]['type'] in ['input', 'output']:
                    self.sim.grid[x][y]['type'] = 'empty'
        
        self._restore_layout()
        
        if self.input_points:
            if len(self.input_points) == 1:
                x, y, d, s = self.input_points[0]
                self.sim.set_input(x, y, d, s)
            else:
                inputs = []
                for i, (x, y, d, s) in enumerate(self.input_points):
                    delay = self.input_delays.get(i, 0 if i == 0 else 5)
                    inputs.append({'x': x, 'y': y, 'duration': d, 'strength': s, 'delay': delay})
                self.sim.set_inputs(inputs)
        
        if self.output_point:
            x, y = self.output_point
            self.sim.set_output(x, y)
        
        try:
            self.target_delay = int(self.target_delay_entry.get())
            self.target_duration = int(self.target_duration_entry.get())
        except ValueError:
            pass
        
        if self.use_strength_var.get():
            try:
                self.target_strength = int(self.target_strength_entry.get())
            except ValueError:
                self.target_strength = None
        else:
            self.target_strength = None
        
        self.sim.set_target(self.target_delay, self.target_duration, self.target_strength)
        self.sim.reset()
    
    def clear_components(self):
        if messagebox.askyesno("确认", "确定要清除所有元件吗？"):
            self.sim.clear_all()
            self._save_layout()
            self.level_data.modified = True
            self._update_modified_status()
            self._redraw()
            self.status_label.config(text="已清除所有元件", foreground='#888')
    
    def clear_io(self):
        if messagebox.askyesno("确认", "确定要清除所有输入/输出点吗？"):
            self.input_points = []
            self.input_delays = {}
            self.output_point = None
            self._update_input_label()
            self.output_label.config(text="未设置", foreground='#888')
            self._configure_simulator()
            self.level_data.modified = True
            self._update_modified_status()
            self._redraw()
            self.status_label.config(text="已清除输入/输出", foreground='#888')
    
    # ============================================================
    # 绘制
    # ============================================================
    
    def _redraw(self):
        self.canvas.delete('all')
        w = self.cols * CELL
        h = self.rows * CELL
        
        self.canvas.create_rectangle(0, 0, w, h, fill='#0d1117', outline='')
        
        for x in range(self.cols + 1):
            self.canvas.create_line(x * CELL, 0, x * CELL, h, fill='#1a2333', width=1)
        for y in range(self.rows + 1):
            self.canvas.create_line(0, y * CELL, w, y * CELL, fill='#1a2333', width=1)
        
        for x in range(self.cols):
            for y in range(self.rows):
                cell = self.sim.grid[x][y]
                signal = self.sim.signals[x][y] if x < len(self.sim.signals) and y < len(self.sim.signals[x]) else 0
                self._draw_cell(x, y, cell, signal)
        
        if self.hover_x >= 0 and self.hover_y >= 0:
            cell = self.sim.grid[self.hover_x][self.hover_y]
            if self.mode == 'set_input':
                self._draw_selection_indicator(self.hover_x, self.hover_y, '#4ecca3', '点击设置输入')
            elif self.mode == 'set_output':
                self._draw_selection_indicator(self.hover_x, self.hover_y, '#3498db', '点击设置输出')
            elif self.mode == 'place' and self.selected_comp not in ['erase'] and cell['type'] == 'empty':
                self._draw_preview(self.hover_x, self.hover_y, self.selected_comp)
    
    def _draw_cell(self, x: int, y: int, cell: Dict, signal: int):
        px = x * CELL
        py = y * CELL
        cx = px + CELL // 2
        cy = py + CELL // 2
        
        t = cell['type']
        
        if t == 'empty':
            pass
        elif t == 'input':
            color = '#4ecca3' if self._is_input_active(x, y) else '#2a5a4a'
            self.canvas.create_oval(cx - 12, cy - 12, cx + 12, cy + 12, fill=color, outline='#1a4a3a')
            label = 'IN'
            if len(self.input_points) > 1:
                for i, (ix, iy, _, _) in enumerate(self.input_points):
                    if ix == x and iy == y:
                        label = chr(ord('A') + i) if i < 26 else str(i)
            self.canvas.create_text(cx, cy, text=label, fill='#fff', font=('Arial', 9, 'bold'))
        elif t == 'output':
            color = '#3498db' if self.sim.output_powered else '#1a4a6a'
            self.canvas.create_oval(cx - 12, cy - 12, cx + 12, cy + 12, fill=color, outline='#1a4a8a')
            self.canvas.create_text(cx, cy, text='OUT', fill='#fff', font=('Arial', 8, 'bold'))
        elif t == 'dust':
            self._draw_dust(x, y, signal)
        elif t == 'block':
            self.canvas.create_rectangle(px + 4, py + 4, px + CELL - 4, py + CELL - 4, fill='#8b0000', outline='#ff4444', width=2)
            self.canvas.create_rectangle(px + 8, py + 8, px + CELL - 8, py + CELL - 8, fill='#aa1010', outline='#660000')
        elif t == 'torch':
            self._draw_torch(x, y, cell)
        elif t == 'repeater':
            self._draw_repeater(x, y, cell)
        elif t == 'comparator':
            self._draw_comparator(x, y, cell)
        elif t == 'observer':
            self._draw_observer(x, y, cell)
    
    def _is_input_active(self, x: int, y: int) -> bool:
        if self.sim.input_states:
            for s in self.sim.input_states:
                if s['x'] == x and s['y'] == y:
                    return s['active']
        return self.sim.input_active
    
    def _draw_dust(self, x: int, y: int, signal: int):
        px = x * CELL
        py = y * CELL
        cx = px + CELL // 2
        cy = py + CELL // 2
        
        conns = [False] * 4
        has_conn = False
        for i in range(4):
            d = DIRECTIONS[i]
            nx = x + d['dx']
            ny = y + d['dy']
            if 0 <= nx < self.cols and 0 <= ny < self.rows:
                n = self.sim.grid[nx][ny]
                if n['type'] == 'output' or self.sim._is_conductive(n):
                    if self.sim._is_directional_source(n):
                        o = self.sim._get_output_dir(n)
                        if nx + o['dx'] == x and ny + o['dy'] == y:
                            conns[i] = True
                            has_conn = True
                    else:
                        conns[i] = True
                        has_conn = True
        
        color = '#ff3b3b' if signal > 0 else '#8b2020'
        glow = '#ff6b6b' if signal > 0 else '#5b1010'
        
        if not has_conn:
            self.canvas.create_oval(cx - 3, cy - 3, cx + 3, cy + 3, fill=glow, outline='')
        else:
            for i in range(4):
                if not conns[i]:
                    continue
                d = DIRECTIONS[i]
                if d['dx'] > 0:
                    self.canvas.create_line(cx, cy, px + CELL, cy, fill=color, width=3)
                elif d['dx'] < 0:
                    self.canvas.create_line(cx, cy, px, cy, fill=color, width=3)
                elif d['dy'] > 0:
                    self.canvas.create_line(cx, cy, cx, py + CELL, fill=color, width=3)
                else:
                    self.canvas.create_line(cx, cy, cx, py, fill=color, width=3)
            self.canvas.create_oval(cx - 3, cy - 3, cx + 3, cy + 3, fill=glow, outline='')
        
        if signal > 0:
            self.canvas.create_rectangle(px + 2, py + 2, px + 14, py + 12, fill='#222222', outline='')
            self.canvas.create_text(px + 8, py + 7, text=str(signal), fill='#ffdd44' if signal > 1 else '#ff6666', font=('Arial', 8, 'bold'))
    
    def _draw_torch(self, x: int, y: int, cell: Dict):
        px = x * CELL
        py = y * CELL
        cx = px + CELL // 2
        cy = py + CELL // 2
        d = DIRECTIONS[cell['direction']]
        
        self.canvas.create_line(cx, cy, cx - d['dx'] * 7, cy - d['dy'] * 7, fill='#666', width=3)
        
        color = '#444' if cell['extinguished'] else '#ff3333'
        glow = '#222' if cell['extinguished'] else '#ff6666'
        self.canvas.create_oval(cx + d['dx'] * 5 - 5, cy + d['dy'] * 5 - 5, cx + d['dx'] * 5 + 5, cy + d['dy'] * 5 + 5, fill=color, outline='')
        if not cell['extinguished']:
            self.canvas.create_oval(cx + d['dx'] * 5 - 3, cy + d['dy'] * 5 - 3, cx + d['dx'] * 5 + 3, cy + d['dy'] * 5 + 3, fill=glow, outline='')
    
    def _draw_repeater(self, x: int, y: int, cell: Dict):
        px = x * CELL
        py = y * CELL
        cx = px + CELL // 2
        cy = py + CELL // 2
        d = DIRECTIONS[cell['direction']]
        
        self.canvas.create_rectangle(px + 4, py + 4, px + CELL - 4, py + CELL - 4, fill='#3a3a3a', outline='#555', width=1)
        
        ax = cx + d['dx'] * 12
        ay = cy + d['dy'] * 12
        bx = cx - d['dx'] * 8
        by = cy - d['dy'] * 8
        color = '#ff3b3b' if cell['output_active'] else '#884444'
        self.canvas.create_line(bx, by, ax, ay, fill=color, width=2)
        
        perp = {'dx': -d['dy'], 'dy': d['dx']}
        self.canvas.create_line(ax, ay, ax - d['dx'] * 6 + perp['dx'] * 4, ay - d['dy'] * 6 + perp['dy'] * 4, fill=color, width=2)
        self.canvas.create_line(ax, ay, ax - d['dx'] * 6 - perp['dx'] * 4, ay - d['dy'] * 6 - perp['dy'] * 4, fill=color, width=2)
        
        for i in range(cell['delay']):
            ox = -d['dy'] * (8 + i * 5)
            oy = d['dx'] * (8 + i * 5)
            self.canvas.create_rectangle(cx + d['dx'] * 4 + ox - 3, cy + d['dy'] * 4 + oy - 3, cx + d['dx'] * 4 + ox + 3, cy + d['dy'] * 4 + oy + 3, fill='#aa4444' if cell['output_active'] else '#666', outline='')
        
        self.canvas.create_text(px + 4, py + 4, text=str(cell['delay']), fill='#888', font=('Arial', 7))
        
        if cell['output_active']:
            self.canvas.create_rectangle(px + 4, py + 4, px + CELL - 4, py + CELL - 4, outline='#ff3b3b', width=2)
    
    def _draw_comparator(self, x: int, y: int, cell: Dict):
        px = x * CELL
        py = y * CELL
        cx = px + CELL // 2
        cy = py + CELL // 2
        d = DIRECTIONS[cell['direction']]
        
        self.canvas.create_rectangle(px + 4, py + 4, px + CELL - 4, py + CELL - 4, fill='#3a3a3a', outline='#555', width=1)
        
        ftx = cx + d['dx'] * 10
        fty = cy + d['dy'] * 10
        color = '#ff3b3b' if cell['mode'] == 'compare' else '#444'
        self.canvas.create_oval(ftx - 4, fty - 4, ftx + 4, fty + 4, fill=color, outline='')
        
        perp = {'dx': -d['dy'], 'dy': d['dx']}
        for s in [-1, 1]:
            tx = cx - d['dx'] * 10 + perp['dx'] * s * 6
            ty = cy - d['dy'] * 10 + perp['dy'] * s * 6
            self.canvas.create_oval(tx - 3, ty - 3, tx + 3, ty + 3, fill='#aa3333', outline='')
        
        tipx = cx + d['dx'] * 14
        tipy = cy + d['dy'] * 14
        basex = cx - d['dx'] * 4
        basey = cy - d['dy'] * 4
        color = '#ff3b3b' if cell['output_active'] else '#884444'
        self.canvas.create_line(basex + perp['dx'] * 6, basey + perp['dy'] * 6, tipx, tipy, fill=color, width=2)
        self.canvas.create_line(basex - perp['dx'] * 6, basey - perp['dy'] * 6, tipx, tipy, fill=color, width=2)
        
        if cell['output_active']:
            self.canvas.create_rectangle(px + 4, py + 4, px + CELL - 4, py + CELL - 4, outline='#ff3b3b', width=2)
        
        mode_text = 'C' if cell['mode'] == 'compare' else 'S'
        self.canvas.create_text(cx, py + 4, text=mode_text, fill='#888', font=('Arial', 7))
    
    def _draw_observer(self, x: int, y: int, cell: Dict):
        px = x * CELL
        py = y * CELL
        cx = px + CELL // 2
        cy = py + CELL // 2
        d = DIRECTIONS[cell['direction']]
        
        self.canvas.create_rectangle(px + 4, py + 4, px + CELL - 4, py + CELL - 4, fill='#2a2a3a', outline='#555', width=1)
        
        facex = cx + d['dx'] * 10
        facey = cy + d['dy'] * 10
        self.canvas.create_rectangle(facex - 5, facey - 5, facex + 5, facey + 5, fill='#555', outline='')
        
        perp = {'dx': -d['dy'], 'dy': d['dx']}
        color = '#ff3b3b' if cell['pulsing'] else '#999'
        self.canvas.create_oval(facex + perp['dx'] * 2 - 2, facey + perp['dy'] * 2 - 2, facex + perp['dx'] * 2 + 2, facey + perp['dy'] * 2 + 2, fill=color, outline='')
        self.canvas.create_oval(facex - perp['dx'] * 2 - 2, facey - perp['dy'] * 2 - 2, facex - perp['dx'] * 2 + 2, facey - perp['dy'] * 2 + 2, fill=color, outline='')
        
        if cell['pulsing']:
            ox = cx - d['dx'] * 14
            oy = cy - d['dy'] * 14
            self.canvas.create_oval(ox - 4, oy - 4, ox + 4, oy + 4, fill='#ff3b3b', outline='')
    
    def _draw_preview(self, x: int, y: int, comp: str):
        px = x * CELL
        py = y * CELL
        self.canvas.create_rectangle(px + 1, py + 1, px + CELL - 1, py + CELL - 1, outline='#4ecca3', width=1, dash=(4, 4))
        
        cx = px + CELL // 2
        cy = py + CELL // 2
        if comp == 'dust':
            self.canvas.create_oval(cx - 4, cy - 4, cx + 4, cy + 4, fill='#5b1010', outline='#8b2020')
        elif comp == 'block':
            self.canvas.create_rectangle(px + 8, py + 8, px + CELL - 8, py + CELL - 8, outline='#8b0000', width=2)
        elif comp == 'torch':
            self.canvas.create_line(cx, cy - 8, cx, cy + 4, fill='#666', width=2)
            self.canvas.create_oval(cx - 4, cy - 12, cx + 4, cy - 4, fill='#ff3333', outline='')
        elif comp == 'repeater':
            self.canvas.create_rectangle(px + 8, py + 8, px + CELL - 8, py + CELL - 8, outline='#3a3a3a', width=2)
            d = DIRECTIONS[self.selected_rotate]
            self.canvas.create_line(cx - d['dx'] * 6, cy - d['dy'] * 6, cx + d['dx'] * 6, cy + d['dy'] * 6, fill='#884444', width=2)
        elif comp == 'comparator':
            self.canvas.create_rectangle(px + 8, py + 8, px + CELL - 8, py + CELL - 8, outline='#3a3a3a', width=2)
            d = DIRECTIONS[self.selected_rotate]
            self.canvas.create_oval(cx + d['dx'] * 6 - 3, cy + d['dy'] * 6 - 3, cx + d['dx'] * 6 + 3, cy + d['dy'] * 6 + 3, fill='#ff3b3b', outline='')
        elif comp == 'observer':
            self.canvas.create_rectangle(px + 8, py + 8, px + CELL - 8, py + CELL - 8, outline='#2a2a3a', width=2)
            d = DIRECTIONS[self.selected_rotate]
            self.canvas.create_rectangle(cx + d['dx'] * 6 - 4, cy + d['dy'] * 6 - 4, cx + d['dx'] * 6 + 4, cy + d['dy'] * 6 + 4, outline='#555', width=1)
    
    def _draw_selection_indicator(self, x: int, y: int, color: str, text: str):
        px = x * CELL
        py = y * CELL
        self.canvas.create_rectangle(px + 2, py + 2, px + CELL - 2, py + CELL - 2, outline=color, width=2, dash=(4, 4))
        self.canvas.create_text(px + CELL // 2, py + 4, text=text, fill=color, font=('Arial', 8))
    
    # ============================================================
    # 模拟控制
    # ============================================================
    
    def on_signal_update(self, signals, powered, delay, duration, strength):
        self._redraw()
        if delay >= 0:
            strength_text = f"强度: {strength}" if self.use_strength_var.get() else ""
            self.result_label.config(text=f"延迟: {delay} tick  持续: {duration} tick  {strength_text}")
            
            target_match = (delay == self.target_delay and duration == self.target_duration)
            if self.use_strength_var.get() and self.target_strength is not None:
                target_match = target_match and (strength == self.target_strength)
            
            if target_match:
                self.status_label.config(text="✅ 匹配目标!", foreground='#4ecca3')
            else:
                status_text = f"⏳ 延迟: {delay}/{self.target_delay}  持续: {duration}/{self.target_duration}"
                if self.use_strength_var.get() and self.target_strength is not None:
                    status_text += f"  强度: {strength}/{self.target_strength}"
                self.status_label.config(text=status_text, foreground='#e94560')
        else:
            self.result_label.config(text="延迟: -  持续: -  强度: -")
            if self.sim.running:
                self.status_label.config(text="⏳ 等待信号...", foreground='#888')
    
    def run_simulation(self):
        if not self.input_points:
            messagebox.showwarning("警告", "请先设置输入点！")
            return
        if not self.output_point:
            messagebox.showwarning("警告", "请先设置输出点！")
            return
        
        self._configure_simulator()
        self.sim.reset()
        self.sim.start()
        self.status_label.config(text="▶ 运行中...", foreground='#4ecca3')
        self._redraw()
    
    def stop_simulation(self):
        self.sim.stop()
        self.status_label.config(text="⏹ 已停止", foreground='#888')
    
    def step_simulation(self):
        if not self.input_points:
            messagebox.showwarning("警告", "请先设置输入点！")
            return
        if not self.output_point:
            messagebox.showwarning("警告", "请先设置输出点！")
            return
        
        self._configure_simulator()
        self.sim.step()
    
    def reset_simulation(self):
        self.sim.reset()
        self._redraw()
        self.result_label.config(text="延迟: -  持续: -  强度: -")
        self.status_label.config(text="↺ 已重置", foreground='#888')
    
    # ============================================================
    # 导出和导入
    # ============================================================
    
    def export_json(self):
        self._save_current_level()
        
        filepath = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if not filepath:
            return
        
        try:
            self.level_data.save_to_file(filepath)
            self.status_label.config(text=f"✅ 已导出到 {filepath}", foreground='#4ecca3')
            messagebox.showinfo("成功", f"已导出 {len(self.level_data.levels)} 个关卡到:\n{filepath}")
        except Exception as e:
            messagebox.showerror("错误", f"导出失败: {e}")
    
    def import_json(self):
        filepath = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if not filepath:
            return
        
        try:
            new_level_data = LevelData()
            new_level_data.load_from_file(filepath)
            
            if len(self.level_data.levels) > 1 or self.level_data.levels[0].get('name') != '新关卡':
                result = messagebox.askyesno("导入选项", 
                    f"当前有 {len(self.level_data.levels)} 个关卡。\n"
                    f"导入文件包含 {len(new_level_data.levels)} 个关卡。\n\n"
                    "点击'是'追加到末尾，点击'否'替换全部。")
                if result:
                    for level in new_level_data.levels:
                        self.level_data.levels.append(level)
                    self.level_data.modified = True
                else:
                    self.level_data.levels = new_level_data.levels
                    self.level_data.modified = True
            else:
                self.level_data.levels = new_level_data.levels
                self.level_data.modified = True
            
            self.level_data.filepath = None
            self.level_data.current_index = 0
            self._load_current_level()
            self._redraw()
            self._update_level_list()
            self.status_label.config(text=f"✅ 已导入 {len(self.level_data.levels)} 个关卡", foreground='#4ecca3')
            self._update_modified_status()
            
        except Exception as e:
            messagebox.showerror("错误", f"导入失败: {e}")


def main():
    root = tk.Tk()
    app = CircuitDesigner(root)
    root.bind('<r>', lambda e: app.rotate_selected())
    root.bind('<R>', lambda e: app.rotate_selected())
    root.mainloop()


if __name__ == '__main__':
    main()