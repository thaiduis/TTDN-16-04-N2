# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class ProjectOKR(models.Model):
    _name = 'project.okr'
    _description = 'OKR (Objective & Key Results)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence'

    name = fields.Char(
        string='Objective (Mục tiêu)',
        required=True,
        tracking=True,
        help='Mục tiêu cần đạt được (VD: Tăng doanh số 20%)'
    )
    
    sequence = fields.Integer(
        string='Thứ tự',
        default=10
    )
    
    project_id = fields.Many2one(
        'project.project',
        string='Dự án',
        required=True,
        ondelete='cascade'
    )
    
    description = fields.Html(
        string='Mô tả chi tiết'
    )
    
    # === KEY RESULTS ===
    key_result_ids = fields.One2many(
        'project.okr.key.result',
        'okr_id',
        string='Key Results (Kết quả then chốt)'
    )
    
    kr_count = fields.Integer(
        string='Số Key Result',
        compute='_compute_kr_count'
    )
    
    # === TRACKING ===
    progress = fields.Float(
        string='Tiến độ (%)',
        compute='_compute_progress',
        help='Trung bình tiến độ các Key Result'
    )
    
    deadline = fields.Date(
        string='Hạn chót',
        tracking=True
    )
    
    state = fields.Selection([
        ('active', 'Đang thực hiện'),
        ('achieved', 'Đạt được'),
        ('failed', 'Thất bại'),
    ], string='Trạng thái', default='active', tracking=True)

    @api.depends('key_result_ids')
    def _compute_kr_count(self):
        for okr in self:
            okr.kr_count = len(okr.key_result_ids)
    
    @api.depends('key_result_ids.progress')
    def _compute_progress(self):
        for okr in self:
            if okr.key_result_ids:
                okr.progress = sum(okr.key_result_ids.mapped('progress')) / len(okr.key_result_ids)
            else:
                okr.progress = 0.0


class ProjectOKRKeyResult(models.Model):
    _name = 'project.okr.key.result'
    _description = 'Key Result'
    _order = 'sequence'

    name = fields.Char(
        string='Key Result',
        required=True,
        help='Kết quả đo lường được (VD: Hoàn thành 50 task)'
    )
    
    sequence = fields.Integer(
        string='Thứ tự',
        default=10
    )
    
    okr_id = fields.Many2one(
        'project.okr',
        string='OKR',
        required=True,
        ondelete='cascade'
    )
    
    target_value = fields.Float(
        string='Mục tiêu',
        required=True,
        help='Giá trị cần đạt (VD: 50)'
    )
    
    current_value = fields.Float(
        string='Giá trị Hiện tại',
        default=0.0,
        help='Giá trị đã đạt (VD: 30)'
    )
    
    unit = fields.Char(
        string='Đơn vị',
        default='task',
        help='Đơn vị đo lường (task, %, đơn hàng...)'
    )
    
    progress = fields.Float(
        string='Tiến độ (%)',
        compute='_compute_progress'
    )

    @api.depends('current_value', 'target_value')
    def _compute_progress(self):
        for kr in self:
            if kr.target_value > 0:
                kr.progress = min((kr.current_value / kr.target_value) * 100, 100)
            else:
                kr.progress = 0.0
