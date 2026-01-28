#!/usr/bin/env python3
"""
ocr_autoscan.py
Tự thử nhiều cấu hình Tesseract và crop các vùng có mật độ chữ số cao để tìm CCCD.
Usage:
  python3 ocr_autoscan.py /path/to/image.jpg
Options:
  --lang (default: vie)
  --debug (env HR_ID_OCR_DEBUG=1 cũng bật)
"""
from __future__ import print_function
import sys
import os
import io
import argparse
import base64
try:
    from PIL import Image
except Exception:
    print("ERROR: Pillow missing. pip install pillow", file=sys.stderr)
    raise
try:
    import pytesseract
except Exception:
    print("ERROR: pytesseract missing. pip install pytesseract", file=sys.stderr)
    raise

def load_image_bytes(path):
    with open(path, 'rb') as f:
        return f.read()

def preprocess_cv(img_bytes):
    try:
        import cv2, numpy as np
    except Exception:
        return None
    arr = np.frombuffer(img_bytes, dtype=np.uint8)
    bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if bgr is None:
        return None
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape[:2]
    if max(w,h) < 1000:
        gray = cv2.resize(gray, (int(w*2), int(h*2)), interpolation=cv2.INTER_LINEAR)
    try:
        gray = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
    except Exception:
        gray = cv2.GaussianBlur(gray, (3,3), 0)
    # Adaptive threshold
    try:
        th = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                   cv2.THRESH_BINARY, 11, 2)
        final = th
    except Exception:
        final = gray
    from PIL import Image as PilImage
    final_rgb = cv2.cvtColor(final, cv2.COLOR_GRAY2RGB) if len(final.shape) == 2 else cv2.cvtColor(final, cv2.COLOR_BGR2RGB)
    return PilImage.fromarray(final_rgb)

def preprocess_pillow(img_bytes):
    from PIL import ImageOps, ImageFilter
    img = Image.open(io.BytesIO(img_bytes))
    img = img.convert('L')
    try:
        img = ImageOps.autocontrast(img, cutoff=1)
    except Exception:
        pass
    try:
        img = img.filter(ImageFilter.MedianFilter(size=3))
    except Exception:
        pass
    w,h = img.size
    if max(w,h) < 1000:
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
    return img.convert('RGB')

def image_to_data(pil_img, lang='vie', config='--oem 1 --psm 6'):
    try:
        return pytesseract.image_to_data(pil_img, lang=lang, config=config, output_type=pytesseract.Output.DICT)
    except Exception:
        # fallback without lang
        return pytesseract.image_to_data(pil_img, config=config, output_type=pytesseract.Output.DICT)

def mean_conf_from_data(data):
    raw = data.get('conf', []) or []
    vals = []
    for v in raw:
        try:
            vi = int(v)
        except Exception:
            continue
        if vi >= 0:
            vals.append(vi)
    if not vals:
        return None
    return sum(vals) / len(vals)

def group_lines(data):
    # Group boxes by (block_num, par_num, line_num)
    groups = {}
    n = len(data.get('level', []))
    for i in range(n):
        key = (data.get('block_num', [None])[i], data.get('par_num', [None])[i], data.get('line_num', [None])[i])
        left = data.get('left', [0])[i]
        top = data.get('top', [0])[i]
        width = data.get('width', [0])[i]
        height = data.get('height', [0])[i]
        text = data.get('text', [''])[i] or ''
        conf = data.get('conf', ['-1'])[i]
        groups.setdefault(key, []).append({'left': left, 'top': top, 'w': width, 'h': height, 'text': text, 'conf': conf})
    # For each group compute bounding box and concatenated text
    regions = []
    for key, items in groups.items():
        xs = [it['left'] for it in items]
        ys = [it['top'] for it in items]
        ws = [it['w'] for it in items]
        hs = [it['h'] for it in items]
        left = min(xs)
        top = min(ys)
        right = max([x+w for x,w in zip(xs, ws)])
        bottom = max([y+h for y,h in zip(ys, hs)])
        text = ' '.join([it['text'] for it in items if isinstance(it['text'], str)])
        regions.append({'bbox': (left, top, right, bottom), 'text': text})
    return regions

def digit_ratio(s):
    if not s:
        return 0.0
    digits = sum(1 for ch in s if ch.isdigit())
    total = len(s)
    return digits/total if total>0 else 0.0

def crop_pil(pil_img, bbox, pad=4):
    left, top, right, bottom = bbox
    left = max(0, left-pad)
    top = max(0, top-pad)
    right = min(pil_img.width, right+pad)
    bottom = min(pil_img.height, bottom+pad)
    return pil_img.crop((left, top, right, bottom))

def enhance_crop_strong(pil_img, scale_override=None):
    """Apply stronger preprocessing targeted at small crops: upscale, bilateral denoise, CLAHE, unsharp."""
    try:
        import cv2, numpy as np
    except Exception:
        # fallback: return original
        return pil_img
    arr = np.array(pil_img.convert('RGB'))
    # Convert to gray for many ops
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    h, w = gray.shape[:2]
    # upscale small crops or use override
    scale = 1
    if scale_override:
        scale = scale_override
    else:
        if max(w, h) < 800:
            scale = 2
    if scale != 1:
        gray = cv2.resize(gray, (int(w*scale), int(h*scale)), interpolation=cv2.INTER_CUBIC)
    # bilateral filter to remove noise but keep edges
    try:
        gray = cv2.bilateralFilter(gray, d=9, sigmaColor=75, sigmaSpace=75)
    except Exception:
        gray = cv2.GaussianBlur(gray, (3,3), 0)
    # CLAHE
    try:
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
        gray = clahe.apply(gray)
    except Exception:
        pass
    # adaptive threshold (try two variants and pick one by avg intensity)
    try:
        th1 = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                    cv2.THRESH_BINARY, 11, 2)
        th2 = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                                    cv2.THRESH_BINARY, 15, 4)
        # choose the one with stronger contrast (higher std)
        s1 = th1.std()
        s2 = th2.std()
        final = th1 if s1 >= s2 else th2
    except Exception:
        final = gray
    # morphological close to join broken digits
    try:
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3,3))
        final = cv2.morphologyEx(final, cv2.MORPH_CLOSE, kernel)
    except Exception:
        pass
    # unsharp mask (sharpen)
    try:
        gaussian = cv2.GaussianBlur(final, (0,0), 3)
        unsharp = cv2.addWeighted(final, 1.5, gaussian, -0.5, 0)
        final = unsharp
    except Exception:
        pass
    # convert to RGB PIL
    final_rgb = cv2.cvtColor(final, cv2.COLOR_GRAY2RGB) if len(final.shape) == 2 else cv2.cvtColor(final, cv2.COLOR_BGR2RGB)
    from PIL import Image as PilImage
    return PilImage.fromarray(final_rgb)

def try_enhance_scales_and_ocr(crop, lang, cfg_num, scales=(1,2,3,4)):
    """Try multiple upscale factors and return best (text, conf, enhanced_image, scale)."""
    best = {'conf': None, 'text': '', 'enhanced': None, 'scale': None}
    for s in scales:
        try:
            enhanced = enhance_crop_strong(crop, scale_override=s)
            d = image_to_data(enhanced, lang=lang, config=cfg_num)
            conf = mean_conf_from_data(d)
            text = ' '.join([t for t in d.get('text', []) if isinstance(t, str) and t.strip()])
            if conf is not None and (best['conf'] is None or conf > best['conf']):
                best.update({'conf': conf, 'text': text, 'enhanced': enhanced, 'scale': s})
        except Exception:
            continue
    return best

def autoscan(path, lang='vie', debug=False):
    img_bytes = load_image_bytes(path)
    pil_img = preprocess_cv(img_bytes) or preprocess_pillow(img_bytes)
    if debug or os.environ.get('HR_ID_OCR_DEBUG'):
        import time
        debug_path = f'/tmp/ocr_autoscan_pre_{int(time.time())}.png'
        pil_img.save(debug_path)
        print("Saved debug preprocessed image to", debug_path)

    # Try full-image OCR with multiple configs
    configs = [
        ('full_psm6', '--oem 1 --psm 6'),
        ('full_psm11', '--oem 1 --psm 11'),
        ('full_psm3', '--oem 1 --psm 3'),
    ]
    results = []
    for name, cfg in configs:
        data = image_to_data(pil_img, lang=lang, config=cfg)
        conf = mean_conf_from_data(data)
        text = ' '.join([t for t in data.get('text', []) if isinstance(t, str) and t.strip()])
        results.append({'type': name, 'config': cfg, 'conf': conf, 'text': text, 'data': data})

    # From the psm6 result, group lines and find candidate regions with high digit ratio
    base = results[0]
    regions = group_lines(base['data'])
    candidates = []
    for reg in regions:
        dr = digit_ratio(reg['text'])
        if dr >= 0.25 or any(ch.isdigit() for ch in reg['text']):  # candidate if some digits
            crop = crop_pil(pil_img, reg['bbox'])
            # enhance crop strongly and try both original and enhanced
            cfg_num = '--oem 1 --psm 7 -c tessedit_char_whitelist=0123456789'
            # try multiple upscales and pick the best result
            best = try_enhance_scales_and_ocr(crop, lang, cfg_num, scales=(1,2,3,4))
            candidates.append({'bbox': reg['bbox'], 'orig_text': reg['text'], 'digit_ratio': dr, 'num_text': best.get('text'), 'num_conf': best.get('conf'), 'crop': crop, 'enhanced_crop': best.get('enhanced'), 'scale': best.get('scale')})
            if debug or os.environ.get('HR_ID_OCR_DEBUG'):
                try:
                    import time
                    p = f'/tmp/ocr_crop_{int(time.time())}.png'
                    crop.save(p)
                    if best.get('enhanced') is not None:
                        pe = f'/tmp/ocr_crop_enh_{int(time.time())}.png'
                        best['enhanced'].save(pe)
                        print("Saved crop to", p, "and enhanced to", pe, "scale=", best.get('scale'))
                    else:
                        print("Saved crop to", p, "no enhanced result")
                except Exception:
                    pass

    # Also try combinations: full image numeric whitelist
    cfg_full_num = '--oem 1 --psm 3 -c tessedit_char_whitelist=0123456789'
    data_full_num = image_to_data(pil_img, lang=lang, config=cfg_full_num)
    conf_full_num = mean_conf_from_data(data_full_num)
    text_full_num = ' '.join([t for t in data_full_num.get('text', []) if isinstance(t, str) and t.strip()])
    results.append({'type': 'full_num', 'config': cfg_full_num, 'conf': conf_full_num, 'text': text_full_num, 'data': data_full_num})

    # Rank candidates by num_conf then digit_ratio
    candidates_sorted = sorted(candidates, key=lambda x: ((x['num_conf'] or 0), x['digit_ratio']), reverse=True)

    # Print summary
    print("Full-image results (summary):")
    for r in results:
        print(f"- {r['type']}: conf={r['conf']} text_snippet={repr(r['text'][:120])}")
    print("\nFull-image numeric attempt: conf=", conf_full_num, "text_snippet=", repr(text_full_num[:120]))
    print("\nTop candidate crops (num_conf, digit_ratio, text):")
    for c in candidates_sorted[:10]:
        print(c['num_conf'], c['digit_ratio'], repr(c['num_text'][:80]), "orig:", repr(c['orig_text'][:80]))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('image', help='Path to image')
    parser.add_argument('--lang', default='vie', help='Tesseract language')
    parser.add_argument('--debug', action='store_true', help='Save debug crops')
    args = parser.parse_args()
    if not os.path.exists(args.image):
        print("Image not found:", args.image, file=sys.stderr)
        sys.exit(2)
    autoscan(args.image, lang=args.lang, debug=args.debug)

if __name__ == '__main__':
    main()

