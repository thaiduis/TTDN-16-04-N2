#!/usr/bin/env python3
"""
ocr_test.py
Script test OCR để chạy trong container. In kích thước ảnh, vài dòng text đầu,
và ma trận confidence từ pytesseract.image_to_data.

Usage:
  python3 ocr_test.py /path/to/image.jpg --lang vie
  or
  python3 ocr_test.py --base64-file /tmp/img.b64

Môi trường:
  - Nếu đặt env HR_ID_OCR_DEBUG=1 sẽ lưu ảnh tiền xử lý vào /tmp/ocr_debug_*.png
"""
from __future__ import print_function
import sys
import os
import argparse
import base64
import io
try:
    from PIL import Image
except Exception as e:
    print("ERROR: Pillow không được cài. pip install pillow", file=sys.stderr)
    raise
try:
    import pytesseract
except Exception as e:
    print("ERROR: pytesseract không được cài. pip install pytesseract", file=sys.stderr)
    raise

def preprocess_with_opencv(img_bytes):
    """Thử OpenCV preprocessing; trả về PIL Image"""
    try:
        import cv2
        import numpy as np
    except Exception:
        return None
    arr = np.frombuffer(img_bytes, dtype=np.uint8)
    bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if bgr is None:
        return None
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape[:2]
    if max(w, h) < 1000:
        gray = cv2.resize(gray, (int(w*2), int(h*2)), interpolation=cv2.INTER_LINEAR)
    try:
        gray = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
    except Exception:
        gray = cv2.GaussianBlur(gray, (3,3), 0)
    # Deskew attempt
    try:
        edges = cv2.Canny(gray, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            largest = max(contours, key=cv2.contourArea)
            rect = cv2.minAreaRect(largest)
            angle = rect[-1]
            if angle < -45:
                angle = -(90 + angle)
            else:
                angle = -angle
            if abs(angle) > 0.5:
                center = (gray.shape[1]//2, gray.shape[0]//2)
                M = cv2.getRotationMatrix2D(center, angle, 1.0)
                gray = cv2.warpAffine(gray, M, (gray.shape[1], gray.shape[0]), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    except Exception:
        pass
    try:
        th = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                   cv2.THRESH_BINARY, 11, 2)
        final = th
    except Exception:
        final = gray
    # Convert to PIL Image RGB
    from PIL import Image as PilImage
    final_rgb = cv2.cvtColor(final, cv2.COLOR_GRAY2RGB) if len(final.shape) == 2 else cv2.cvtColor(final, cv2.COLOR_BGR2RGB)
    img = PilImage.fromarray(final_rgb)
    return img

def preprocess_with_pillow(img):
    """Fallback preprocessing with Pillow"""
    try:
        from PIL import ImageOps, ImageFilter
        img = img.convert('L')
        try:
            img = ImageOps.autocontrast(img, cutoff=1)
        except Exception:
            pass
        try:
            img = img.filter(ImageFilter.MedianFilter(size=3))
        except Exception:
            pass
        w, h = img.size
        if max(w, h) < 1000:
            img = img.resize((int(w*2), int(h*2)), Image.BILINEAR)
        try:
            import numpy as np
            arr = np.array(img)
            th = arr.mean()
            arr = (arr > th).astype('uint8') * 255
            from PIL import Image as PilImage
            img = PilImage.fromarray(arr)
        except Exception:
            pass
        img = img.convert('RGB')
    except Exception:
        pass
    return img

def run_ocr(pil_img, lang='vie', extra_config='--oem 1 --psm 6'):
    # image_to_data để lấy confidence per word/line
    try:
        data = pytesseract.image_to_data(pil_img, lang=lang, config=extra_config, output_type=pytesseract.Output.DICT)
    except Exception as e:
        # thử không dùng lang nếu gây lỗi
        try:
            data = pytesseract.image_to_data(pil_img, config=extra_config, output_type=pytesseract.Output.DICT)
        except Exception as e2:
            raise
    return data

def summarize_data(data):
    n = len(data.get('text', []))
    texts = [t for t in data.get('text', []) if isinstance(t, str) and t.strip()]
    raw_confs = data.get('conf', []) or []
    confidences = []
    for c in raw_confs:
        try:
            ci = int(c)
        except Exception:
            # skip non-convertible values
            continue
        # Tesseract uses -1 for unknown/confidence not available
        if ci >= 0:
            confidences.append(ci)
    summary = {
        'total_boxes': n,
        'nonempty_texts': len(texts),
        'sample_texts': texts[:10],
        'conf_count': len(confidences),
        'conf_mean': (sum(confidences)/len(confidences)) if confidences else None,
        'conf_min': min(confidences) if confidences else None,
        'conf_max': max(confidences) if confidences else None,
    }
    return summary

def main():
    parser = argparse.ArgumentParser(description='OCR test script')
    parser.add_argument('image', nargs='?', help='Path to image file')
    parser.add_argument('--base64-file', help='Path to file containing base64 image (alternative)')
    parser.add_argument('--lang', default='vie', help='Tesseract language (default: vie)')
    parser.add_argument('--config', default='--oem 1 --psm 6', help='Extra tesseract config')
    args = parser.parse_args()

    img_bytes = None
    if args.image:
        with open(args.image, 'rb') as f:
            img_bytes = f.read()
    elif args.base64_file:
        with open(args.base64_file, 'rb') as f:
            b64 = f.read()
            if isinstance(b64, bytes):
                b64 = b64.decode('utf-8')
            img_bytes = base64.b64decode(b64)
    else:
        print("ERROR: cần cung cấp đường dẫn ảnh hoặc --base64-file", file=sys.stderr)
        sys.exit(2)

    # Try OpenCV preprocessing
    pil_img = None
    pil_img = preprocess_with_opencv(img_bytes)
    if pil_img is None:
        # Fallback to Pillow
        pil_img = Image.open(io.BytesIO(img_bytes))
        pil_img = preprocess_with_pillow(pil_img)

    print("Kích thước ảnh (w,h):", pil_img.size)
    try:
        # Save debug image if requested
        if os.environ.get('HR_ID_OCR_DEBUG'):
            import time
            path = f'/tmp/ocr_debug_{int(time.time())}.png'
            pil_img.save(path)
            print("Saved debug preprocessed image to", path)
    except Exception:
        pass

    print("Chạy pytesseract.image_to_data (lang=%s config=%s)..." % (args.lang, args.config))
    data = run_ocr(pil_img, lang=args.lang, extra_config=args.config)
    summary = summarize_data(data)
    print("Tổng hộp nhận diện:", summary['total_boxes'])
    print("Số ô có text:", summary['nonempty_texts'])
    print("Vài dòng text mẫu:", summary['sample_texts'])
    print("Conf count:", summary['conf_count'], "mean/min/max:", summary['conf_mean'], summary['conf_min'], summary['conf_max'])
    # Print a small table of words+conf (first 30 non-empty)
    print("\nFirst non-empty words with confidence (up to 30):")
    printed = 0
    for t, c in zip(data.get('text', []), data.get('conf', [])):
        if t.strip():
            print(repr(t), c)
            printed += 1
            if printed >= 30:
                break

if __name__ == '__main__':
    main()

