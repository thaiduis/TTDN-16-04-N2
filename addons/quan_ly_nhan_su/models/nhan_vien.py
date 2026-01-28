from odoo import models, fields, api


class NhanVien(models.Model):
    _name = 'nhan_vien'
    _description = 'Bảng chứa thông tin nhân viên'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'ma_dinh_danh'

    # Thông tin cơ bản
    ma_dinh_danh = fields.Char("Mã nhân viên", required=True, copy=False, default='/', tracking=True)
    name = fields.Char("Họ và tên", required=True, tracking=True)
    anh_dai_dien = fields.Binary(string='Ảnh đại diện')
    
    # Thông tin cá nhân
    gioi_tinh = fields.Selection([
        ('nam', 'Nam'),
        ('nu', 'Nữ'),
        ('khac', 'Khác')
    ], string='Giới tính', tracking=True)
    ngay_sinh = fields.Date("Ngày sinh", tracking=True)
    noi_sinh = fields.Char("Nơi sinh")
    que_quan = fields.Char("Quê quán")
    dia_chi_hien_tai = fields.Text("Địa chỉ hiện tại")
    
    # Giấy tờ
    cmnd = fields.Char("CMND/CCCD", tracking=True)
    ngay_cap_cmnd = fields.Date("Ngày cấp")
    noi_cap_cmnd = fields.Char("Nơi cấp")
    # Ảnh và dữ liệu CCCD/ID
    id_card_image = fields.Binary(string='Ảnh CCCD/CMND', attachment=True)
    id_card_filename = fields.Char(string='Tên file ảnh')
    id_card_text = fields.Text(string='Nội dung trích xuất từ ảnh')
    id_number = fields.Char(string='Số CCCD/CMND', tracking=True)
    id_name = fields.Char(string='Họ và tên (trích từ CCCD)')
    id_verified = fields.Boolean(string='CCCD đã xác thực', default=False)
    id_confidence = fields.Float(string='Độ chính xác trích xuất', digits=(5,2))
    id_auto_ocr = fields.Boolean(string='Tự động OCR khi upload ảnh', default=True)
    
    # Liên hệ
    email = fields.Char("Email", tracking=True)
    so_dien_thoai = fields.Char("Số điện thoại", tracking=True)
    nguoi_lien_he_khan_cap = fields.Char("Người liên hệ khẩn cấp")
    sdt_lien_he_khan_cap = fields.Char("SĐT khẩn cấp")
    
    # Thông tin công việc
    phong_ban_id = fields.Many2one('phong.ban', string='Phòng ban', tracking=True)
    chuc_vu_id = fields.Many2one('chuc.vu', string='Chức vụ', tracking=True)
    ngay_vao_lam = fields.Date("Ngày vào làm", tracking=True)
    ngay_nghi_viec = fields.Date("Ngày nghỉ việc", tracking=True)
    trang_thai = fields.Selection([
        ('thu_viec', 'Thử việc'),
        ('chinh_thuc', 'Chính thức'),
        ('nghi_viec', 'Nghỉ việc')
    ], string='Trạng thái', default='thu_viec', tracking=True)
    
    # Lương
    luong_co_ban = fields.Float("Lương cơ bản", help="Lương cơ bản theo tháng", tracking=True)
    
    # Học vấn
    trinh_do = fields.Selection([
        ('thpt', 'THPT'),
        ('trung_cap', 'Trung cấp'),
        ('cao_dang', 'Cao đẳng'),
        ('dai_hoc', 'Đại học'),
        ('thac_si', 'Thạc sĩ'),
        ('tien_si', 'Tiến sĩ')
    ], string='Trình độ')
    chuyen_mon = fields.Char("Chuyên môn")
    
    # === NĂNG LỰC & HIỆU SUẤT (Theo Smart HR Design) ===
    # Kỹ năng
    ky_nang_ids = fields.One2many('ky.nang.nhan.vien', 'nhan_vien_id', string='Kỹ năng')
    so_luong_ky_nang = fields.Integer(string='Số kỹ năng', compute='_compute_so_luong_ky_nang')
    
    # Sức chứa công việc (Capacity)
    capacity_per_day = fields.Float(
        string='Năng suất/ngày (giờ)', 
        default=6.0,
        help='Số giờ làm việc hiệu quả tối đa mỗi ngày (VD: 6h làm việc chính, trừ thời gian họp)'
    )
    
    # Tải công việc hiện tại (Workload)
    current_workload = fields.Float(
        string='Tải công việc (%)', 
        compute='_compute_current_workload',
        help='Phần trăm công việc hiện tại so với năng suất tối đa'
    )
    tong_gio_cong_viec = fields.Float(
        string='Tổng giờ công việc đang làm',
        help='Tổng số giờ của các công việc đang thực hiện (sẽ được tính từ module Dự án)'
    )
    
    # Lịch sử hiệu suất
    lich_su_hieu_suat_ids = fields.One2many('lich.su.hieu.suat', 'nhan_vien_id', string='Lịch sử hiệu suất')
    diem_hieu_suat_trung_binh = fields.Float(
        string='Điểm hiệu suất TB',
        compute='_compute_diem_hieu_suat',
        help='Điểm trung bình dựa trên lịch sử làm việc'
    )
    
    # Relations
    cham_cong_ids = fields.One2many('cham.cong', 'nhan_vien_id', string='Chấm công')
    bang_luong_ids = fields.One2many('bang.luong', 'nhan_vien_id', string='Bảng lương')
    
    # Computed
    tuoi = fields.Integer(string='Tuổi', compute='_compute_tuoi')
    so_nam_cong_tac = fields.Integer(string='Số năm công tác', compute='_compute_so_nam_cong_tac')
    
    ghi_chu = fields.Text("Ghi chú")
    active = fields.Boolean(string='Hoạt động', default=True)
    
    _sql_constraints = [
        ('ma_dinh_danh_unique', 'UNIQUE(ma_dinh_danh)', 'Mã nhân viên phải là duy nhất!'),
        ('cmnd_unique', 'UNIQUE(cmnd)', 'Số CMND/CCCD phải là duy nhất!')
    ]
    
    @api.depends('ngay_sinh')
    def _compute_tuoi(self):
        from datetime import date
        today = date.today()
        for record in self:
            if record.ngay_sinh:
                record.tuoi = today.year - record.ngay_sinh.year
            else:
                record.tuoi = 0
    
    @api.depends('ngay_vao_lam')
    def _compute_so_nam_cong_tac(self):
        from datetime import date
        today = date.today()
        for record in self:
            if record.ngay_vao_lam:
                record.so_nam_cong_tac = today.year - record.ngay_vao_lam.year
            else:
                record.so_nam_cong_tac = 0
    
    @api.depends('ky_nang_ids')
    def _compute_so_luong_ky_nang(self):
        """Tính số lượng kỹ năng nhân viên có"""
        for record in self:
            record.so_luong_ky_nang = len(record.ky_nang_ids)
    
    @api.depends('tong_gio_cong_viec', 'capacity_per_day')
    def _compute_current_workload(self):
        """Tính tải công việc hiện tại (%)"""
        for record in self:
            if record.capacity_per_day > 0:
                # Giả sử tính theo tuần (5 ngày làm việc)
                max_capacity_week = record.capacity_per_day * 5
                if max_capacity_week > 0:
                    record.current_workload = (record.tong_gio_cong_viec / max_capacity_week) * 100
                else:
                    record.current_workload = 0
            else:
                record.current_workload = 0
    
    @api.depends('lich_su_hieu_suat_ids.chenh_lech_phan_tram')
    def _compute_diem_hieu_suat(self):
        """Tính điểm hiệu suất trung bình dựa trên lịch sử"""
        for record in self:
            if record.lich_su_hieu_suat_ids:
                # Logic: Nếu làm nhanh hơn dự kiến (chenh_lech âm) = tốt, trễ hạn (dương) = kém
                total_score = 0
                count = 0
                for ls in record.lich_su_hieu_suat_ids:
                    if ls.loai_ghi_nhan == 'som_han':
                        total_score += 100
                    elif ls.loai_ghi_nhan == 'dung_han':
                        total_score += 90
                    elif ls.loai_ghi_nhan == 'chat_luong_cao':
                        total_score += 95
                    elif ls.loai_ghi_nhan == 'tre_han':
                        total_score += 60
                    else:
                        total_score += 70
                    count += 1
                record.diem_hieu_suat_trung_binh = total_score / count if count > 0 else 0
            else:
                record.diem_hieu_suat_trung_binh = 0

    @api.model
    def create(self, vals):
        if vals.get('ma_dinh_danh', '/') == '/':
            vals['ma_dinh_danh'] = self.env['ir.sequence'].next_by_code('nhan_vien.ma_dinh_danh') or '/'
        return super(NhanVien, self).create(vals)
    
    def write(self, vals):
        """Override write để xử lý khi chuyển trạng thái"""
        # Xử lý khi chuyển sang trạng thái nghỉ việc
        if 'trang_thai' in vals and vals['trang_thai'] == 'nghi_viec':
            if not vals.get('ngay_nghi_viec'):
                vals['ngay_nghi_viec'] = fields.Date.today()
        
        # Xử lý khi chuyển từ nghỉ việc sang trạng thái khác
        if 'trang_thai' in vals and vals['trang_thai'] != 'nghi_viec':
            if self.trang_thai == 'nghi_viec':
                vals['ngay_nghi_viec'] = False
        
        return super(NhanVien, self).write(vals)
    
    def action_cap_nhat_ma_nhan_vien(self):
        """Cập nhật mã nhân viên cho các bản ghi có mã là '/'"""
        for record in self:
            if record.ma_dinh_danh == '/':
                record.write({
                    'ma_dinh_danh': self.env['ir.sequence'].next_by_code('nhan_vien.ma_dinh_danh') or '/'
                })

    def action_run_id_ocr(self):
        """Chạy OCR trên ảnh CCCD/CMND đính kèm và trích xuất thông tin cơ bản.
        Cố gắng dùng pytesseract + PIL khi có, nếu không có sẽ ghi log và raise informative error.
        """
        import base64
        import logging
        _logger = logging.getLogger(__name__)

        try:
            from PIL import Image
            import io
            try:
                import pytesseract
            except Exception:
                pytesseract = None
        except Exception:
            Image = None
            pytesseract = None

        for record in self:
            if not record.id_card_image:
                continue
            if Image is None or pytesseract is None:
                _logger.warning('PIL or pytesseract not available for OCR.')
                # Raise a clear, consistent error if local OCR libraries are missing.
                # Avoid calling non-existing ir.model.data methods; simply raise Exception.
                raise Exception('OCR libraries (Pillow, pytesseract) are not installed on the server. Install them or configure a cloud OCR connector.')
            try:
                image_data = base64.b64decode(record.id_card_image)
                img = Image.open(io.BytesIO(image_data))
                # Convert to RGB to avoid some tesseract issues
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                raw_text = pytesseract.image_to_string(img, lang='vie+eng')
                record.id_card_text = raw_text
                # Try to parse ID number (Vietnamese CCCD is 9 or 12 digits)
                import re
                match = re.search(r'\\b(\\d{9,12})\\b', raw_text.replace(' ', '').replace('.', ''))
                if match:
                    record.id_number = match.group(1)
                else:
                    record.id_number = record.cmnd or False
                # Try to extract name heuristically: look for line starting with 'Họ và tên' or 'Name'
                lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
                name_found = False
                for l in lines:
                    low = l.lower()
                    if 'họ và tên' in low or 'ho va ten' in low or 'name' in low:
                        # split on ':' or '-'
                        parts = re.split(r'[:\\-]', l, maxsplit=1)
                        candidate = parts[1].strip() if len(parts) > 1 else parts[0].strip()
                        record.id_name = candidate
                        name_found = True
                        break
                if not name_found and lines:
                    # fallback: take the first long-ish line
                    for l in lines:
                        if len(l) > 3 and any(c.isalpha() for c in l):
                            record.id_name = l
                            break
                # Confidence: use pytesseract image_to_data if available
                try:
                    data = pytesseract.image_to_data(img, lang='vie+eng', output_type=pytesseract.Output.DICT)
                    confs = [int(x) for x in data.get('conf', []) if x.isdigit() or (isinstance(x, (str,)) and x.lstrip('-').isdigit())]
                    if confs:
                        avg = sum(confs) / len(confs)
                        record.id_confidence = float(avg)
                    else:
                        record.id_confidence = 0.0
                except Exception:
                    record.id_confidence = 0.0
                # Basic verification: if extracted name or number matches existing fields
                record.id_verified = bool(record.id_number and (record.id_number == (record.cmnd or record.id_number)))
            except Exception as e:
                _logger.exception('Error during ID OCR: %s', e)
                raise

    def _run_ocr_for_record(self):
        """Helper to run OCR for a single record using default connector."""
        self.ensure_one()
        try:
            if not self.id_card_image:
                return False
            connector = self.env['hr.id.ocr.connector'].get_default_connector()
            service = self.env['hr.id.ocr.service']
            res = service.perform_ocr(self.id_card_image, connector.id if connector else False)
            vals = {
                'id_card_text': res.get('text', '') or '',
                'id_number': res.get('id_number') or False,
                'id_name': res.get('id_name') or False,
                'id_confidence': res.get('confidence', 0.0) or 0.0,
                'id_verified': bool(res.get('id_number') and (res.get('id_number') == (self.cmnd or res.get('id_number')))),
            }
            # write without touching id_card_image to avoid re-trigger
            super(NhanVien, self).write(vals)
            return True
        except Exception:
            # don't break the flow on OCR errors; log only
            import logging
            _logger = logging.getLogger(__name__)
            _logger.exception('Auto OCR failed for employee %s', self.id)
            return False

    @api.model
    def create(self, vals):
        record = super(NhanVien, self).create(vals)
        # If image provided at creation and auto OCR enabled, run OCR
        try:
            if record.id_auto_ocr and record.id_card_image:
                record._run_ocr_for_record()
        except Exception:
            # swallow to avoid blocking create
            import logging
            logging.getLogger(__name__).exception('Error in post-create OCR')
        return record

    def write(self, vals):
        """Override write to auto-run OCR when id_card_image is updated and auto OCR enabled."""
        res = super(NhanVien, self).write(vals)
        try:
            if 'id_card_image' in vals:
                for record in self:
                    # only run if enabled
                    if record.id_auto_ocr and record.id_card_image:
                        record._run_ocr_for_record()
        except Exception:
            import logging
            logging.getLogger(__name__).exception('Error during auto OCR in write')
        return res
