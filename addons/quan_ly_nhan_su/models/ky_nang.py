# -*- coding: utf-8 -*-

from odoo import models, fields, api


class KyNang(models.Model):
    """Danh mục kỹ năng/chuyên môn"""
    _name = 'ky.nang'
    _description = 'Kỹ năng'
    _order = 'name'

    name = fields.Char(string='Tên kỹ năng', required=True, help='Ví dụ: Python, Design, Sale...')
    ma_ky_nang = fields.Char(string='Mã kỹ năng')
    loai_ky_nang = fields.Selection([
        ('ky_thuat', 'Kỹ thuật'),
        ('quan_ly', 'Quản lý'),
        ('giao_tiep', 'Giao tiếp'),
        ('ngoai_ngu', 'Ngoại ngữ'),
        ('khac', 'Khác')
    ], string='Loại kỹ năng', default='ky_thuat')
    mo_ta = fields.Text(string='Mô tả')
    active = fields.Boolean(string='Hoạt động', default=True)
    
    _sql_constraints = [
        ('name_unique', 'UNIQUE(name)', 'Tên kỹ năng phải là duy nhất!'),
    ]


class KyNangNhanVien(models.Model):
    """Kỹ năng của từng nhân viên kèm mức độ thành thạo"""
    _name = 'ky.nang.nhan.vien'
    _description = 'Kỹ năng của Nhân viên'
    _order = 'nhan_vien_id, trinh_do desc'

    nhan_vien_id = fields.Many2one('nhan_vien', string='Nhân viên', required=True, ondelete='cascade')
    ky_nang_id = fields.Many2one('ky.nang', string='Kỹ năng', required=True)
    trinh_do = fields.Selection([
        ('moi_hoc', 'Mới học'),
        ('co_ban', 'Cơ bản'),
        ('trung_binh', 'Trung bình'),
        ('kha', 'Khá'),
        ('gioi', 'Giỏi'),
        ('chuyen_gia', 'Chuyên gia')
    ], string='Trình độ', default='co_ban', required=True)
    kinh_nghiem_nam = fields.Integer(string='Số năm kinh nghiệm', help='Số năm làm việc với kỹ năng này')
    chung_chi = fields.Char(string='Chứng chỉ', help='Chứng chỉ liên quan (nếu có)')
    ngay_dat = fields.Date(string='Ngày đạt được')
    ghi_chu = fields.Text(string='Ghi chú')
    
    _sql_constraints = [
        ('nhan_vien_ky_nang_unique', 'UNIQUE(nhan_vien_id, ky_nang_id)', 
         'Nhân viên không thể có cùng một kỹ năng nhiều lần!')
    ]


class LichSuHieuSuat(models.Model):
    """Ghi lại lịch sử hiệu suất làm việc của nhân viên"""
    _name = 'lich.su.hieu.suat'
    _description = 'Lịch sử Hiệu suất'
    _order = 'ngay_ghi_nhan desc'

    nhan_vien_id = fields.Many2one('nhan_vien', string='Nhân viên', required=True, ondelete='cascade')
    ngay_ghi_nhan = fields.Date(string='Ngày ghi nhận', default=fields.Date.today, required=True)
    loai_ghi_nhan = fields.Selection([
        ('dung_han', 'Hoàn thành đúng hạn'),
        ('som_han', 'Hoàn thành sớm hạn'),
        ('tre_han', 'Hoàn thành trễ hạn'),
        ('chat_luong_cao', 'Chất lượng cao'),
        ('can_cai_thien', 'Cần cải thiện')
    ], string='Loại ghi nhận', required=True)
    thoi_gian_du_kien = fields.Float(string='Thời gian dự kiến (giờ)', help='Thời gian ước tính ban đầu')
    thoi_gian_thuc_te = fields.Float(string='Thời gian thực tế (giờ)', help='Thời gian thực tế hoàn thành')
    chenh_lech_phan_tram = fields.Float(string='Chênh lệch (%)', compute='_compute_chenh_lech', store=True)
    cong_viec_lien_quan = fields.Char(string='Công việc liên quan')
    nhan_xet = fields.Text(string='Nhận xét')
    
    @api.depends('thoi_gian_du_kien', 'thoi_gian_thuc_te')
    def _compute_chenh_lech(self):
        for record in self:
            if record.thoi_gian_du_kien and record.thoi_gian_du_kien > 0:
                chenh_lech = ((record.thoi_gian_thuc_te - record.thoi_gian_du_kien) / record.thoi_gian_du_kien) * 100
                record.chenh_lech_phan_tram = chenh_lech
            else:
                record.chenh_lech_phan_tram = 0
