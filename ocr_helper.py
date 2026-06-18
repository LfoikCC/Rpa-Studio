import os
import cv2
import pyautogui
import numpy as np
import time
from rapidocr_onnxruntime import RapidOCR

# Initialize OCR Engine once per script execution
ocr_engine = RapidOCR()

def click_ocr(target_text, click_offset=(0, 0), retry=3):
    """OCR 识别文字并点击，支持偏移量"""
    print(f"[*] OCR 查找 '{target_text}' (Offset: {click_offset})...")
    for _ in range(retry):
        img = cv2.cvtColor(np.array(pyautogui.screenshot()), cv2.COLOR_RGB2BGR)
        result, _ = ocr_engine(img)
        if result:
            for box, text, score in result:
                if target_text in text:
                    cx = (box[0][0] + box[2][0]) / 2 + click_offset[0]
                    cy = (box[0][1] + box[2][1]) / 2 + click_offset[1]
                    print(f"[+] 找到 '{target_text}', 点击 ({cx}, {cy})")
                    pyautogui.click(cx, cy)
                    return True
        time.sleep(1)
    print(f"[-] 未找到: '{target_text}'")
    return False

def click_ocr_lowest(target_text, click_offset=(0, 0), exact_match=False, retry=3):
    """OCR 识别文字并点击屏幕上最下方的那一个匹配项"""
    print(f"[*] OCR 查找(最下方) '{target_text}' (Exact: {exact_match}, Offset: {click_offset})...")
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
                print(f"[+] 找到(最下方) '{target_text_found}', 点击 ({target_cx}, {target_cy})")
                pyautogui.click(target_cx, target_cy)
                return True
        time.sleep(1)
    print(f"[-] 未找到: '{target_text}'")
    return False

def click_to_right_of(target_text, width_multiplier=0.5, retry=3):
    """寻找目标文字，根据该文字自身的宽度，向右按比例偏移点击"""
    print(f"[*] OCR 查找 '{target_text}' 并向右偏移 {width_multiplier} 倍宽度...")
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
                    target_x = x_right + (text_width * width_multiplier)
                    print(f"[+] 找到锚点 '{text}' (宽度:{text_width:.1f}), 点击 ({target_x:.1f}, {y_center:.1f})")
                    pyautogui.click(target_x, y_center)
                    return True
        time.sleep(1)
    print(f"[-] 未找到锚点: '{target_text}'")
    return False

def find_image_and_click(template_path, threshold=0.85):
    """使用 OpenCV 原生模板匹配寻找图片并点击"""
    print(f"[*] OpenCV 匹配图片 '{os.path.basename(template_path)}' (Thresh: {threshold})...")
    img = pyautogui.screenshot()
    img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    
    try:
        template = cv2.imdecode(np.fromfile(template_path, dtype=np.uint8), cv2.IMREAD_COLOR)
    except Exception as e:
        print(f"[-] 图像加载失败: {e}")
        return False
        
    if template is None:
        print(f"[-] 图像为空")
        return False
        
    res = cv2.matchTemplate(img_cv, template, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
    
    if max_val >= threshold:
        h, w = template.shape[:2]
        center_x = max_loc[0] + w // 2
        center_y = max_loc[1] + h // 2
        print(f"[+] 图片匹配成功 (置信度: {max_val:.4f}), 点击 ({center_x}, {center_y})")
        pyautogui.click(center_x, center_y)
        return True
        
    print(f"[-] 图片匹配失败 (最高置信度: {max_val:.4f})")
    return False
