import sys
import os
import json
import shutil
from generator import generate_script
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QListWidget, QPushButton, QLabel, 
                             QStackedWidget, QLineEdit, QComboBox, QFormLayout, 
                             QMessageBox, QInputDialog, QFileDialog, QCheckBox, 
                             QTextEdit, QSplitter, QDialog)
from PyQt5.QtCore import Qt, QProcess, QTimer
from PyQt5.QtGui import QPainter, QColor

class CoordinatePicker(QDialog):
    def __init__(self):
        super().__init__()
        self.picked_x = None
        self.picked_y = None
        
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.CrossCursor)
        
        # 获取所有屏幕组合的总几何区域
        desktop = QApplication.desktop()
        geom = desktop.geometry()
        for i in range(desktop.screenCount()):
            geom = geom.united(desktop.screenGeometry(i))
        self.setGeometry(geom)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.picked_x = event.globalPos().x()
            self.picked_y = event.globalPos().y()
            self.accept()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.reject()

FLOWS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'flows')
SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scripts')
USER_SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'user_scripts')
os.makedirs(FLOWS_DIR, exist_ok=True)
os.makedirs(USER_SCRIPTS_DIR, exist_ok=True)

class RPAMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Choice RPA Studio - Advanced Edition")
        self.setGeometry(100, 100, 1050, 750)
        self.current_flow_name = None
        self.actions = []
        self.process = None

        self.initUI()
        self.load_flows()

    def initUI(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # Left Panel: Flow List
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.addWidget(QLabel("RPA 流程列表"))
        
        self.flow_list = QListWidget()
        self.flow_list.itemClicked.connect(self.on_flow_selected)
        left_layout.addWidget(self.flow_list)

        btn_layout = QHBoxLayout()
        self.btn_new = QPushButton("新建流程")
        self.btn_new.clicked.connect(self.create_flow)
        self.btn_delete = QPushButton("删除流程")
        self.btn_delete.clicked.connect(self.delete_flow)
        btn_layout.addWidget(self.btn_new)
        btn_layout.addWidget(self.btn_delete)
        left_layout.addLayout(btn_layout)

        # Import Buttons
        btn_layout_2 = QHBoxLayout()
        self.btn_import_json = QPushButton("导入 JSON")
        self.btn_import_json.clicked.connect(self.import_json)
        self.btn_import_py = QPushButton("导入 Py脚本")
        self.btn_import_py.clicked.connect(self.import_py)
        btn_layout_2.addWidget(self.btn_import_json)
        btn_layout_2.addWidget(self.btn_import_py)
        left_layout.addLayout(btn_layout_2)

        main_layout.addWidget(left_panel, 2)

        # Right Panel: Flow Editor + Console Splitter
        right_splitter = QSplitter(Qt.Vertical)
        
        # --- Top Half: Flow Editor ---
        editor_widget = QWidget()
        self.right_layout = QVBoxLayout(editor_widget)
        self.lbl_flow_name = QLabel("当前未选择流程")
        self.lbl_flow_name.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.right_layout.addWidget(self.lbl_flow_name)

        # Action Editor List
        self.action_list = QListWidget()
        self.action_list.itemClicked.connect(self.on_action_selected)
        self.right_layout.addWidget(self.action_list)

        # Step Management Buttons
        step_manage_layout = QHBoxLayout()
        self.btn_up = QPushButton("↑ 上移")
        self.btn_down = QPushButton("↓ 下移")
        self.btn_del_step = QPushButton("✕ 删除步骤")
        self.btn_up.clicked.connect(self.move_step_up)
        self.btn_down.clicked.connect(self.move_step_down)
        self.btn_del_step.clicked.connect(self.delete_step)
        step_manage_layout.addWidget(self.btn_up)
        step_manage_layout.addWidget(self.btn_down)
        step_manage_layout.addWidget(self.btn_del_step)
        step_manage_layout.addStretch()
        self.right_layout.addLayout(step_manage_layout)

        # Add / Insert Action Controls
        add_action_layout = QHBoxLayout()
        self.action_type_combo = QComboBox()
        self.action_type_combo.addItems([
            "Wait", "Click XY", "Type Text", "Press Key", 
            "OCR Click (Offset)", "OCR Click Lowest", "OCR Click Right", 
            "Image Click (CV2)", "Open App/File", "Kill Process", "Run Python",
            "Loop (Excel)", "If (OCR Text)", "End Block"
        ])
        self.btn_add_action = QPushButton("插入动作(至选中行下方)")
        self.btn_add_action.clicked.connect(self.add_action)
        self.btn_update_action = QPushButton("更新选中动作")
        self.btn_update_action.clicked.connect(self.update_action)
        
        add_action_layout.addWidget(self.action_type_combo)
        add_action_layout.addWidget(self.btn_add_action)
        add_action_layout.addWidget(self.btn_update_action)
        self.right_layout.addLayout(add_action_layout)

        # Action Configuration Panel (Dynamic)
        self.config_panel = QStackedWidget()
        self.setup_config_panels()
        self.right_layout.addWidget(self.config_panel)

        self.action_type_combo.currentIndexChanged.connect(self.config_panel.setCurrentIndex)

        # Save & Run
        bottom_layout = QHBoxLayout()
        self.btn_save = QPushButton("保存流程")
        self.btn_save.clicked.connect(self.save_flow_with_msg)
        self.btn_run = QPushButton("运行流程")
        self.btn_run.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        self.btn_run.clicked.connect(self.run_flow)
        
        self.btn_stop = QPushButton("强制停止")
        self.btn_stop.setStyleSheet("background-color: #f44336; color: white;")
        self.btn_stop.clicked.connect(self.stop_flow)
        self.btn_stop.setEnabled(False)
        
        bottom_layout.addWidget(self.btn_save)
        bottom_layout.addWidget(self.btn_run)
        bottom_layout.addWidget(self.btn_stop)
        self.right_layout.addLayout(bottom_layout)
        
        right_splitter.addWidget(editor_widget)

        # --- Bottom Half: Console Terminal ---
        console_widget = QWidget()
        console_layout = QVBoxLayout(console_widget)
        console_layout.setContentsMargins(0, 10, 0, 0)
        console_layout.addWidget(QLabel("运行反馈终端 (Console):"))
        self.console_output = QTextEdit()
        self.console_output.setReadOnly(True)
        self.console_output.setStyleSheet("background-color: #1e1e1e; color: #00ff00; font-family: Consolas, monospace;")
        console_layout.addWidget(self.console_output)
        
        btn_clear = QPushButton("清空终端")
        btn_clear.clicked.connect(self.console_output.clear)
        console_layout.addWidget(btn_clear, alignment=Qt.AlignRight)
        
        right_splitter.addWidget(console_widget)
        
        # Set splitter sizes (approx 60% editor, 40% console)
        right_splitter.setSizes([450, 300])
        main_layout.addWidget(right_splitter, 5)

    def setup_config_panels(self):
        # 0. Wait
        wait_widget = QWidget()
        wait_layout = QFormLayout(wait_widget)
        self.input_wait = QLineEdit()
        self.input_wait.setPlaceholderText("秒数, e.g., 2.5")
        wait_layout.addRow("等待时间 (秒):", self.input_wait)
        self.config_panel.addWidget(wait_widget)

        # 1. Click XY
        xy_widget = QWidget()
        xy_layout = QFormLayout(xy_widget)
        self.input_x = QLineEdit()
        self.input_y = QLineEdit()
        self.btn_pick_xy = QPushButton("📍 抓取屏幕坐标 (按 Esc 取消)")
        self.btn_pick_xy.clicked.connect(self.start_coordinate_picker)
        xy_layout.addRow(self.btn_pick_xy)
        xy_layout.addRow("X 坐标:", self.input_x)
        xy_layout.addRow("Y 坐标:", self.input_y)
        self.config_panel.addWidget(xy_widget)

        # 2. Type Text
        type_widget = QWidget()
        type_layout = QFormLayout(type_widget)
        self.input_text = QLineEdit()
        type_layout.addRow("输入内容:", self.input_text)
        self.config_panel.addWidget(type_widget)

        # 3. Press Key
        key_widget = QWidget()
        key_layout = QVBoxLayout(key_widget)
        mod_layout = QHBoxLayout()
        self.chk_ctrl = QCheckBox("Ctrl")
        self.chk_shift = QCheckBox("Shift")
        self.chk_alt = QCheckBox("Alt")
        self.chk_win = QCheckBox("Win")
        mod_layout.addWidget(self.chk_ctrl)
        mod_layout.addWidget(self.chk_shift)
        mod_layout.addWidget(self.chk_alt)
        mod_layout.addWidget(self.chk_win)
        mod_layout.addStretch()
        input_layout = QFormLayout()
        self.input_main_key = QLineEdit()
        self.input_main_key.setPlaceholderText("在此输入主按键 (如: d, enter, f9)")
        input_layout.addRow("主按键:", self.input_main_key)
        key_layout.addLayout(mod_layout)
        key_layout.addLayout(input_layout)
        self.config_panel.addWidget(key_widget)

        # 4. OCR Click (Offset)
        ocr_off_widget = QWidget()
        ocr_off_layout = QFormLayout(ocr_off_widget)
        self.in_ocr_text = QLineEdit()
        self.in_ocr_x_off = QLineEdit("0")
        self.in_ocr_y_off = QLineEdit("0")
        ocr_off_layout.addRow("目标文字:", self.in_ocr_text)
        ocr_off_layout.addRow("X 偏移量:", self.in_ocr_x_off)
        ocr_off_layout.addRow("Y 偏移量:", self.in_ocr_y_off)
        self.config_panel.addWidget(ocr_off_widget)

        # 5. OCR Click Lowest
        ocr_low_widget = QWidget()
        ocr_low_layout = QFormLayout(ocr_low_widget)
        self.in_low_text = QLineEdit()
        self.in_low_exact = QCheckBox("精确匹配 (Exact Match)")
        self.in_low_x_off = QLineEdit("0")
        self.in_low_y_off = QLineEdit("0")
        ocr_low_layout.addRow("目标文字:", self.in_low_text)
        ocr_low_layout.addRow("", self.in_low_exact)
        ocr_low_layout.addRow("X 偏移量:", self.in_low_x_off)
        ocr_low_layout.addRow("Y 偏移量:", self.in_low_y_off)
        self.config_panel.addWidget(ocr_low_widget)

        # 6. OCR Click Right Of
        ocr_right_widget = QWidget()
        ocr_right_layout = QFormLayout(ocr_right_widget)
        self.in_right_text = QLineEdit()
        self.in_right_mult = QLineEdit("0.5")
        ocr_right_layout.addRow("锚点文字:", self.in_right_text)
        ocr_right_layout.addRow("向右偏移倍数:", self.in_right_mult)
        self.config_panel.addWidget(ocr_right_widget)

        # 7. Image Click (CV2)
        img_widget = QWidget()
        img_layout = QFormLayout(img_widget)
        self.in_img_path = QLineEdit()
        self.btn_browse_img = QPushButton("浏览...")
        self.btn_browse_img.clicked.connect(self.browse_img_file)
        img_hbox = QHBoxLayout()
        img_hbox.addWidget(self.in_img_path)
        img_hbox.addWidget(self.btn_browse_img)
        self.in_img_thresh = QLineEdit("0.85")
        img_layout.addRow("图片路径:", img_hbox)
        img_layout.addRow("匹配阈值:", self.in_img_thresh)
        self.config_panel.addWidget(img_widget)

        # 8. Open App
        open_app_widget = QWidget()
        open_app_layout = QFormLayout(open_app_widget)
        self.input_app_path = QLineEdit()
        self.btn_browse_app = QPushButton("浏览...")
        self.btn_browse_app.clicked.connect(self.browse_app_file)
        app_hbox = QHBoxLayout()
        app_hbox.addWidget(self.input_app_path)
        app_hbox.addWidget(self.btn_browse_app)
        open_app_layout.addRow("应用路径:", app_hbox)
        self.config_panel.addWidget(open_app_widget)

        # 9. Kill Process
        kill_widget = QWidget()
        kill_layout = QFormLayout(kill_widget)
        self.input_process_name = QLineEdit()
        self.input_process_name.setPlaceholderText("例如: excel.exe")
        kill_layout.addRow("进程名称:", self.input_process_name)
        self.config_panel.addWidget(kill_widget)

        # 10. Run Python
        py_widget = QWidget()
        py_layout = QFormLayout(py_widget)
        self.input_py_path = QLineEdit()
        self.btn_browse_py = QPushButton("浏览...")
        self.btn_browse_py.clicked.connect(self.browse_py_file)
        py_hbox = QHBoxLayout()
        py_hbox.addWidget(self.input_py_path)
        py_hbox.addWidget(self.btn_browse_py)
        py_layout.addRow("Python脚本:", py_hbox)
        self.config_panel.addWidget(py_widget)

        # 11. Loop (Excel)
        loop_widget = QWidget()
        loop_layout = QFormLayout(loop_widget)
        self.input_loop_excel = QLineEdit()
        self.btn_browse_loop = QPushButton("浏览...")
        self.btn_browse_loop.clicked.connect(self.browse_loop_excel)
        loop_hbox = QHBoxLayout()
        loop_hbox.addWidget(self.input_loop_excel)
        loop_hbox.addWidget(self.btn_browse_loop)
        
        self.combo_col_type = QComboBox()
        self.combo_col_type.addItems(["列名 (Header)", "列索引 (Index)"])
        self.input_loop_col = QLineEdit()
        self.input_loop_var = QLineEdit("item")
        
        loop_layout.addRow("Excel 路径:", loop_hbox)
        loop_layout.addRow("定位方式:", self.combo_col_type)
        loop_layout.addRow("具体列名/索引:", self.input_loop_col)
        loop_layout.addRow("变量名 (代码中引用):", self.input_loop_var)
        self.config_panel.addWidget(loop_widget)

        # 12. If (OCR Text)
        if_widget = QWidget()
        if_layout = QFormLayout(if_widget)
        self.input_if_text = QLineEdit()
        if_layout.addRow("如果看到文字:", self.input_if_text)
        if_layout.addRow(QLabel("(存在则执行后续缩进内的动作)"))
        self.config_panel.addWidget(if_widget)

        # 13. End Block
        end_widget = QWidget()
        end_layout = QVBoxLayout(end_widget)
        end_layout.addWidget(QLabel("--- 逻辑块结束标志 (End Block) ---"))
        end_layout.addWidget(QLabel("用于结束上方的 Loop 或 If 结构。"))
        self.config_panel.addWidget(end_widget)

    def browse_loop_excel(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择数据源 Excel", "", "Excel Files (*.xlsx *.xls)")
        if file_path:
            self.input_loop_excel.setText(file_path)


    def browse_py_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择 Python 脚本", "", "Python Files (*.py)")
        if file_path:
            self.input_py_path.setText(file_path)

    def browse_app_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择可执行文件", "", "Executable Files (*.exe);;All Files (*)")
        if file_path:
            self.input_app_path.setText(file_path)

    def browse_img_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择模板图片", "", "Image Files (*.png *.jpg *.jpeg)")
        if file_path:
            self.in_img_path.setText(file_path)

    def start_coordinate_picker(self):
        self.showMinimized()
        # Delay the overlay slightly so the window has time to minimize
        QTimer.singleShot(200, self.show_picker_overlay)

    def show_picker_overlay(self):
        global global_picker
        global_picker = CoordinatePicker()
        if global_picker.exec_() == QDialog.Accepted:
            self.on_coordinate_picked(global_picker.picked_x, global_picker.picked_y)
        else:
            self.on_coordinate_picked(None, None)
        global_picker = None

    def on_coordinate_picked(self, x, y):
        if x is not None and y is not None:
            self.input_x.setText(str(x))
            self.input_y.setText(str(y))
        self.showNormal()
        self.activateWindow()

    # --- Flow Management ---
    def import_json(self):
        file_paths, _ = QFileDialog.getOpenFileNames(self, "导入流程 JSON", "", "JSON Files (*.json)")
        if file_paths:
            for file_path in file_paths:
                dest = os.path.join(FLOWS_DIR, os.path.basename(file_path))
                shutil.copy(file_path, dest)
            self.load_flows()
            QMessageBox.information(self, "成功", f"成功导入 {len(file_paths)} 个流程！")

    def import_py(self):
        file_paths, _ = QFileDialog.getOpenFileNames(self, "导入 Python 脚本", "", "Python Files (*.py)")
        if file_paths:
            count = 0
            for file_path in file_paths:
                name = os.path.splitext(os.path.basename(file_path))[0]
                dest = os.path.join(USER_SCRIPTS_DIR, os.path.basename(file_path))
                shutil.copy(file_path, dest)
                
                flow_path = os.path.join(FLOWS_DIR, f"{name}_py.json")
                actions = [{"type": "Run Python", "script_path": dest}]
                with open(flow_path, 'w', encoding='utf-8') as f:
                    json.dump(actions, f, ensure_ascii=False, indent=4)
                count += 1
            self.load_flows()
            QMessageBox.information(self, "成功", f"成功导入并将 {count} 个 Python 脚本封装为独立流程！")

    def load_flows(self):
        self.flow_list.clear()
        if not os.path.exists(FLOWS_DIR):
            return
        for file in os.listdir(FLOWS_DIR):
            if file.endswith('.json'):
                self.flow_list.addItem(file[:-5])

    def create_flow(self):
        name, ok = QInputDialog.getText(self, "新建流程", "请输入流程名称:")
        if ok and name:
            file_path = os.path.join(FLOWS_DIR, f"{name}.json")
            if os.path.exists(file_path):
                QMessageBox.warning(self, "错误", "同名流程已存在！")
                return
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump([], f)
            self.load_flows()
            
            items = self.flow_list.findItems(name, Qt.MatchExactly)
            if items:
                self.flow_list.setCurrentItem(items[0])
                self.on_flow_selected(items[0])

    def delete_flow(self):
        item = self.flow_list.currentItem()
        if not item:
            return
        name = item.text()
        reply = QMessageBox.question(self, '确认', f"确定要删除流程 '{name}' 吗?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            file_path = os.path.join(FLOWS_DIR, f"{name}.json")
            if os.path.exists(file_path):
                os.remove(file_path)
            self.load_flows()
            self.current_flow_name = None
            self.lbl_flow_name.setText("当前未选择流程")
            self.action_list.clear()
            self.actions = []

    def on_flow_selected(self, item):
        self.current_flow_name = item.text()
        self.lbl_flow_name.setText(f"当前编辑: {self.current_flow_name}")
        self.load_current_flow()

    def load_current_flow(self):
        self.action_list.clear()
        self.actions = []
        if not self.current_flow_name:
            return
            
        file_path = os.path.join(FLOWS_DIR, f"{self.current_flow_name}.json")
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    self.actions = json.load(f)
                self.render_action_list()
            except Exception as e:
                QMessageBox.warning(self, "错误", f"加载流程失败: {str(e)}")

    def render_action_list(self):
        self.action_list.clear()
        depth = 0
        for action in self.actions:
            action_type = action.get('type')
            
            # End Block reduces indent before being rendered
            if action_type == 'End Block':
                depth = max(0, depth - 1)
            
            indent = "    " * depth
            prefix = "└── " if depth > 0 else ""
            
            params_str = ""
            
            if action_type == 'Wait':
                params_str = f"{action.get('seconds', 0)} s"
            elif action_type == 'Click XY':
                params_str = f"({action.get('x')}, {action.get('y')})"
            elif action_type == 'Type Text':
                params_str = f"'{action.get('text')}'"
            elif action_type == 'Press Key':
                params_str = f"'{action.get('key')}'"
            elif action_type == 'OCR Click (Offset)':
                params_str = f"'{action.get('text')}' Offset({action.get('x_off')}, {action.get('y_off')})"
            elif action_type == 'OCR Click Lowest':
                ex = "Exact" if action.get('exact') else "Has"
                params_str = f"'{action.get('text')}' [{ex}] Offset({action.get('x_off')}, {action.get('y_off')})"
            elif action_type == 'OCR Click Right':
                params_str = f"'{action.get('text')}' x {action.get('mult')} width"
            elif action_type == 'Image Click (CV2)':
                params_str = f"'{os.path.basename(action.get('path', ''))}' Thresh:{action.get('thresh')}"
            elif action_type in ('Open App/File', 'Open App'):
                params_str = f"'{os.path.basename(action.get('path', ''))}'"
            elif action_type == 'Kill Process':
                params_str = f"'{action.get('process_name')}'"
            elif action_type == 'Run Python':
                params_str = f"'{os.path.basename(action.get('script_path', ''))}'"
            elif action_type == 'Loop (Excel)':
                params_str = f"File: {os.path.basename(action.get('excel_path',''))} Var: {action.get('var_name')}"
            elif action_type == 'If (OCR Text)':
                params_str = f"Contains: '{action.get('text')}'"
            elif action_type == 'End Block':
                params_str = "---"
                
            display_text = f"{indent}{prefix}[{action_type}]  {params_str}"
            self.action_list.addItem(display_text)
            
            # Start Block increases indent for the NEXT actions
            if action_type in ('Loop (Excel)', 'If (OCR Text)'):
                depth += 1

    # --- Step Management (Up/Down/Del/Edit) ---
    def on_action_selected(self, item):
        row = self.action_list.row(item)
        action = self.actions[row]
        action_type = action.get('type')
        
        idx = self.action_type_combo.findText(action_type)
        if idx >= 0:
            self.action_type_combo.setCurrentIndex(idx)
            
        if action_type == 'Wait':
            self.input_wait.setText(str(action.get('seconds', '')))
        elif action_type == 'Click XY':
            self.input_x.setText(str(action.get('x', '')))
            self.input_y.setText(str(action.get('y', '')))
        elif action_type == 'Type Text':
            self.input_text.setText(str(action.get('text', '')))
        elif action_type == 'Press Key':
            key_str = action.get('key', '')
            self.chk_ctrl.setChecked('ctrl' in key_str.lower())
            self.chk_shift.setChecked('shift' in key_str.lower())
            self.chk_alt.setChecked('alt' in key_str.lower())
            self.chk_win.setChecked('win' in key_str.lower())
            
            # extract main key
            parts = key_str.split('+')
            main_k = parts[-1] if parts else ''
            self.input_main_key.setText(main_k)
        elif action_type == 'OCR Click (Offset)':
            self.in_ocr_text.setText(action.get('text', ''))
            self.in_ocr_x_off.setText(str(action.get('x_off', 0)))
            self.in_ocr_y_off.setText(str(action.get('y_off', 0)))
        elif action_type == 'OCR Click Lowest':
            self.in_low_text.setText(action.get('text', ''))
            self.in_low_exact.setChecked(action.get('exact', False))
            self.in_low_x_off.setText(str(action.get('x_off', 0)))
            self.in_low_y_off.setText(str(action.get('y_off', 0)))
        elif action_type == 'OCR Click Right':
            self.in_right_text.setText(action.get('text', ''))
            self.in_right_mult.setText(str(action.get('mult', 0.5)))
        elif action_type == 'Image Click (CV2)':
            self.in_img_path.setText(action.get('path', ''))
            self.in_img_thresh.setText(str(action.get('thresh', 0.85)))
        elif action_type in ('Open App/File', 'Open App'):
            self.input_app_path.setText(action.get('path', ''))
        elif action_type == 'Kill Process':
            self.input_process_name.setText(action.get('process_name', ''))
        elif action_type == 'Run Python':
            self.input_py_path.setText(action.get('script_path', ''))
        elif action_type == 'Loop (Excel)':
            self.input_loop_excel.setText(action.get('excel_path', ''))
            self.combo_col_type.setCurrentText(action.get('col_type', ''))
            self.input_loop_col.setText(str(action.get('col_val', '')))
            self.input_loop_var.setText(action.get('var_name', 'item'))
        elif action_type == 'If (OCR Text)':
            self.input_if_text.setText(action.get('text', ''))

    def move_step_up(self):
        row = self.action_list.currentRow()
        if row > 0:
            self.actions[row - 1], self.actions[row] = self.actions[row], self.actions[row - 1]
            self.render_action_list()
            self.action_list.setCurrentRow(row - 1)
            self.save_flow()

    def move_step_down(self):
        row = self.action_list.currentRow()
        if 0 <= row < len(self.actions) - 1:
            self.actions[row + 1], self.actions[row] = self.actions[row], self.actions[row + 1]
            self.render_action_list()
            self.action_list.setCurrentRow(row + 1)
            self.save_flow()

    def delete_step(self):
        row = self.action_list.currentRow()
        if row >= 0:
            del self.actions[row]
            self.render_action_list()
            if row < self.action_list.count():
                self.action_list.setCurrentRow(row)
            else:
                self.action_list.setCurrentRow(self.action_list.count() - 1)
            self.save_flow()

    def get_action_data_from_ui(self):
        action_type = self.action_type_combo.currentText()
        action_data = {'type': action_type}

        try:
            if action_type == 'Wait':
                action_data['seconds'] = float(self.input_wait.text() or "0")
            elif action_type == 'Click XY':
                action_data['x'] = int(self.input_x.text() or "0")
                action_data['y'] = int(self.input_y.text() or "0")
            elif action_type == 'Type Text':
                action_data['text'] = self.input_text.text()
            elif action_type == 'Press Key':
                mods = []
                if self.chk_ctrl.isChecked(): mods.append('ctrl')
                if self.chk_shift.isChecked(): mods.append('shift')
                if self.chk_alt.isChecked(): mods.append('alt')
                if self.chk_win.isChecked(): mods.append('win')
                
                main_k = self.input_main_key.text().strip().lower()
                if not main_k:
                    QMessageBox.warning(self, "输入错误", "请输入主按键！")
                    return None
                    
                if mods:
                    action_data['key'] = '+'.join(mods + [main_k])
                else:
                    action_data['key'] = main_k
            elif action_type == 'OCR Click (Offset)':
                action_data['text'] = self.in_ocr_text.text()
                action_data['x_off'] = int(self.in_ocr_x_off.text() or "0")
                action_data['y_off'] = int(self.in_ocr_y_off.text() or "0")
                if not action_data['text']: raise ValueError("需要文本")
            elif action_type == 'OCR Click Lowest':
                action_data['text'] = self.in_low_text.text()
                action_data['exact'] = self.in_low_exact.isChecked()
                action_data['x_off'] = int(self.in_low_x_off.text() or "0")
                action_data['y_off'] = int(self.in_low_y_off.text() or "0")
                if not action_data['text']: raise ValueError("需要文本")
            elif action_type == 'OCR Click Right':
                action_data['text'] = self.in_right_text.text()
                action_data['mult'] = float(self.in_right_mult.text() or "0.5")
                if not action_data['text']: raise ValueError("需要文本")
            elif action_type == 'Image Click (CV2)':
                action_data['path'] = self.in_img_path.text()
                action_data['thresh'] = float(self.in_img_thresh.text() or "0.85")
                if not os.path.exists(action_data['path']):
                    QMessageBox.warning(self, "输入错误", "图片路径不存在！")
                    return None
            elif action_type == 'Open App/File':
                action_data['path'] = self.input_app_path.text()
                if not action_data['path']:
                    QMessageBox.warning(self, "输入错误", "请输入应用或文件路径！")
                    return None
            elif action_type == 'Kill Process':
                action_data['process_name'] = self.input_process_name.text().strip()
                if not action_data['process_name']:
                    QMessageBox.warning(self, "输入错误", "请输入进程名称！")
                    return None
            elif action_type == 'Run Python':
                path = self.input_py_path.text()
                if not path or not os.path.exists(path):
                    QMessageBox.warning(self, "输入错误", "有效的 Python 脚本路径！")
                    return None
                action_data['script_path'] = path
            elif action_type == 'Loop (Excel)':
                action_data['excel_path'] = self.input_loop_excel.text()
                action_data['col_type'] = self.combo_col_type.currentText()
                action_data['col_val'] = self.input_loop_col.text()
                action_data['var_name'] = self.input_loop_var.text()
                if not os.path.exists(action_data['excel_path']):
                    QMessageBox.warning(self, "输入错误", "Excel 路径不存在！")
                    return None
            elif action_type == 'If (OCR Text)':
                action_data['text'] = self.input_if_text.text()
                if not action_data['text']: raise ValueError("需要文本")
            elif action_type == 'End Block':
                pass # No extra data needed

            return action_data
        except ValueError as e:
            QMessageBox.warning(self, "输入错误", "参数格式不正确或缺失必要值！")
            return None


    def add_action(self):
        if not self.current_flow_name:
            QMessageBox.warning(self, "提示", "请先选择或新建一个流程！")
            return
            
        action_data = self.get_action_data_from_ui()
        if not action_data:
            return

        row = self.action_list.currentRow()
        if row >= 0:
            self.actions.insert(row + 1, action_data)
            self.render_action_list()
            self.action_list.setCurrentRow(row + 1)
        else:
            self.actions.append(action_data)
            self.render_action_list()
            self.action_list.setCurrentRow(len(self.actions) - 1)
        self.save_flow()

    def update_action(self):
        row = self.action_list.currentRow()
        if row < 0:
            QMessageBox.warning(self, "提示", "请先在列表中选中要更新的动作！")
            return
            
        action_data = self.get_action_data_from_ui()
        if not action_data:
            return
            
        self.actions[row] = action_data
        self.render_action_list()
        self.action_list.setCurrentRow(row)
        self.save_flow()

    def save_flow_with_msg(self):
        if self.save_flow():
            QMessageBox.information(self, "成功", "流程保存成功！")

    def save_flow(self):
        if not self.current_flow_name:
            return False
        file_path = os.path.join(FLOWS_DIR, f"{self.current_flow_name}.json")
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.actions, f, ensure_ascii=False, indent=4)
            return True
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败: {str(e)}")
            return False

    # --- Terminal & Execution ---
    def run_flow(self):
        if not self.current_flow_name:
            QMessageBox.warning(self, "提示", "请先选择一个流程！")
            return
            
        if self.process and self.process.state() == QProcess.Running:
            QMessageBox.warning(self, "提示", "已有流程正在运行中！")
            return
            
        self.save_flow()
        
        if not os.path.exists(SCRIPTS_DIR):
            os.makedirs(SCRIPTS_DIR)
            
        try:
            script_path = generate_script(self.current_flow_name, self.actions, SCRIPTS_DIR)
            
            self.console_output.clear()
            self.console_output.append(f"启动 {self.current_flow_name} 的执行脚本...")
            
            self.btn_run.setEnabled(False)
            self.btn_stop.setEnabled(True)
            
            self.process = QProcess(self)
            self.process.setProcessChannelMode(QProcess.MergedChannels)
            self.process.readyReadStandardOutput.connect(self.handle_stdout)
            self.process.finished.connect(self.process_finished)
            
            # Use -u for unbuffered python output
            self.process.start(sys.executable, ['-u', script_path])
            
        except Exception as e:
            QMessageBox.critical(self, "执行错误", f"运行失败: {str(e)}")
            self.btn_run.setEnabled(True)
            self.btn_stop.setEnabled(False)

    def handle_stdout(self):
        if not self.process:
            return
        data = self.process.readAllStandardOutput()
        try:
            # Console outputs on Windows are usually GBK
            text = data.data().decode('gbk', errors='replace')
        except:
            text = data.data().decode('utf-8', errors='replace')
            
        self.console_output.append(text.strip())
        # Scroll to bottom
        cursor = self.console_output.textCursor()
        cursor.movePosition(cursor.End)
        self.console_output.setTextCursor(cursor)

    def process_finished(self):
        self.console_output.append("\n[系统提示] 脚本进程已结束。")
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.process = None

    def stop_flow(self):
        if self.process and self.process.state() == QProcess.Running:
            self.process.kill()
            self.console_output.append("\n[系统提示] 已强制停止流程执行！")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = RPAMainWindow()
    window.show()
    sys.exit(app.exec_())
