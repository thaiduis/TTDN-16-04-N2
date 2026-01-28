from odoo import models, api


class HrIdOcrService(models.AbstractModel):
    _name = 'hr.id.ocr.service'
    _description = 'Service to perform ID OCR using local or cloud connectors'

    @api.model
    def perform_ocr(self, image_b64, connector_id=False):
        """Perform OCR and return a dict with keys: text, id_number, id_name, confidence"""
        import base64, io, logging, re
        _logger = logging.getLogger(__name__)
        text = ''
        id_number = False
        id_name = False
        confidence = 0.0

        connector = None
        if connector_id:
            connector = self.env['hr.id.ocr.connector'].browse(connector_id)
        else:
            connector = self.env['hr.id.ocr.connector'].get_default_connector()

        def _preprocess_image(b64data):
            """Preprocess image for better OCR results: grayscale, autocontrast, denoise, upscale, optional threshold."""
            try:
                # Try OpenCV-based preprocessing first (better results for deskew / adaptive threshold)
                try:
                    import cv2
                    import numpy as np
                    data = base64.b64decode(b64data)
                    arr = np.frombuffer(data, dtype=np.uint8)
                    bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                    if bgr is None:
                        raise ValueError('cv2 failed to decode image bytes')
                    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
                    # Resize if small
                    h, w = gray.shape[:2]
                    max_dim = max(w, h)
                    if max_dim < 1000:
                        scale = 2
                        gray = cv2.resize(gray, (int(w*scale), int(h*scale)), interpolation=cv2.INTER_LINEAR)
                    # Denoise
                    try:
                        gray = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
                    except Exception:
                        gray = cv2.GaussianBlur(gray, (3,3), 0)
                    # Deskew: estimate angle by minAreaRect of the largest contour of edges
                    try:
                        edges = cv2.Canny(gray, 50, 150)
                        contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
                        if contours:
                            largest = max(contours, key=cv2.contourArea)
                            rect = cv2.minAreaRect(largest)
                            angle = rect[-1]
                            # Convert angle from OpenCV's representation
                            if angle < -45:
                                angle = -(90 + angle)
                            else:
                                angle = -angle
                            if abs(angle) > 0.5:
                                center = (gray.shape[1]//2, gray.shape[0]//2)
                                M = cv2.getRotationMatrix2D(center, angle, 1.0)
                                gray = cv2.warpAffine(gray, M, (gray.shape[1], gray.shape[0]), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
                    except Exception:
                        # ignore deskew failures
                        pass
                    # Adaptive threshold to improve contrast on textured backgrounds
                    try:
                        th = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                                   cv2.THRESH_BINARY, 11, 2)
                        # morphological opening to remove small noise
                        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1,1))
                        th = cv2.morphologyEx(th, cv2.MORPH_OPEN, kernel)
                        final = th
                    except Exception:
                        final = gray
                    # Convert back to PIL Image RGB
                    from PIL import Image as PilImage
                    final_rgb = cv2.cvtColor(final, cv2.COLOR_GRAY2RGB) if len(final.shape) == 2 else cv2.cvtColor(final, cv2.COLOR_BGR2RGB)
                    img = PilImage.fromarray(final_rgb)
                    # Optional debug save
                    try:
                        import os, time
                        if os.environ.get('HR_ID_OCR_DEBUG'):
                            path = f'/tmp/ocr_debug_{int(time.time())}.png'
                            img.save(path)
                            _logger.info('Saved OCR debug image to %s', path)
                    except Exception:
                        pass
                    return img
                except Exception:
                    # OpenCV not available or failed — fallback to Pillow pipeline
                    from PIL import Image, ImageFilter, ImageOps
                    data = base64.b64decode(b64data)
                    img = Image.open(io.BytesIO(data))
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
                    try:
                        img = img.convert('RGB')
                    except Exception:
                        pass
                    return img
            except Exception as e:
                _logger.exception('Image preprocessing failed: %s', e)
                raise

        # Try local OCR first if provider is local
        if connector and connector.provider == 'local':
            try:
                from PIL import Image
                import pytesseract
                # Preprocess the image for better OCR
                img = _preprocess_image(image_b64)
                # Use LSTM engine and a page segmentation mode suitable for ID card text blocks
                custom_config = r'--oem 1 --psm 6'
                try:
                    text = pytesseract.image_to_string(img, lang='vie+eng', config=custom_config)
                except Exception:
                    # fallback without config
                    text = pytesseract.image_to_string(img, lang='vie+eng')
                # sanitize text
                raw_text = text or ''
                sanitized_text = re.sub(r'[^\\x00-\\x7F\\u00C0-\\u017F\\n\\r\\t]', ' ', raw_text)
                sanitized_text = re.sub(r'\\s+', ' ', sanitized_text).strip()
                # extract id number and name heuristically
                match = re.search(r'\\b(\\d{9,12})\\b', re.sub(r'[\\.\\s]', '', sanitized_text))
                if match:
                    id_number = match.group(1)
                lines = [l.strip() for l in (raw_text or '').splitlines() if l.strip()]
                for l in lines:
                    low = l.lower()
                    if 'họ và tên' in low or 'ho va ten' in low or 'name' in low:
                        parts = re.split(r'[:\\-]', l, maxsplit=1)
                        id_name = parts[1].strip() if len(parts) > 1 else parts[0].strip()
                        break
                if not id_name and lines:
                    # fallback: choose the first line that looks like a name (contains letters and spaces)
                    for l in lines:
                        if len(l) > 3 and any(c.isalpha() for c in l):
                            id_name = l
                            break
                # Confidence: use pytesseract image_to_data if available
                try:
                    data = pytesseract.image_to_data(img, lang='vie+eng', config=custom_config, output_type=pytesseract.Output.DICT)
                    confs = []
                    for c in data.get('conf', []):
                        try:
                            # conf may be string or int; skip -1 values
                            ci = int(float(c))
                            if ci >= 0:
                                confs.append(ci)
                        except Exception:
                            continue
                    if confs:
                        confidence = float(sum(confs) / len(confs))
                    else:
                        confidence = 0.0
                except Exception:
                    confidence = 0.0
                return {'text': raw_text, 'id_number': id_number, 'id_name': id_name, 'confidence': confidence}
            except Exception as e:
                _logger.warning('Local OCR failed: %s', e)
                # fallback to cloud if available

        # Cloud or custom connector fallback
        if connector and connector.provider != 'local' and connector.endpoint:
            try:
                import requests, json
                payload = {'image_base64': image_b64}
                headers = {'Authorization': f'Bearer {connector.api_key}'} if connector.api_key else {}
                r = requests.post(connector.endpoint, json=payload, headers=headers, timeout=15)
                if r.status_code == 200:
                    j = r.json()
                    text = j.get('text', j.get('data', ''))
                    id_number = j.get('id_number') or j.get('id')
                    id_name = j.get('id_name') or j.get('name')
                    confidence = float(j.get('confidence', 0.0) or 0.0)
                    return {'text': text, 'id_number': id_number, 'id_name': id_name, 'confidence': confidence}
                else:
                    _logger.warning('Cloud OCR failed status %s', r.status_code)
            except Exception as e:
                _logger.exception('Cloud OCR error: %s', e)

        # Last resort: return empty result
        return {'text': text, 'id_number': id_number, 'id_name': id_name, 'confidence': confidence}

