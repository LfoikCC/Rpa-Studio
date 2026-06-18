import os
import time
import pandas as pd
import pyautogui
import pygetwindow as gw
import cv2
import numpy as np
from rapidocr_onnxruntime import RapidOCR
import pyperclip
import shutil

# ----------------- 配置区 -----------------
EXCEL_PATH = r"D:\昊志机电\同行数据取数\conf\同行公司代码.xlsx"
DATA_DIR = r"D:\昊志机电\同行数据取数\data"

os.makedirs(os.path.join(DATA_DIR, "三大表"), exist_ok=True)
os.makedirs(os.path.join(DATA_DIR, "三小表"), exist_ok=True)
os.makedirs(os.path.join(DATA_DIR, "应付账款"), exist_ok=True)

ocr_engine = RapidOCR()
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.5

# ----------------- 核心工具函数 -----------------

def clear_directories():
    print("开始清空历史数据文件夹...")
    for folder in ["三大表", "三小表", "应付账款"]:
        dir_path = os.path.join(DATA_DIR, folder)
        if os.path.exists(dir_path):
            for filename in os.listdir(dir_path):
                file_path = os.path.join(dir_path, filename)
                try:
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                except Exception as e:
                    print(f"无法删除 {file_path}: {e}")
    print("清空完毕！")

def open_choice():
    print("正在启动 Choice 金融终端...")
    CHOICE_PATH = r"D:\choice\Choice.exe"
    import subprocess
    try:
        subprocess.Popen(CHOICE_PATH)
    except Exception as e:
        print(f"启动 Choice 失败: {e}")
        return False
        
    print("等待登录界面加载 (8秒)...")
    time.sleep(8) 
    
    print("正在自动输入账号密码...")
    pyautogui.hotkey('ctrl', 'a')
    pyautogui.press('delete')
    pyautogui.typewrite("shhxgq0001", interval=0.05)
    time.sleep(0.5)
    
    pyautogui.press('tab')
    time.sleep(0.5)
    pyautogui.hotkey('ctrl', 'a')
    pyautogui.press('delete')
    pyautogui.typewrite("qg543534", interval=0.05)
    time.sleep(0.5)
    
    print("提交登录...")
    pyautogui.press('enter')
    
    print("登录请求已发送，等待软件完全加载进入主界面 (15秒)...")
    time.sleep(15)
    return True

def activate_choice():
    """激活并前置 Choice 窗口，未打开时自动启动并登录"""
    windows = gw.getWindowsWithTitle("Choice金融终端")
    if windows:
        win = windows[0]
        if win.isMinimized:
            win.restore()
        try:
            win.activate()
        except:
            pass
        time.sleep(1)
        return True
        
    print("未找到 Choice金融终端 窗口，准备自动启动并登录...")
    if not open_choice():
        return False
    
    # 循环尝试寻找刚启动的窗口
    print("正在等待 Choice 窗口出现...")
    for _ in range(15):
        windows = gw.getWindowsWithTitle("Choice金融终端")
        if windows:
            win = windows[0]
            if win.isMinimized:
                win.restore()
            try:
                win.activate()
            except:
                pass
            time.sleep(1)
            print("Choice 窗口已成功激活。")
            return True
        time.sleep(2)
        
    print("未能成功识别到启动后的 Choice 主界面。")
    return False

def click_ocr(target_text, retry=3, click_offset=(0, 0)):
    """OCR 识别文字并点击"""
    for _ in range(retry):
        img = cv2.cvtColor(np.array(pyautogui.screenshot()), cv2.COLOR_RGB2BGR)
        result, _ = ocr_engine(img)
        if result:
            for box, text, score in result:
                if target_text in text:
                    cx = (box[0][0] + box[2][0]) / 2 + click_offset[0]
                    cy = (box[0][1] + box[2][1]) / 2 + click_offset[1]
                    pyautogui.click(cx, cy)
                    time.sleep(1)
                    return True
        time.sleep(1)
    return False

def click_ocr_lowest(target_text, retry=3, click_offset=(0, 0), exact_match=False):
    """OCR 识别文字并点击屏幕上最下方的那一个匹配项（适用于搜索框下方弹出的浮窗）"""
    for _ in range(retry):
        img = cv2.cvtColor(np.array(pyautogui.screenshot()), cv2.COLOR_RGB2BGR)
        result, _ = ocr_engine(img)
        if result:
            matches = []
            for box, text, score in result:
                clean_text = text.strip().replace(" ", "")
                match = (target_text == clean_text) if exact_match else (target_text in clean_text)
                if match:
                    cx = (box[0][0] + box[2][0]) / 2 + click_offset[0]
                    cy = (box[0][1] + box[2][1]) / 2 + click_offset[1]
                    matches.append((cx, cy, clean_text))
            
            if matches:
                matches.sort(key=lambda x: x[1], reverse=True)
                target_cx, target_cy, target_text_found = matches[0]
                print(f"     [OCR] 找到 '{target_text_found}' (最下方)! 坐标: ({target_cx}, {target_cy})，正在点击...")
                pyautogui.click(target_cx, target_cy)
                time.sleep(1)
                return True
        time.sleep(1)
    return False

def click_to_right_of(target_text, width_multiplier=0.5, retry=3):
    """
    终极分辨率无关方案：寻找目标文字，根据该文字自身的宽度，向右按比例偏移点击。
    这样不管在什么分辨率下，都能完美点击到文字旁边紧挨着的无文字小图标。
    """
    for _ in range(retry):
        img = cv2.cvtColor(np.array(pyautogui.screenshot()), cv2.COLOR_RGB2BGR)
        result, _ = ocr_engine(img)
        if result:
            for box, text, score in result:
                if target_text in text:
                    x_left = box[0][0]
                    x_right = box[1][0]
                    y_center = (box[0][1] + box[2][1]) / 2
                    
                    text_width = x_right - x_left
                    # 在文字的右边界基础上，再向右偏移 倍数*自身宽度
                    target_x = x_right + (text_width * width_multiplier)
                    
                    print(f"     [动态定位] 找到锚点 '{text}' (宽度:{text_width:.1f})，向右点击坐标: ({target_x:.1f}, {y_center:.1f})")
                    pyautogui.click(target_x, y_center)
                    time.sleep(1)
                    return True
        time.sleep(1)
    return False

def find_image_cv2(template_path, threshold=0.85):
    """使用 OpenCV 原生模板匹配，彻底解决 pyautogui 在纯色背景下的误判问题"""
    img = pyautogui.screenshot()
    img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    
    # 修复 cv2.imread 无法读取包含中文路径（Choice取数工具）的问题
    try:
        template = cv2.imdecode(np.fromfile(template_path, dtype=np.uint8), cv2.IMREAD_COLOR)
    except Exception as e:
        print(f"     [OpenCV] 图像加载失败: {e}")
        return None
        
    if template is None:
        return None
        
    res = cv2.matchTemplate(img_cv, template, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
    print(f"     [OpenCV] 图像匹配最高置信度: {max_val:.4f}，坐标: {max_loc}")
    if max_val >= threshold:
        h, w = template.shape[:2]
        center_x = max_loc[0] + w // 2
        center_y = max_loc[1] + h // 2
        return center_x, center_y
    return None

# ----------------- 业务逻辑 -----------------

LAST_SEARCH_TEXT = None

def get_ocr_matches(target_text, exact_match=False):
    """返回屏幕上所有匹配的文字及其坐标，按Y坐标从上到下排序"""
    img = cv2.cvtColor(np.array(pyautogui.screenshot()), cv2.COLOR_RGB2BGR)
    result, _ = ocr_engine(img)
    matches = []
    if result:
        for box, text, score in result:
            clean_text = text.strip().replace(" ", "")
            if exact_match:
                match = (target_text == clean_text)
            else:
                match = (target_text in clean_text)
                
            if match:
                cx = (box[0][0] + box[2][0]) / 2
                cy = (box[0][1] + box[2][1]) / 2
                matches.append((cx, cy, clean_text))
    matches.sort(key=lambda x: x[1])
    return matches

def click_search_box(last_text=None):
    """智能寻找左上角的专属搜索框"""
    for _ in range(3):
        matches = get_ocr_matches("支持栏目全称") or get_ocr_matches("首字母检索")
        if matches:
            pyautogui.click(matches[0][0], matches[0][1])
            return True
        if last_text:
            matches = get_ocr_matches(last_text, exact_match=True)
            if matches:
                pyautogui.click(matches[0][0], matches[0][1])
                return True
        time.sleep(1)
    return False

def click_dropdown_item(target_text):
    """点击搜索框下方弹出的浮窗中对应的精确报表名"""
    for i in range(4):
        matches = get_ocr_matches(target_text, exact_match=True)
        if len(matches) >= 2:
            cx, cy, txt = matches[1] 
            print(f"     [OCR] 找到精准浮窗项 '{txt}'! 坐标: ({cx}, {cy})，正在点击...")
            pyautogui.click(cx, cy)
            return True
        elif len(matches) == 1:
            print(f"     [OCR] 仅找到 1 个精准 '{target_text}'，等待浮窗弹出 (重试 {i+1})...")
        time.sleep(1.5)
    return False

def search_company(code):
    """在主界面的右下角搜索框搜索公司并进入公司页面"""
    global LAST_SEARCH_TEXT
    LAST_SEARCH_TEXT = None 
    
    # 确保股票代码补齐 6 位，例如 2520 -> 002520
    padded_code = str(code).zfill(6)
    
    print(f"\n=====================================")
    print(f"[{padded_code}] 开始处理新公司...")
    activate_choice()
    
    screen_w, screen_h = pyautogui.size()
    pyautogui.click(screen_w // 2, screen_h // 2)
    time.sleep(0.5)
    
    print(f"  -> 搜索代码: {padded_code}")
    pyautogui.press('esc')
    time.sleep(0.5)
    
    pyautogui.typewrite(padded_code, interval=0.1)
    time.sleep(1)
    
    pyautogui.press('enter')
    
    print(f"  -> 等待公司页面加载...")
    time.sleep(5)

def enter_f9_and_search_report(report_name):
    """在公司页面按 F9 进入深度资料并查找具体报表"""
    global LAST_SEARCH_TEXT
    print(f"  -> 准备导出: {report_name}")
    
    print("     按下 F9 进入深度资料...")
    pyautogui.press('f9')
    time.sleep(4) 
    
    print(f"     在深度资料中定位搜索框...")
    if click_search_box(LAST_SEARCH_TEXT):
        pyautogui.hotkey('ctrl', 'a')
        pyautogui.press('backspace')
    else:
        print("     [警告] 未找到专用的栏目搜索框，尝试在固定坐标(约左上角)点击...")
        pyautogui.click(100, 240)
        pyautogui.hotkey('ctrl', 'a')
        pyautogui.press('backspace')

    time.sleep(0.5)
    
    pyperclip.copy(report_name)
    pyautogui.hotkey('ctrl', 'v')
    time.sleep(2) 
    
    print(f"     OCR 查找并点击下方浮窗: {report_name}")
    success = click_dropdown_item(report_name)
    
    if not success:
        print(f"     [中断] 无法在浮窗中找到精准报表 '{report_name}'，终止该报表后续操作！")
        return False
        
    LAST_SEARCH_TEXT = report_name
    time.sleep(3) 
    return True

def do_export_custom(save_path_dir, file_name):
    """执行导出并处理 Choice 专属的下载弹窗（如三大表、EDE表）"""
    print(f"     正在执行导出...")
    
    print("     等待下载弹窗...")
    time.sleep(2) 
    
    pyautogui.hotkey('ctrl', 'a')
    pyautogui.press('backspace')
    pyperclip.copy(file_name)
    pyautogui.hotkey('ctrl', 'v')
    time.sleep(0.5)
    
    print("     OCR 寻找'保存路径'或'下载到'并点击输入框...")
    # 根据用户截图，"保存路径"这四个字是在输入框的正上方！
    # 所以需要向下偏移大约 30 像素才能点进输入框，而不是向右偏移
    if click_ocr("保存路径", retry=2, click_offset=(0, 30)) or click_ocr("下载到", retry=1, click_offset=(100, 0)):
        time.sleep(0.5)
        pyautogui.hotkey('ctrl', 'a')
        pyautogui.press('backspace')
        pyperclip.copy(save_path_dir)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.5)
    else:
        print("     [警告] 未找到'保存路径'或'下载到'标签，尝试使用 Tab 键切换...")
        pyautogui.press('tab')
        time.sleep(0.5)
        pyautogui.hotkey('ctrl', 'a')
        pyautogui.press('backspace')
        pyperclip.copy(save_path_dir)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.5)
    
    print("     强制使用 OCR 点击底部 '保存' 按钮...")
    # 必须使用 click_ocr_lowest 且精确匹配，防止点到界面右上角的“保存模板”或上方的“保存路径”
    if click_ocr_lowest("保存", retry=3, exact_match=True):
        time.sleep(2) 
        return True
    else:
        # 兜底：如果精确匹配不到，找最下面的“保存”
        if click_ocr_lowest("保存", retry=2):
            time.sleep(2)
            return True
        print("     [错误] 未能在弹窗中找到保存按钮！")
        return False

def do_export_windows(save_path_dir, file_name):
    """执行导出并处理系统自带的文件资源管理器弹窗（如三小表）"""
    print(f"     正在执行 Windows 系统弹窗导出...")

    # 【修复】确保焦点在右侧数据展示区，否则向上滚动的是左侧菜单栏
    screen_w, screen_h = pyautogui.size()
    pyautogui.click(screen_w * 3 // 4, screen_h // 2)
    time.sleep(0.5)

    # 确保页面滚到最上面，防止“导出excel”按钮被隐藏
    pyautogui.scroll(1000)
    time.sleep(0.5)

    # 尝试寻找文字“导出excel”
    clicked_export = click_ocr("导出excel", retry=2)
    
    # 【适配特殊界面】如“财务摘要(报告期)”，它没有文字按钮，只有一个挨着“收起”的 Excel 小图标
    if not clicked_export:
        print("     [提示] 未找到'导出excel'文字，尝试寻找'收起'附近的图标...")
        # 寻找“收起”，往左偏移大约 20 像素，往上偏移大概 15 像素（根据截图相对位置预估）
        clicked_export = click_ocr("收起", retry=2, click_offset=(-15, -25))

    if clicked_export:
        print("     等待 Windows 下载弹窗...")
        time.sleep(2) 

        print("     OCR 寻找地址栏并点击...")
        clicked_addr = click_ocr("搜索", retry=2, click_offset=(-200, 0))
        if not clicked_addr:
            clicked_addr = click_ocr("名称", retry=2, click_offset=(50, -50))

        if clicked_addr:
            time.sleep(0.5)
            pyautogui.hotkey('ctrl', 'a')
            pyautogui.press('backspace')
            pyperclip.copy(save_path_dir)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.5)
            pyautogui.press('enter')
            time.sleep(1)
        else:
            print("     [警告] 未能通过视觉定位到地址栏，路径可能未更改！")

        print("     强制使用 OCR 点击 '保存(S)' 按钮...")
        if click_ocr("保存(S)", retry=3):
            print("     保存完毕。等待 Excel 缓慢启动 (15秒)...")
            time.sleep(15) 
            print("     执行清理：结束 Excel 进程以关闭自动打开的报表...")
            os.system("taskkill /F /IM excel.exe >nul 2>&1")
            time.sleep(1)
            return True
        else:
            if click_ocr_lowest("保存", retry=2):
                print("     保存完毕。等待 Excel 缓慢启动 (15秒)...")
                time.sleep(15)
                print("     执行清理：结束 Excel 进程以关闭自动打开的报表...")
                os.system("taskkill /F /IM excel.exe >nul 2>&1")
                time.sleep(1)
                return True
            print("     [错误] 未能在弹窗中找到保存按钮！")
            return False
    else:
        print("     [致命错误] 未找到界面的 '导出excel' 按钮或对应图标，取消导出该表！")
        return False

def process_company(code):
    search_company(code)

    # --- 三大表 (为方便调试，暂时跳过) ---
    # reports_major = ["资产负债表", "利润表", "现金流量表"]
    # for rep in reports_major:
    #     if enter_f9_and_search_report(rep):
    #         print("     配置时间范围: 近十年")
    #         if click_ocr("近十年", retry=2):
    #             time.sleep(2) 
    #         target_dir = os.path.join(DATA_DIR, "三大表")
    #         file_name = f"{code}_{rep}.xlsx"
    #         do_export_custom(target_dir, file_name)

    # --- 三小表 (为方便调试，暂时跳过) ---
    # reports_minor = ["销售费用明细", "管理费用", "研发支出", "财务摘要(报告期)"]
    # for rep in reports_minor:
    #     if enter_f9_and_search_report(rep):
    #         print("     配置时间范围: 近十年")
    #         if click_ocr("近十年", retry=2):
    #             time.sleep(2) 
    #         target_dir = os.path.join(DATA_DIR, "三小表")
    #         file_name = f"{code}_财务摘要.xlsx" if rep == "财务摘要(报告期)" else f"{code}_{rep}.xlsx"
    #         do_export_windows(target_dir, file_name)

def search_and_export_ar(codes):
    # --- 应收账款周转天数 (EDE) - 批量处理 ---
    print(f"\n=====================================")
    print(f"  -> 准备批量导出: 应收账款周转天数 (功能码: EDE)")
    
    print("     退回主界面状态并唤起键盘精灵...")
    # 完全采用与搜索公司代码一致的逻辑
    screen_w, screen_h = pyautogui.size()
    pyautogui.click(screen_w // 2, screen_h // 2)
    time.sleep(0.5)
    
    # 清空可能存在的焦点锁定
    pyautogui.press('esc')
    time.sleep(0.5)

    # 在键盘精灵盲打输入 EDE
    print("     输入 EDE 并跳转...")
    pyautogui.typewrite("EDE", interval=0.1)
    time.sleep(1)
    pyautogui.press('enter')
    time.sleep(1)
    # 金融终端有时需要按两下回车才能确认键盘精灵的推荐项
    pyautogui.press('enter') 
    time.sleep(5) # 等待 EDE 页面加载

    print("     OCR寻找左侧指标搜索框...")
    # 恢复精确的文字要求
    if click_ocr("输入拼音查找指标", retry=3):
        time.sleep(0.5)
        pyautogui.hotkey('ctrl', 'a')
        pyautogui.press('backspace')
        pyperclip.copy("应收账款周转天数(不含应收票据)")
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(1)
        pyautogui.press('enter')
        time.sleep(2) # 等待参数面板弹出

        print("     处理参数面板: 勾选使用报告期 & 设置近十年")
        # 1. 勾选使用报告期 (默认四个报告期是勾上的)
        click_ocr("使用报告期", retry=2)
        time.sleep(0.5)

        # 2. 修改时间范围为近十年 (当前年份-9)
        # 点击 "时间范围" 右侧大约 60 像素的下拉框位置将其展开
        if click_ocr("时间范围", retry=2, click_offset=(60, 0)):
            time.sleep(1)
            start_year = str(time.localtime().tm_year - 9)
            print(f"     在下拉列表中向下滚动寻找年份: {start_year}")
            
            # 将鼠标向下轻微移动，确保悬停在下拉列表上，以便滚轮生效
            x, y = pyautogui.position()
            pyautogui.moveTo(x, y + 30)
            
            found_year = False
            for _ in range(8): # 最多向下滚动 8 次
                if click_ocr(start_year, retry=1):
                    found_year = True
                    break
                pyautogui.scroll(-300) # 鼠标滚轮向下
                time.sleep(0.5)
                
            if not found_year:
                print(f"     [警告] 滚动未找到年份 {start_year}，尝试回车关闭下拉框...")
                pyautogui.press('enter')

        time.sleep(0.5)

        # 3. 勾选四个报告期
        print("     勾选四个报告期: 一季, 中报, 三季, 年度")
        img = cv2.cvtColor(np.array(pyautogui.screenshot()), cv2.COLOR_RGB2BGR)
        result, _ = ocr_engine(img)
        found_box = None
        if result:
            for box, text, score in reversed(result):
                clean_t = text.strip().replace(" ", "").replace("口", "").replace("□", "")
                if "一季" in clean_t and "中报" in clean_t and "年度" in clean_t:
                    found_box = box
                    print(f"     [OCR] 找到合并行文本: '{text}'")
                    break
        
        if found_box:
            x_start = found_box[0][0]
            x_end = found_box[1][0]
            y_center = (found_box[0][1] + found_box[2][1]) / 2
            segment_width = (x_end - x_start) / 4
            for i in range(4):
                target_x = x_start + (i * segment_width) + (segment_width * 0.2)
                pyautogui.click(target_x, y_center)
                time.sleep(0.3)
        else:
            print("     [警告] 未能通过 OCR 找到组合的报告期复选框行！")

        # 4. 取消勾选保存为默认参数
        print("     取消勾选'保存为默认参数'...")
        click_ocr("保存为默认", retry=2, click_offset=(-20, 0))
        time.sleep(0.5)

        # 5. 点击确定
        print("     点击确定...")
        click_ocr("确定", retry=2)
        time.sleep(4) # 等待数据加载

        # 6. 【核心修复】在左下角的“搜索板块或成份”输入框里循环输入所有公司代码
        print("     定位左下角的'搜索板块或成份'输入框...")
        if click_ocr("搜索板块或成份", retry=3):
            time.sleep(0.5)
            for i, comp_code in enumerate(codes):
                padded_comp_code = str(comp_code).zfill(6)
                print(f"       -> 输入公司代码 ({i+1}/{len(codes)}): {padded_comp_code}")
                # 清除输入框（双重保险：点击+全选删除）
                pyautogui.click()
                pyautogui.hotkey('ctrl', 'a')
                pyautogui.press('backspace')
                
                # 必须输入补齐 6 位的完整代码，防止 Choice 默认联想到其他股票
                pyautogui.typewrite(padded_comp_code, interval=0.05)
                time.sleep(0.5) # 输完后等待0.5秒让联想菜单反应过来
                pyautogui.press('enter')
                time.sleep(1) # 给界面一点时间把这只股票加进右侧数据表
            
            # 所有公司添加完毕后，执行导出
            target_dir = os.path.join(DATA_DIR, "应付账款")
            file_name = f"批量_应收账款周转天数.xlsx"
            
            print("     所有公司添加完毕，准备导出批量数据...")
            clicked_arrow = False
            
            print("     尝试通过 OpenCV 图像识别点击下拉箭头...")
            # 首先确保鼠标移开，防止悬浮框遮挡
            screen_w, screen_h = pyautogui.size()
            pyautogui.moveTo(screen_w // 2, screen_h // 2)
            
            # 自动获取脚本所在目录，确保图片在同一文件夹内即可识别，提高跨电脑复用性
            base_dir = os.path.dirname(os.path.abspath(__file__))
            arrow_img_path = os.path.join(base_dir, "Snipaste_2026-06-16_09-16-43.png")
            
            if os.path.exists(arrow_img_path):
                for _ in range(5):
                    # 使用 OpenCV 原生匹配，置信度设为 0.85
                    center = find_image_cv2(arrow_img_path, threshold=0.85)
                    if center:
                        pyautogui.click(center[0], center[1])
                        clicked_arrow = True
                        print(f"     [OpenCV] 成功找到并点击箭头！坐标: {center}")
                        # 点击后立刻将鼠标移走，防止悬浮框遮挡下方菜单
                        pyautogui.moveTo(screen_w // 2, screen_h // 2)
                        break
                    time.sleep(1)
            else:
                print(f"     [致命错误] 找不到图标图片文件: {arrow_img_path}")
                
            if clicked_arrow:
                time.sleep(2) # 增加等待下拉菜单完全展开的时间
                print("     寻找展开菜单中的'导出'...")
                # 放宽匹配条件，只要菜单里有“导出”字样就去点，避免因为 EXCEL 字体不同导致 OCR 失败
                if click_ocr("导出EXCEL", retry=2) or click_ocr("导出excel", retry=1) or click_ocr("导出", retry=3):
                    time.sleep(2)
                    do_export_custom(target_dir, file_name)
                else:
                    print("     [警告] 下拉菜单已展开，但未找到'导出EXCEL'选项。")
            else:
                print("     [致命错误] 相对定位未能找到右上角的下拉箭头以调出导出菜单！")
        else:
            print("  -> [致命错误] 未能在 EDE 页面找到'搜索板块或成份'输入框，无法添加公司！")

    else:
        print("  -> [跳过] 未能在 EDE 页面找到指标搜索框。")

def main():
    clear_directories()
    
    if not activate_choice():
        return
        
    print("Choice 窗口已激活，2秒后开始全自动取数...")
    time.sleep(2)
    
    try:
        df = pd.read_excel(EXCEL_PATH, header=None)
        codes = df.iloc[0:19, 0].dropna().tolist()
    except Exception as e:
        print(f"读取 Excel 失败: {e}")
        return

    # 循环前置处理每家公司的三大表三小表
    for code in codes:
        process_company(code)

    # 最后在 EDE 页面一次性批量导出所有公司的指标
    search_and_export_ar(codes)

    print("所有流程执行完毕！")

if __name__ == "__main__":
    main()