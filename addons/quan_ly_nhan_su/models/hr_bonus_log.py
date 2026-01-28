# -*- coding: utf-8 -*-

from odoo import models, fields, api


class HRBonusLog(models.Model):
    """Log thưởng từ Project/Milestone"""
    _name = 'hr.bonus.log'
    _description = 'Lịch sử Thưởng'
    _order = 'date desc'

    nhan_vien_id = fields.Many2one(
        'nhan_vien',
        string='Nhân viên',
        required=True
    )
    
    amount = fields.Float(
        string='Số tiền',
        required=True
    )
    
    date = fields.Date(
        string='Ngày',
        default=fields.Date.today,
        required=True
    )
    
    reason = fields.Char(
        string='Lý do',
        required=True
    )
    
    # Source tracking
    milestone_id = fields.Many2one(
        'project.milestone',
        string='Milestone'
    )
    
    project_id = fields.Many2one(
        'project.project',
        string='Dự án',
        related='milestone_id.project_id',
        store=True
    )
    
    okr_id = fields.Many2one(
        'project.okr',
        string='OKR'
    )
    
    # Status
    paid = fields.Boolean(
        string='Đã Thanh toán',
        default=False
    )
    
    payment_date = fields.Date(
        string='Ngày Thanh toán'
    )
