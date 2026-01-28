# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime


class BangLuong(models.Model):
    _name = 'bang.luong'
    _description = 'Bảng lương nhân viên'
    _order = 'thang desc, nam desc'
    _rec_name = 'display_name'

    nhan_vien_id = fields.Many2one('nhan_vien', string='Nhân viên', required=True, ondelete='cascade')
    thang = fields.Selection([
        ('1', 'Tháng 1'), ('2', 'Tháng 2'), ('3', 'Tháng 3'),
        ('4', 'Tháng 4'), ('5', 'Tháng 5'), ('6', 'Tháng 6'),
        ('7', 'Tháng 7'), ('8', 'Tháng 8'), ('9', 'Tháng 9'),
        ('10', 'Tháng 10'), ('11', 'Tháng 11'), ('12', 'Tháng 12')
    ], string='Tháng', required=True, default=lambda self: str(datetime.now().month))
    nam = fields.Integer(string='Năm', required=True, default=lambda self: datetime.now().year)
    
    # Thông tin công
    so_cong_chuan = fields.Float(string='Số công chuẩn', default=26.0, 
                                  help='Số công chuẩn trong tháng (thường là 26 ngày)')
    so_cong_thuc_te = fields.Float(string='Số công thực tế', 
                                    help='Tổng số công từ chấm công hoặc nhập thủ công')
    tu_dong_tinh_cong = fields.Boolean(string='Tự động tính công', default=True,
                                        help='Tự động tính từ chấm công, bỏ tick để nhập thủ công')
    
    # Lương cơ bản
    luong_co_ban = fields.Float(string='Lương cơ bản', help='Lương cơ bản từ nhân viên')
    luong_co_ban_1_cong = fields.Float(string='Lương cơ bản/công', compute='_compute_luong_1_cong', 
                                       store=True, help='Lương cơ bản / số công chuẩn')
    
    # Lương theo công
    luong_theo_cong = fields.Float(string='Lương theo công', compute='_compute_luong_theo_cong', 
                                   store=True, help='Số công thực tế * Lương cơ bản/công')
    
    # Thưởng phạt
    tien_thuong = fields.Float(string='Tiền thưởng', default=0.0)
    ly_do_thuong = fields.Text(string='Lý do thưởng')
    tien_phat = fields.Float(string='Tiền phạt', default=0.0)
    ly_do_phat = fields.Text(string='Lý do phạt')
    
    # Phụ cấp
    phu_cap_an_trua = fields.Float(string='Phụ cấp ăn trưa', default=0.0)
    phu_cap_di_lai = fields.Float(string='Phụ cấp đi lại', default=0.0)
    phu_cap_khac = fields.Float(string='Phụ cấp khác', default=0.0)
    
    # Tổng lương
    tong_luong = fields.Float(string='Tổng lương nhận', compute='_compute_tong_luong', 
                              store=True, 
                              help='Lương theo công + Thưởng - Phạt + Phụ cấp')
    
    # Trạng thái
    trang_thai = fields.Selection([
        ('nhap', 'Nháp'),
        ('xac_nhan', 'Đã xác nhận'),
        ('da_tra', 'Đã trả lương')
    ], string='Trạng thái', default='nhap', tracking=True)
    
    ngay_tra_luong = fields.Date(string='Ngày trả lương')
    ghi_chu = fields.Text(string='Ghi chú')
    display_name = fields.Char(string='Tên', compute='_compute_display_name', store=True)
    
    _sql_constraints = [
        ('unique_nhan_vien_thang_nam', 'UNIQUE(nhan_vien_id, thang, nam)', 
         'Một nhân viên chỉ có một bảng lương trong một tháng!')
    ]
    
    @api.depends('nhan_vien_id', 'thang', 'nam')
    def _compute_display_name(self):
        for record in self:
            if record.nhan_vien_id and record.thang and record.nam:
                record.display_name = f"Lương {record.nhan_vien_id.name} - {record.thang}/{record.nam}"
            else:
                record.display_name = "Bảng lương mới"
    
    @api.onchange('nhan_vien_id')
    def _onchange_nhan_vien_id(self):
        """Tự động điền lương cơ bản khi chọn nhân viên"""
        if self.nhan_vien_id:
            self.luong_co_ban = self.nhan_vien_id.luong_co_ban
    
    @api.depends('luong_co_ban', 'so_cong_chuan')
    def _compute_luong_1_cong(self):
        for record in self:
            if record.so_cong_chuan > 0:
                record.luong_co_ban_1_cong = record.luong_co_ban / record.so_cong_chuan
            else:
                record.luong_co_ban_1_cong = 0.0
    
    @api.onchange('nhan_vien_id', 'thang', 'nam', 'tu_dong_tinh_cong')
    def _onchange_tinh_cong(self):
        """Tính lại số công khi thay đổi nhân viên, tháng, năm hoặc chế độ tự động"""
        if self.tu_dong_tinh_cong and self.nhan_vien_id and self.thang and self.nam:
            # Tìm các bản ghi chấm công từ ngày 1-26 của tháng
            ngay_bat_dau = f"{self.nam}-{self.thang.zfill(2)}-01"
            ngay_ket_thuc = f"{self.nam}-{self.thang.zfill(2)}-26"
            
            cham_cong_recs = self.env['cham.cong'].search([
                ('nhan_vien_id', '=', self.nhan_vien_id.id),
                ('ngay_cham', '>=', ngay_bat_dau),
                ('ngay_cham', '<=', ngay_ket_thuc)
            ])
            self.so_cong_thuc_te = sum(cham_cong_recs.mapped('so_cong'))
    
    @api.depends('so_cong_thuc_te', 'luong_co_ban_1_cong')
    def _compute_luong_theo_cong(self):
        for record in self:
            record.luong_theo_cong = record.so_cong_thuc_te * record.luong_co_ban_1_cong
    
    @api.depends('luong_theo_cong', 'tien_thuong', 'tien_phat', 'phu_cap_an_trua', 
                 'phu_cap_di_lai', 'phu_cap_khac')
    def _compute_tong_luong(self):
        for record in self:
            tong_phu_cap = (record.phu_cap_an_trua or 0.0) + (record.phu_cap_di_lai or 0.0) + (record.phu_cap_khac or 0.0)
            luong_theo_cong = record.luong_theo_cong or 0.0
            tien_thuong = record.tien_thuong or 0.0
            tien_phat = record.tien_phat or 0.0
            record.tong_luong = luong_theo_cong + tien_thuong - tien_phat + tong_phu_cap
    
    @api.constrains('tien_phat', 'tien_thuong')
    def _check_tien(self):
        for record in self:
            if record.tien_phat < 0:
                raise ValidationError('Tiền phạt không thể âm!')
            if record.tien_thuong < 0:
                raise ValidationError('Tiền thưởng không thể âm!')
    
    def action_xac_nhan(self):
        """Xác nhận bảng lương"""
        self.write({'trang_thai': 'xac_nhan'})
    
    def action_da_tra(self):
        """Đánh dấu đã trả lương"""
        self.write({
            'trang_thai': 'da_tra',
            'ngay_tra_luong': fields.Date.today()
        })
    
    def action_ve_nhap(self):
        """Đưa về trạng thái nháp"""
        self.write({'trang_thai': 'nhap'})
    
    def action_tinh_lai_cong(self):
        """Tính lại số công từ chấm công (ngày 1-26)"""
        for record in self:
            if record.nhan_vien_id and record.thang and record.nam:
                ngay_bat_dau = f"{record.nam}-{record.thang.zfill(2)}-01"
                ngay_ket_thuc = f"{record.nam}-{record.thang.zfill(2)}-26"
                
                cham_cong_recs = self.env['cham.cong'].search([
                    ('nhan_vien_id', '=', record.nhan_vien_id.id),
                    ('ngay_cham', '>=', ngay_bat_dau),
                    ('ngay_cham', '<=', ngay_ket_thuc)
                ])
                record.so_cong_thuc_te = sum(cham_cong_recs.mapped('so_cong'))
