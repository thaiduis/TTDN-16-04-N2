#!/usr/bin/env python3
"""
ocr_parse_cccd.py
Script thử nghiệm trích xuất các trường trên CCCD:
  - id_number (số CCCD)
  - full_name (Họ và tên)
  - gender (Giới tính)
  - dob (Ngày sinh)
  - nationality (Quốc tịch)
  - place_of_birth (Quê quán / Nơi sinh)

Usage:
  python3 ocr_parse_cccd.py /path/to/image.png

Lưu ý: Chạy trước trên container; không thay đổi code module Odoo.
"""
from __future__ import print_function
import sys, os, io, re, json, argparse
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
    try:
        # CLAHE (adaptive histogram equalization)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
        gray = clahe.apply(gray)
    except Exception:
        pass
    try:
        th = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                   cv2.THRESH_BINARY, 11, 2)
        # morphological closing to fill gaps
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3,3))
        final = cv2.morphologyEx(th, cv2.MORPH_CLOSE, kernel)
    except Exception:
        final = gray
    try:
        # sharpen
        kernel = np.array([[0,-1,0],[-1,5,-1],[0,-1,0]])
        final = cv2.filter2D(final, -1, kernel)
    except Exception:
        pass
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
    groups = {}
    n = len(data.get('level', []))
    for i in range(n):
        key = (data.get('block_num', [None])[i], data.get('par_num', [None])[i], data.get('line_num', [None])[i])
        left = data.get('left', [0])[i]
        top = data.get('top', [0])[i]
        width = data.get('width', [0])[i]
        height = data.get('height', [0])[i]
        text = data.get('text', [''])[i] or ''
        groups.setdefault(key, []).append({'left': left, 'top': top, 'w': width, 'h': height, 'text': text})
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

def digit_regex_candidates(text):
    # find sequences of digits (allow spaces/dashes)
    if not text:
        return []
    # normalize separators
    t = re.sub(r'[\s\-\.,/]+', '', text)
    # common CCCD length 9-12
    ids = re.findall(r'\d{9,12}', t)
    if ids:
        return ids
    # try find sequences with spaces or punctuation, join them
    parts = re.findall(r'[\d\-\s\.]{6,}', text)
    joined = []
    for p in parts:
        s = re.sub(r'[\s\-\.\,\/]+', '', p)
        if len(s) >= 9:
            joined.append(s)
    return joined

def find_label_value(lines, label_patterns):
    for lbl in label_patterns:
        pat = re.compile(r'%s[:\s\-]*([A-Za-z0-9À-ỹ .,\/\-]+)' % lbl, re.IGNORECASE)
        for ln in lines:
            m = pat.search(ln)
            if m:
                return m.group(1).strip()
    return None

def parse_dates_from_text(text):
    # common date formats
    patterns = [
        r'(\d{1,2}[\/\-\.\s]\d{1,2}[\/\-\.\s]\d{2,4})',
        r'(\d{4}[\/\-\.\s]\d{1,2}[\/\-\.\s]\d{1,2})',
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            return m.group(1)
    return None

def normalize_date_string(s):
    # try parsing common variants and normalize to DD/MM/YYYY
    import datetime
    s = s.strip()
    s = s.replace('.', '/').replace('-', '/')
    # remove non-digit except slash
    s = re.sub(r'[^0-9/]', '', s)
    parts = s.split('/')
    try:
        if len(parts) == 3:
            d, m, y = parts
            yd = int(y)
            # fix obvious OCR year errors (e.g., 2805 -> 1985)
            if yd > datetime.datetime.now().year:
                # try last two digits heuristic
                y2 = int(str(yd)[-2:])
                for base in (1900, 2000):
                    cy = base + y2
                    age = datetime.datetime.now().year - cy
                    if 15 <= age <= 120:
                        yd = cy
                        break
            dd = int(d); mm = int(m)
            return f"{dd:02d}/{mm:02d}/{yd:04d}"
    except Exception:
        pass
    return s

def pick_name_from_lines(lines):
    # heuristic: choose line with at least two words, no digits, and >3 chars each
    candidates = []
    for ln in lines:
        if any(ch.isdigit() for ch in ln):
            continue
        parts = [p for p in re.split(r'[\s,]+', ln) if p]
        if len(parts) >= 2 and all(len(p) >= 2 for p in parts):
            candidates.append((ln, len(parts)))
    if not candidates:
        return None
    # pick max words
    candidates.sort(key=lambda x: x[1], reverse=True)
    return candidates[0][0]

def parse_cccd(path, lang='vie', debug=False):
    img_bytes = load_image_bytes(path)
    pil_img = preprocess_cv(img_bytes) or preprocess_pillow(img_bytes)
    if debug or os.environ.get('HR_ID_OCR_DEBUG'):
        import time
        p = f'/tmp/ocr_parse_pre_{int(time.time())}.png'
        pil_img.save(p)
        print("Saved preprocessed image:", p)

    data = image_to_data(pil_img, lang=lang, config='--oem 1 --psm 6')
    full_text = '\n'.join([t for t in data.get('text', []) if isinstance(t, str)])
    lines = [ln.strip() for ln in full_text.split('\n') if ln.strip()]

    result = {
        'id_number': None, 'id_conf': None,
        'full_name': None, 'full_name_conf': None,
        'gender': None, 'gender_conf': None,
        'dob': None, 'dob_conf': None,
        'nationality': None, 'nationality_conf': None,
        'place_of_birth': None, 'place_of_birth_conf': None,
        'raw_text_sample': lines[:30],
    }

    # ID number: search full text regex then per-region numeric OCR
    ids = digit_regex_candidates(full_text)
    if ids:
        result['id_number'] = ids[0]
        result['id_conf'] = mean_conf_from_data(data)
    # if not found, per-region numeric attempt
    if not result['id_number']:
        regions = group_lines(data)
        best = None
        for reg in regions:
            # quick check for digits in raw text
            if any(ch.isdigit() for ch in reg['text']):
                crop = pil_img.crop(reg['bbox'])
                cfg = '--oem 1 --psm 7 -c tessedit_char_whitelist=0123456789'
                dnum = image_to_data(crop, lang=lang, config=cfg)
                txt = ' '.join([t for t in dnum.get('text', []) if isinstance(t, str) and t.strip()])
                ids2 = digit_regex_candidates(txt)
                conf2 = mean_conf_from_data(dnum)
                if ids2 and conf2 and (not best or conf2 > best['conf']):
                    best = {'id': ids2[0], 'conf': conf2, 'text': txt}
        if best:
            result['id_number'] = best['id']
            result['id_conf'] = best['conf']

    # Gender
    gender = find_label_value(lines, ['Giới tính', 'Gioi tinh', 'Sex', 'GT'])
    if gender:
        g = gender.lower()
        if 'nam' in g:
            result['gender'] = 'Nam'
        elif 'nữ' in g or 'nu' in g:
            result['gender'] = 'Nữ'
        else:
            result['gender'] = gender
        result['gender_conf'] = mean_conf_from_data(data)
    else:
        # fallback search for standalone words
        for ln in lines:
            if re.search(r'\b(Nam|NỮ|Nữ|Nu|Male|Female)\b', ln, re.IGNORECASE):
                m = re.search(r'\b(Nam|NỮ|Nữ|Nu|Male|Female)\b', ln, re.IGNORECASE)
                result['gender'] = m.group(1)
                result['gender_conf'] = mean_conf_from_data(data)
                break

    # DOB
    dob = find_label_value(lines, ['Ngày sinh', 'Ngay sinh', 'Date of birth', 'DOB'])
    if dob:
        d = parse_dates_from_text(dob) or dob
        dnorm = normalize_date_string(d)
        result['dob'] = dnorm
        result['dob_conf'] = mean_conf_from_data(data)
    else:
        # try to extract date from lines
        for ln in lines:
            d = parse_dates_from_text(ln)
            if d:
                result['dob'] = normalize_date_string(d)
                result['dob_conf'] = mean_conf_from_data(data)
                break

    # Nationality
    nat = find_label_value(lines, ['Quốc tịch', 'Quoc tich', 'Nationality'])
    if nat:
        result['nationality'] = nat
        result['nationality_conf'] = mean_conf_from_data(data)
    else:
        # look for VIET NAM etc
        for ln in lines:
            if re.search(r'Việ?t|Viet|Việt Nam|VIỆT NAM|Vietnam', ln, re.IGNORECASE):
                result['nationality'] = 'Việt Nam'
                result['nationality_conf'] = mean_conf_from_data(data)
                break

    # Place of birth / Quê quán / Nơi sinh
    pob = find_label_value(lines, ['Quê quán', 'Que quan', 'Nơi sinh', 'Noi sinh', 'Place of birth'])
    if pob:
        result['place_of_birth'] = pob
        result['place_of_birth_conf'] = mean_conf_from_data(data)
    else:
        # try heuristics: long line with letters and commas
        candidate = pick_name_from_lines(lines)
        if candidate:
            # if name already present, skip; otherwise candidate might be place or name
            if result['full_name'] is None:
                result['full_name'] = candidate
                result['full_name_conf'] = mean_conf_from_data(data)

    # Full name: look for label
    name = find_label_value(lines, ['Họ và tên', 'Ho va ten', 'Họ tên', 'Ho ten', 'Full name', 'Name'])
    if name:
        # clean name: remove stray punctuation and multiple spaces
        nm = re.sub(r'[^A-Za-zÀ-ỹ\s]', ' ', name).strip()
        nm = re.sub(r'\s+', ' ', nm)
        result['full_name'] = nm.title()
        result['full_name_conf'] = mean_conf_from_data(data)
    else:
        # try pick from lines
        if not result['full_name']:
            nm = pick_name_from_lines(lines)
            if nm:
                nm2 = re.sub(r'[^A-Za-zÀ-ỹ\s]', ' ', nm).strip()
                nm2 = re.sub(r'\s+', ' ', nm2)
                result['full_name'] = nm2.title()
                result['full_name_conf'] = mean_conf_from_data(data)

    return result

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('image', help='Path to image')
    parser.add_argument('--lang', default='vie', help='tesseract language')
    parser.add_argument('--debug', action='store_true')
    args = parser.parse_args()
    if not os.path.exists(args.image):
        print("Image not found:", args.image, file=sys.stderr)
        sys.exit(2)
    out = parse_cccd(args.image, lang=args.lang, debug=args.debug)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    # save to /tmp for inspection
    try:
        with open('/tmp/ocr_parsed_cccd.json', 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

if __name__ == '__main__':
    main()

