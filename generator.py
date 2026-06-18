import os
import json

def generate_script(flow_name, actions, output_dir):
    script_path = os.path.join(output_dir, f"{flow_name}_run.py")
    
    code = [
        "import time",
        "import pyautogui",
        "import pyperclip",
        "import sys",
        "import os",
        "import subprocess",
        "import pandas as pd",
        "",
        "# Add ChoiceRPA_Studio root dir to path to import ocr_helper",
        f"sys.path.append(r'{os.path.dirname(os.path.abspath(__file__))}')",
        "from ocr_helper import click_ocr, click_ocr_lowest, click_to_right_of, find_image_and_click, ocr_engine",
        "",
        "pyautogui.FAILSAFE = True",
        "pyautogui.PAUSE = 0.5",
        "context = {}",
        "",
        "def resolve(val):",
        "    if isinstance(val, str) and '${' in val:",
        "        for k, v in context.items():",
        "            val = val.replace(f'${{{k}}}', str(v))",
        "    return val",
        "",
        "def main():",
        f"    print('>>> 开始运行 RPA 流程: {flow_name} <<<')",
        "    print('-' * 40)",
    ]
    
    indent_level = 1
    
    def add_line(line):
        code.append("    " * indent_level + line)

    if not actions:
        add_line("print('没有配置任何动作。')")
        add_line("return")
        
    for idx, action in enumerate(actions):
        action_type = action.get('type')
        
        # End Block reduces indent before processing
        if action_type == 'End Block':
            indent_level = max(1, indent_level - 1)
            add_line(f"# --- End of block ---")
            continue

        step_prefix = f"print('[{idx+1}/{len(actions)}] 正在执行: {action_type}...')"
        add_line(step_prefix)
        
        if action_type == 'Wait':
            seconds = action.get('seconds', 0)
            add_line(f"time.sleep({seconds})")
            add_line(f"print('  -> 等待 {seconds} 秒完成。')")
            
        elif action_type == 'Click XY':
            x = action.get('x', 0)
            y = action.get('y', 0)
            add_line(f"pyautogui.click({x}, {y})")
            add_line(f"print('  -> 已点击坐标 ({x}, {y})')")
            
        elif action_type == 'Type Text':
            text = action.get('text', '')
            add_line(f"val = resolve('{text}')")
            add_line(f"pyperclip.copy(val)")
            add_line(f"pyautogui.hotkey('ctrl', 'v')")
            add_line(f"print(f'  -> 已输入文本: {{val}}')")
            
        elif action_type == 'Press Key':
            key_str = action.get('key', '')
            if '+' in key_str:
                keys = [k.strip() for k in key_str.split('+')]
                args_str = ", ".join([f"'{k}'" for k in keys])
                add_line(f"pyautogui.hotkey({args_str})")
                add_line(f"print('  -> 已按下组合键: {key_str}')")
            else:
                add_line(f"pyautogui.press('{key_str}')")
                add_line(f"print('  -> 已按下按键: {key_str}')")
            
        elif action_type == 'OCR Click (Offset)':
            text = action.get('text', '')
            x_off = action.get('x_off', 0)
            y_off = action.get('y_off', 0)
            add_line(f"success = click_ocr(resolve('{text}'), click_offset=({x_off}, {y_off}))")
            add_line(f"if not success: print('  [!] OCR 未找到文本')")
            
        elif action_type == 'OCR Click Lowest':
            text = action.get('text', '')
            exact = action.get('exact', False)
            x_off = action.get('x_off', 0)
            y_off = action.get('y_off', 0)
            add_line(f"success = click_ocr_lowest(resolve('{text}'), click_offset=({x_off}, {y_off}), exact_match={exact})")
            add_line(f"if not success: print('  [!] OCR 未找到底部文本')")

        elif action_type == 'OCR Click Right':
            text = action.get('text', '')
            mult = action.get('mult', 0.5)
            add_line(f"success = click_to_right_of(resolve('{text}'), width_multiplier={mult})")
            add_line(f"if not success: print('  [!] OCR 未找到锚点文本')")

        elif action_type == 'Image Click (CV2)':
            path = action.get('path', '')
            thresh = action.get('thresh', 0.85)
            path_safe = path.replace('\\', '\\\\')
            add_line(f"success = find_image_and_click(r'{path_safe}', threshold={thresh})")
            add_line(f"if not success: print('  [!] 图片匹配失败')")
            
        elif action_type == 'Open App/File':
            path = action.get('path', '')
            path_safe = path.replace('\\', '\\\\')
            add_line(f"print(f'  -> 正在打开: {path_safe}')")
            add_line(f"try: os.startfile(r'{path_safe}')")
            add_line(f"except Exception as e: print(f'  [!] 打开失败: {{e}}')")

        elif action_type == 'Kill Process':
            pname = action.get('process_name', '')
            add_line(f"print(f'  -> 正在终止进程: {pname}')")
            add_line(f"os.system(f'taskkill /F /IM {pname} >nul 2>&1')")
            
        elif action_type == 'Run Python':
            script_path_action = action.get('script_path', '')
            script_path_safe = script_path_action.replace('\\', '\\\\')
            add_line(f"print('  -> 正在执行外部 Python...')")
            add_line(f"subprocess.run([sys.executable, '-u', r'{script_path_safe}'], check=True)")

        elif action_type == 'Loop (Excel)':
            path = action.get('excel_path', '')
            path_safe = path.replace('\\', '\\\\')
            col_type = action.get('col_type')
            col_val = action.get('col_val')
            var_name = action.get('var_name', 'item')
            
            if "列名" in col_type:
                # 有列名的情况：保持默认 header=0，但强制类型为 str
                add_line(f"df = pd.read_excel(r'{path_safe}', dtype=str)")
                add_line(f"data_list = df['{col_val}'].dropna().tolist()")
            else:
                # 按索引的情况：设置 header=None 防止跳过第一行，强制类型为 str
                idx = int(col_val)
                add_line(f"df = pd.read_excel(r'{path_safe}', header=None, dtype=str)")
                add_line(f"data_list = df.iloc[:, {idx}].dropna().tolist()")
            
            add_line(f"for row_val in data_list:")
            indent_level += 1
            add_line(f"context['{var_name}'] = row_val")
            add_line(f"print(f'  -> [Loop] {var_name} = {{row_val}}')")

        elif action_type == 'If (OCR Text)':
            text = action.get('text', '')
            add_line(f"import cv2; import numpy as np")
            add_line(f"img_tmp = cv2.cvtColor(np.array(pyautogui.screenshot()), cv2.COLOR_RGB2BGR)")
            add_line(f"res_tmp, _ = ocr_engine(img_tmp)")
            add_line(f"found_tmp = any(resolve('{text}') in t for _, t, _ in res_tmp) if res_tmp else False")
            add_line(f"if found_tmp:")
            indent_level += 1
            add_line(f"print('  -> [If] 条件满足，进入块内执行。')")

        add_line("")
        
    code.append("    print('-' * 40)")
    code.append("    print('>>> 流程执行结束 <<<')")
    code.append("")
    code.append("if __name__ == '__main__':")
    code.append("    main()")
    
    with open(script_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(code))
        
    return script_path
