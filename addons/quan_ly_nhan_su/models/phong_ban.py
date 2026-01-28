# -*- coding: utf-8 -*-

from odoo import models, fields, api


class PhongBan(models.Model):
    _name = 'phong.ban'
    _description = 'Phòng ban'
    _order = 'name'

    name = fields.Char(string='Tên phòng ban', required=True)
    ma_phong_ban = fields.Char(string='Mã phòng ban', required=True)
    truong_phong_id = fields.Many2one('nhan_vien', string='Trưởng phòng')
    mo_ta = fields.Text(string='Mô tả')
    nhan_vien_ids = fields.One2many('nhan_vien', 'phong_ban_id', string='Nhân viên')
    so_luong_nhan_vien = fields.Integer(string='Số lượng NV', compute='_compute_so_luong_nv', store=True)
    
    _sql_constraints = [
        ('ma_phong_ban_unique', 'UNIQUE(ma_phong_ban)', 'Mã phòng ban phải là duy nhất!')
    ]
    
    @api.depends('nhan_vien_ids')
    def _compute_so_luong_nv(self):
        for record in self:
            record.so_luong_nhan_vien = len(record.nhan_vien_ids)


class ChucVu(models.Model):
    _name = 'chuc.vu'
    _description = 'Chức vụ'
    _order = 'name'

    name = fields.Char(string='Tên chức vụ', required=True)
    ma_chuc_vu = fields.Char(string='Mã chức vụ', required=True)
    mo_ta = fields.Text(string='Mô tả')
    nhan_vien_ids = fields.One2many('nhan_vien', 'chuc_vu_id', string='Nhân viên')
    
    _sql_constraints = [
        ('ma_chuc_vu_unique', 'UNIQUE(ma_chuc_vu)', 'Mã chức vụ phải là duy nhất!')
    ]
