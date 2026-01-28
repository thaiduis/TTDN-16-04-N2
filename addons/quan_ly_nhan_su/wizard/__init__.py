# -*- coding: utf-8 -*-

from odoo import models, fields, api
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta


class TaoChamCongWizard(models.TransientModel):
    _name = 'tao.cham.cong.wizard'
    _description = 'Wizard tạo chấm công tự động'

    thang = fields.Selection([
        ('1', 'Tháng 1'), ('2', 'Tháng 2'), ('3', 'Tháng 3'),
        ('4', 'Tháng 4'), ('5', 'Tháng 5'), ('6', 'Tháng 6'),
        ('7', 'Tháng 7'), ('8', 'Tháng 8'), ('9', 'Tháng 9'),
        ('10', 'Tháng 10'), ('11', 'Tháng 11'), ('12', 'Tháng 12')
    ], string='Tháng', required=True, default=lambda self: str(datetime.now().month))
    nam = fields.Integer(string='Năm', required=True, default=lambda self: datetime.now().year)
    nhan_vien_ids = fields.Many2many('nhan_vien', string='Nhân viên', required=True)
    loai_cham_cong_mac_dinh = fields.Selection([
        ('full', 'Công đủ'),
        ('half', 'Nửa công'),
        ('off', 'Nghỉ'),
    ], string='Loại chấm công mặc định', default='full', required=True)
    
    def action_tao_cham_cong(self):
        """Tạo chấm công từ ngày 1-26 cho tháng được chọn"""
        ChamCong = self.env['cham.cong']
        
        for nhan_vien in self.nhan_vien_ids:
            # Tạo chấm công từ ngày 1 đến 26
            for ngay in range(1, 27):
                ngay_cham = datetime(self.nam, int(self.thang), ngay).date()
                
                # Kiểm tra đã có chấm công chưa
                existing = ChamCong.search([
                    ('nhan_vien_id', '=', nhan_vien.id),
                    ('ngay_cham', '=', ngay_cham)
                ])
                
                if not existing:
                    # Tạo chấm công mới
                    ChamCong.create({
                        'nhan_vien_id': nhan_vien.id,
                        'ngay_cham': ngay_cham,
                        'loai_cham_cong': self.loai_cham_cong_mac_dinh,
                        'gio_vao': 8.0,
                        'gio_ra': 17.0,
                    })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Thành công',
                'message': f'Đã tạo chấm công cho {len(self.nhan_vien_ids)} nhân viên từ ngày 1-26/{self.thang}/{self.nam}',
                'type': 'success',
                'sticky': False,
            }
        }
