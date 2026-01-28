# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class ChamCong(models.Model):
    _name = 'cham.cong'
    _description = 'Chấm công nhân viên'
    _order = 'ngay_cham desc'
    _rec_name = 'display_name'

    nhan_vien_id = fields.Many2one('nhan_vien', string='Nhân viên', required=True, ondelete='cascade')
    ngay_cham = fields.Date(string='Ngày chấm', required=True, default=fields.Date.today)
    
    # Buổi sáng
    gio_vao_sang = fields.Float(string='Giờ vào (sáng)', default=8.0, help='Giờ vào làm buổi sáng (VD: 8.0 = 8h00)')
    gio_ra_sang = fields.Float(string='Giờ ra (sáng)', default=12.0, help='Giờ tan làm buổi sáng (VD: 12.0 = 12h00)')
    
    # Buổi chiều
    gio_vao_chieu = fields.Float(string='Giờ vào (chiều)', default=13.0, help='Giờ vào làm buổi chiều (VD: 13.0 = 13h00)')
    gio_ra_chieu = fields.Float(string='Giờ ra (chiều)', default=17.0, help='Giờ tan làm buổi chiều (VD: 17.0 = 17h00)')
    
    # Tổng hợp
    so_gio_lam = fields.Float(string='Số giờ làm', compute='_compute_so_gio_lam', store=True, 
                              help='Tổng số giờ làm việc trong ngày')
    
    # Giữ lại để tương thích
    gio_vao = fields.Float(string='Giờ vào', related='gio_vao_sang', store=True)
    gio_ra = fields.Float(string='Giờ ra', related='gio_ra_chieu', store=True)
    
    loai_cham_cong = fields.Selection([
        ('full', 'Công đủ'),
        ('half', 'Nửa công'),
        ('off', 'Nghỉ'),
        ('phep', 'Nghỉ phép'),
        ('benh', 'Nghỉ ốm')
    ], string='Loại chấm công', default='full', required=True)
    
    so_cong = fields.Float(string='Số công', compute='_compute_so_cong', store=True, 
                           help='Số công trong ngày')
    
    ghi_chu = fields.Text(string='Ghi chú')
    display_name = fields.Char(string='Tên', compute='_compute_display_name', store=True)
    
    _sql_constraints = [
        ('unique_nhan_vien_ngay', 'UNIQUE(nhan_vien_id, ngay_cham)', 
         'Một nhân viên chỉ được chấm công một lần trong một ngày!')
    ]
    
    @api.depends('nhan_vien_id', 'ngay_cham')
    def _compute_display_name(self):
        for record in self:
            if record.nhan_vien_id and record.ngay_cham:
                record.display_name = f"{record.nhan_vien_id.name} - {record.ngay_cham}"
            else:
                record.display_name = "Chấm công mới"
    
    @api.depends('gio_vao_sang', 'gio_ra_sang', 'gio_vao_chieu', 'gio_ra_chieu')
    def _compute_so_gio_lam(self):
        for record in self:
            so_gio_sang = 0.0
            so_gio_chieu = 0.0
            
            # Tính giờ làm buổi sáng
            if record.gio_vao_sang and record.gio_ra_sang and record.gio_ra_sang > record.gio_vao_sang:
                so_gio_sang = record.gio_ra_sang - record.gio_vao_sang
            
            # Tính giờ làm buổi chiều
            if record.gio_vao_chieu and record.gio_ra_chieu and record.gio_ra_chieu > record.gio_vao_chieu:
                so_gio_chieu = record.gio_ra_chieu - record.gio_vao_chieu
            
            record.so_gio_lam = so_gio_sang + so_gio_chieu
            
            # Tự động ghi chú
            record._auto_ghi_chu()
    
    def _auto_ghi_chu(self):
        """Tự động tạo ghi chú dựa trên giờ vào/ra"""
        for record in self:
            ghi_chu_parts = []
            
            # Kiểm tra đi muộn sáng (sau 8h)
            if record.gio_vao_sang and record.gio_vao_sang > 8.0:
                phut_muon = int((record.gio_vao_sang - 8.0) * 60)
                ghi_chu_parts.append(f"Đi muộn buổi sáng {phut_muon} phút")
            
            # Kiểm tra về sớm sáng (trước 12h)
            if record.gio_ra_sang and record.gio_ra_sang < 12.0:
                phut_som = int((12.0 - record.gio_ra_sang) * 60)
                ghi_chu_parts.append(f"Về sớm buổi sáng {phut_som} phút")
            
            # Kiểm tra đi muộn chiều (sau 13h)
            if record.gio_vao_chieu and record.gio_vao_chieu > 13.0:
                phut_muon = int((record.gio_vao_chieu - 13.0) * 60)
                ghi_chu_parts.append(f"Đi muộn buổi chiều {phut_muon} phút")
            
            # Kiểm tra về sớm chiều (trước 17h)
            if record.gio_ra_chieu and record.gio_ra_chieu < 17.0:
                phut_som = int((17.0 - record.gio_ra_chieu) * 60)
                ghi_chu_parts.append(f"Về sớm buổi chiều {phut_som} phút")
            
            # Kiểm tra thiếu giờ
            if record.so_gio_lam < 8.0 and record.loai_cham_cong == 'full':
                gio_thieu = 8.0 - record.so_gio_lam
                ghi_chu_parts.append(f"Thiếu {gio_thieu:.1f} giờ")
            
            # Kiểm tra làm thêm
            if record.so_gio_lam > 8.0:
                gio_tang = record.so_gio_lam - 8.0
                ghi_chu_parts.append(f"Làm thêm {gio_tang:.1f} giờ")
            
            # Cập nhật ghi chú nếu có vi phạm
            if ghi_chu_parts:
                record.ghi_chu = "; ".join(ghi_chu_parts)
            elif not record.ghi_chu or record.ghi_chu.startswith("Đi muộn") or record.ghi_chu.startswith("Về sớm") or "Thiếu" in (record.ghi_chu or "") or "Làm thêm" in (record.ghi_chu or ""):
                # Xóa ghi chú tự động nếu không còn vi phạm
                record.ghi_chu = ""
    
    @api.depends('loai_cham_cong', 'gio_vao', 'gio_ra')
    def _compute_so_cong(self):
        for record in self:
            if record.loai_cham_cong == 'full':
                record.so_cong = 1.0
            elif record.loai_cham_cong == 'half':
                record.so_cong = 0.5
            elif record.loai_cham_cong == 'off':
                record.so_cong = 0.0
            elif record.loai_cham_cong == 'phep':
                record.so_cong = 1.0  # Nghỉ phép vẫn tính công
            elif record.loai_cham_cong == 'benh':
                record.so_cong = 0.8  # Nghỉ ốm tính 80% công
            else:
                record.so_cong = 0.0
    
    @api.constrains('gio_vao_sang', 'gio_ra_sang', 'gio_vao_chieu', 'gio_ra_chieu')
    def _check_gio_lam_viec(self):
        for record in self:
            # Kiểm tra giờ sáng
            if record.gio_vao_sang and record.gio_ra_sang:
                if record.gio_ra_sang < record.gio_vao_sang:
                    raise ValidationError('Giờ ra sáng phải sau giờ vào sáng!')
            
            # Kiểm tra giờ chiều
            if record.gio_vao_chieu and record.gio_ra_chieu:
                if record.gio_ra_chieu < record.gio_vao_chieu:
                    raise ValidationError('Giờ ra chiều phải sau giờ vào chiều!')
            
            # Kiểm tra giá trị hợp lệ (0-24)
            for field_name, field_label in [
                ('gio_vao_sang', 'Giờ vào sáng'),
                ('gio_ra_sang', 'Giờ ra sáng'),
                ('gio_vao_chieu', 'Giờ vào chiều'),
                ('gio_ra_chieu', 'Giờ ra chiều')
            ]:
                value = getattr(record, field_name)
                if value and (value < 0 or value > 24):
                    raise ValidationError(f'{field_label} phải trong khoảng 0-24!')
