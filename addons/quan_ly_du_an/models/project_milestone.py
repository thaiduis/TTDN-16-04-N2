# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ProjectMilestone(models.Model):
    _name = 'project.milestone'
    _description = 'Giai đoạn Dự án (Milestone)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, deadline'

    name = fields.Char(
        string='Tên Giai đoạn',
        required=True,
        tracking=True
    )
    
    sequence = fields.Integer(
        string='Thứ tự',
        default=10,
        help='Thứ tự hiển thị'
    )
    
    project_id = fields.Many2one(
        'project.project',
        string='Dự án',
        required=True,
        ondelete='cascade'
    )
    
    deadline = fields.Date(
        string='Hạn chót',
        tracking=True
    )
    
    description = fields.Html(
        string='Mô tả'
    )
    
    # === TASKS ===
    task_ids = fields.One2many(
        'project.task',
        'milestone_id',
        string='Công việc'
    )
    
    task_count = fields.Integer(
        string='Số Task',
        compute='_compute_task_count'
    )
    
    # === PROGRESS ===
    completion_percentage = fields.Float(
        string='% Hoàn thành',
        compute='_compute_completion_percentage'
    )
    
    is_completed = fields.Boolean(
        string='Đã hoàn thành',
        default=False,
        tracking=True
    )
    
    # === STATUS ===
    state = fields.Selection([
        ('draft', 'Nháp'),
        ('in_progress', 'Đang thực hiện'),
        ('done', 'Hoàn thành'),
        ('cancelled', 'Hủy'),
    ], string='Trạng thái', default='draft', tracking=True)

    @api.depends('task_ids')
    def _compute_task_count(self):
        for milestone in self:
            milestone.task_count = len(milestone.task_ids)
    
    @api.depends('task_ids', 'task_ids.stage_id')
    def _compute_completion_percentage(self):
        """Tính % hoàn thành dựa trên báo cáo mới nhất của các task"""
        for milestone in self:
            total = len(milestone.task_ids)
            if total == 0:
                milestone.completion_percentage = 0.0
            else:
                # Lấy % hoàn thành từ báo cáo mới nhất của mỗi task
                SmartReport = self.env['task.smart.report']
                total_progress = 0.0
                tasks_with_reports = 0
                
                for task in milestone.task_ids:
                    # Tìm báo cáo mới nhất của task này
                    latest_report = SmartReport.search([
                        ('task_id', '=', task.id)
                    ], order='create_date desc', limit=1)
                    
                    if latest_report:
                        total_progress += latest_report.progress_percentage
                        tasks_with_reports += 1
                    elif task.stage_id.fold:
                        # Nếu task đã done nhưng không có báo cáo → coi như 100%
                        total_progress += 100
                        tasks_with_reports += 1
                
                # Tính trung bình có trọng số
                if tasks_with_reports > 0:
                    milestone.completion_percentage = total_progress / tasks_with_reports
                else:
                    # Fallback: dùng logic cũ (done/total)
                    done = len(milestone.task_ids.filtered(lambda t: t.stage_id.fold))
                    milestone.completion_percentage = (done / total) * 100
    
    def action_start(self):
        """Bắt đầu giai đoạn"""
        self.write({'state': 'in_progress'})
    
    def action_complete(self):
        """Hoàn thành giai đoạn"""
        self.write({
            'state': 'done',
            'is_completed': True
        })
    
    def action_cancel(self):
        """Hủy giai đoạn"""
        self.write({'state': 'cancelled'})
