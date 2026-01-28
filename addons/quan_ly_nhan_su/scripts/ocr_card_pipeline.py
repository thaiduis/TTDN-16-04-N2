#!/usr/bin/env python3
"""
ocr_card_pipeline.py
Auto-detect ID card rectangle, warp to top-down view, crop candidate fields,
apply super-resolution (pyrUp) and enhanced preprocessing, then run local OCR
to extract id_number, full_name, gender, dob, nationality, place_of_birth.

Usage:
  python3 ocr_card_pipeline.py /path/to/image.png
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

def load_image(path):
    from PIL import Image
    return Image.open(path)

def detect_card_and_warp(np_img):
    """Detect largest quadrilateral contour and warp to rectangle. Return warped RGB numpy array."""
    import cv2, numpy as np
    h0, w0 = np_img.shape[:2]
    img = np_img.copy()
    ratio = 1.0
    if max(w0, h0) > 1600:
        scale = 1600.0 / max(w0, h0)
        img = cv2.resize(img, (int(w0*scale), int(h0*scale)), interpolation=cv2.INTER_AREA)
        ratio = 1.0/scale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5,5), 0)
    edged = cv2.Canny(blur, 50, 150)
    contours, _ = cv2.findContours(edged, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:10]
    screenCnt = None
    for c in contours:
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        if len(approx) == 4:
            screenCnt = approx
            break
    if screenCnt is None:
        return None  # failed
    pts = screenCnt.reshape(4,2).astype('float32')
    # order points: tl,tr,br,bl
    def order_pts(pts):
        s = pts.sum(axis=1)
        diff = np.diff(pts, axis=1)
        tl = pts[np.argmin(s)]
        br = pts[np.argmax(s)]
        tr = pts[np.argmin(diff)]
        bl = pts[np.argmax(diff)]
        return np.array([tl,tr,br,bl], dtype='float32')
    rect = order_pts(pts)
    (tl,tr,br,bl) = rect
    widthA = ((br[0]-bl[0])**2 + (br[1]-bl[1])**2)**0.5
    widthB = ((tr[0]-tl[0])**2 + (tr[1]-tl[1])**2)**0.5
    maxWidth = max(int(widthA), int(widthB))
    heightA = ((tr[0]-br[0])**2 + (tr[1]-br[1])**2)**0.5
    heightB = ((tl[0]-bl[0])**2 + (tl[1]-bl[1])**2)**0.5
    maxHeight = max(int(heightA), int(heightB))
    dst = np.array([[0,0],[maxWidth-1,0],[maxWidth-1,maxHeight-1],[0,maxHeight-1]], dtype='float32')
    M = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(img, M, (maxWidth, maxHeight))
    # convert to original scale
    if ratio != 1.0:
        warped = cv2.resize(warped, (int(warped.shape[1]*ratio), int(warped.shape[0]*ratio)), interpolation=cv2.INTER_CUBIC)
    return warped

def sr_pyrup(pil_img, times=1):
    """Simple super-resolution via repeated pyrUp."""
    try:
        import cv2, numpy as np
    except Exception:
        return pil_img
    arr = np.array(pil_img.convert('RGB'))
    for _ in range(times):
        arr = cv2.pyrUp(arr)
    from PIL import Image as PilImage
    return PilImage.fromarray(arr)

def preprocess_for_ocr(pil_img):
    """Strong preprocessing: CLAHE, bilateral, adaptive threshold, morphological, unsharp."""
    try:
        import cv2, numpy as np
    except Exception:
        return pil_img
    arr = np.array(pil_img.convert('RGB'))
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    try:
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
        gray = clahe.apply(gray)
    except Exception:
        pass
    try:
        gray = cv2.bilateralFilter(gray, d=9, sigmaColor=75, sigmaSpace=75)
    except Exception:
        gray = cv2.GaussianBlur(gray, (3,3), 0)
    try:
        th = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                   cv2.THRESH_BINARY, 11, 2)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3,3))
        final = cv2.morphologyEx(th, cv2.MORPH_CLOSE, kernel)
    except Exception:
        final = gray
    try:
        gaussian = cv2.GaussianBlur(final, (0,0), 3)
        unsharp = cv2.addWeighted(final, 1.5, gaussian, -0.5, 0)
        final = unsharp
    except Exception:
        pass
    from PIL import Image as PilImage
    final_rgb = cv2.cvtColor(final, cv2.COLOR_GRAY2RGB) if len(final.shape) == 2 else cv2.cvtColor(final, cv2.COLOR_BGR2RGB)
    return PilImage.fromarray(final_rgb)

def ocr_text(pil_img, lang='vie', config='--oem 1 --psm 6'):
    try:
        return pytesseract.image_to_string(pil_img, lang=lang, config=config)
    except Exception:
        return pytesseract.image_to_string(pil_img, config=config)

def image_to_data_conf(pil_img, lang='vie', config='--oem 1 --psm 6'):
    try:
        d = pytesseract.image_to_data(pil_img, lang=lang, config=config, output_type=pytesseract.Output.DICT)
    except Exception:
        d = pytesseract.image_to_data(pil_img, config=config, output_type=pytesseract.Output.DICT)
    # compute mean conf
    raw = d.get('conf', []) or []
    vals = []
    for v in raw:
        try:
            vi = int(v)
        except Exception:
            continue
        if vi >= 0:
            vals.append(vi)
    mean = sum(vals)/len(vals) if vals else None
    return d, mean

def find_best_id_and_name(warped_rgb):
    from PIL import Image as PilImage
    import numpy as np
    pil = PilImage.fromarray(warped_rgb)
    w, h = pil.size
    # generate grid of candidate boxes (relative)
    boxes = []
    rows = 8
    cols = 6
    for r in range(rows):
        for c in range(cols):
            left = int(c * w/cols)
            top = int(r * h/rows)
            right = int((c+1) * w/cols)
            bottom = int((r+1) * h/rows)
            boxes.append((left, top, right, bottom))
    best_id = {'conf': None, 'text': None, 'box': None}
    best_name = {'conf': None, 'text': None, 'box': None}
    for box in boxes:
        crop = pil.crop(box)
        # try numeric OCR with scales
        for s in (1,2,3):
            sr = sr_pyrup(crop, times=s-1) if s>1 else crop
            pre = preprocess_for_ocr(sr)
            d, conf = image_to_data_conf(pre, lang='vie', config='--oem 1 --psm 7 -c tessedit_char_whitelist=0123456789')
            text = ''.join([t for t in d.get('text', []) if isinstance(t, str)]).replace(' ', '').replace('\n','')
            if text and re.search(r'\d{6,12}', text):
                if conf is not None and (best_id['conf'] is None or conf > best_id['conf']):
                    best_id.update({'conf': conf, 'text': text, 'box': box})
        # try name OCR (psm 6)
        pre2 = preprocess_for_ocr(crop)
        d2, conf2 = image_to_data_conf(pre2, lang='vie', config='--oem 1 --psm 6')
        txt2 = ' '.join([t for t in d2.get('text', []) if isinstance(t, str) and t.strip()])
        # heuristic: name has >=2 words and no digits
        words = [w for w in re.split(r'[\s,]+', txt2) if w and not any(ch.isdigit() for ch in w)]
        if len(words) >= 2:
            if conf2 is not None and (best_name['conf'] is None or conf2 > best_name['conf']):
                best_name.update({'conf': conf2, 'text': ' '.join(words), 'box': box})
    return best_id, best_name

def crop_fields_and_ocr(warped_rgb, lang='vie'):
    """Crop template-like regions from warped card and OCR per-field."""
    from PIL import Image as PilImage
    import numpy as np
    import re
    pil = PilImage.fromarray(warped_rgb)
    w, h = pil.size
    # Define relative boxes (left, top, right, bottom) as fractions of width/height.
    # These ratios are heuristic and may need tuning per card template.
    fields = {
        'id_number': (0.55, 0.12, 0.95, 0.22),       # right-top area often contains ID
        'full_name': (0.05, 0.22, 0.75, 0.32),      # name area
        'dob': (0.05, 0.32, 0.45, 0.42),            # dob
        'gender': (0.46, 0.32, 0.65, 0.38),
        'nationality': (0.05, 0.42, 0.5, 0.50),
        'place_of_birth': (0.05, 0.50, 0.9, 0.70),
    }
    out = {}
    for fname, (lx, ty, rx, by) in fields.items():
        left = int(lx * w); top = int(ty * h); right = int(rx * w); bottom = int(by * h)
        crop = pil.crop((left, top, right, bottom))
        # For id_number: try multiple SR scales and whitelist
        if fname == 'id_number':
            cfg = '--oem 1 --psm 7 -c tessedit_char_whitelist=0123456789'
            best = {'conf': None, 'text': None, 'scale': None}
            for s in (1,2,3,4):
                sr = sr_pyrup(crop, times=s-1) if s>1 else crop
                pre = preprocess_for_ocr(sr)
                d, conf = image_to_data_conf(pre, lang=lang, config=cfg)
                text = ''.join([t for t in d.get('text', []) if isinstance(t, str)]).replace(' ', '').replace('\n','')
                # normalize digits
                text = re.sub(r'[^0-9]', '', text)
                if text and len(text) >= 9:
                    if conf is not None and (best['conf'] is None or conf > best['conf']):
                        best.update({'conf': conf, 'text': text, 'scale': s})
            out[fname] = best
        else:
            # name/dob/gender/nationality/place: try SR x1-2 and psm 6
            cfg = '--oem 1 --psm 6'
            best = {'conf': None, 'text': None}
            for s in (1,2,3):
                sr = sr_pyrup(crop, times=s-1) if s>1 else crop
                pre = preprocess_for_ocr(sr)
                d, conf = image_to_data_conf(pre, lang=lang, config=cfg)
                text = ' '.join([t for t in d.get('text', []) if isinstance(t, str) and t.strip()])
                if text and conf is not None and (best['conf'] is None or conf > best['conf']):
                    best.update({'conf': conf, 'text': text})
            # simple post-processing per field
            txt = best.get('text') or ''
            if fname == 'dob' and txt:
                # try extract date
                m = re.search(r'(\d{1,2}[\./\-\s]\d{1,2}[\./\-\s]\d{2,4})', txt)
                if m:
                    txt = m.group(1)
            if fname == 'gender' and txt:
                if re.search(r'\b(nam|male)\b', txt, re.I):
                    txt = 'Nam'
                elif re.search(r'\b(nữ|nu|female)\b', txt, re.I):
                    txt = 'Nữ'
            out[fname] = {'conf': best.get('conf'), 'text': txt}
    return out

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('image', help='Path to image')
    parser.add_argument('--lang', default='vie', help='tesseract language')
    parser.add_argument('--debug', action='store_true')
    args = parser.parse_args()
    if not os.path.exists(args.image):
        print("Image not found:", args.image, file=sys.stderr)
        sys.exit(2)
    # load as numpy BGR
    import numpy as np, cv2
    pil = load_image(args.image)
    npimg = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
    warped = detect_card_and_warp(npimg)
    if warped is None:
        print("Card not detected; trying center crop fallback")
        h,w = npimg.shape[:2]
        ch, cw = int(h*0.6), int(w*0.8)
        top = (h-ch)//2; left = (w-cw)//2
        warped = npimg[top:top+ch, left:left+cw]
    # save debug warped
    if args.debug or os.environ.get('HR_ID_OCR_DEBUG'):
        import time
        p = f'/tmp/ocr_card_warped_{int(time.time())}.png'
        cv2.imwrite(p, warped)
        print("Saved warped card to", p)
    # Try structured field extraction first
    try:
        fields_out = crop_fields_and_ocr(warped, lang=args.lang)
    except Exception:
        fields_out = None
    # Fallback to previous best search
    best_id, best_name = find_best_id_and_name(warped)
    out = {
        'fields': fields_out,
        'id_candidate': best_id,
        'name_candidate': best_name,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    try:
        with open('/tmp/ocr_card_pipeline_out.json','w',encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

if __name__ == '__main__':
    main()

