# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class Project(models.Model):
    _inherit = 'project.project'

    # === MILESTONE ===
    milestone_ids = fields.One2many(
        'project.milestone',
        'project_id',
        string='Các Giai đoạn'
    )
    
    milestone_count = fields.Integer(
        string='Số Giai đoạn',
        compute='_compute_milestone_count'
    )
    
    # === OKR ===
    okr_ids = fields.One2many(
        'project.okr',
        'project_id',
        string='OKR (Objective & Key Results)'
    )
    
    okr_count = fields.Integer(
        string='Số OKR',
        compute='_compute_okr_count'
    )
    
    # === BUDGET TRACKING ===
    planned_budget = fields.Monetary(
        string='Ngân sách Dự kiến',
        currency_field='currency_id',
        help='Tổng ngân sách cho dự án'
    )
    
    actual_cost = fields.Monetary(
        string='Chi phí Thực tế',
        currency_field='currency_id',
        compute='_compute_actual_cost',
        store=True,
        help='Tổng chi phí từ Timesheet'
    )
    
    budget_usage_percentage = fields.Float(
        string='% Sử dụng Ngân sách',
        compute='_compute_budget_usage',
        help='(Actual / Planned) * 100'
    )
    
    budget_status = fields.Selection([
        ('safe', 'An toàn (<70%)'),
        ('warning', 'Cảnh báo (70-90%)'),
        ('critical', 'Nguy hiểm (>90%)'),
    ], string='Trạng thái Ngân sách', compute='_compute_budget_status')
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Tiền tệ',
        default=lambda self: self.env.company.currency_id
    )
    
    # === TEAM & RESOURCES ===
    required_team_size = fields.Integer(
        string='Quy mô Team Yêu cầu',
        default=1,
        help='Số lượng nhân viên cần thiết'
    )
    
    current_team_size = fields.Integer(
        string='Quy mô Team Hiện tại',
        compute='_compute_current_team_size'
    )
    
    # === HEALTH METRICS ===
    completion_percentage = fields.Float(
        string='% Hoàn thành',
        compute='_compute_completion_percentage',
        help='Dựa trên Task hoàn thành'
    )
    
    project_health = fields.Selection([
        ('excellent', 'Xuất sắc'),
        ('good', 'Tốt'),
        ('at_risk', 'Có rủi ro'),
        ('critical', 'Nghiêm trọng'),
    ], string='Sức khỏe Dự án', compute='_compute_project_health')

    # ==================
    # COMPUTED FIELDS
    # ==================
    @api.depends('milestone_ids')
    def _compute_milestone_count(self):
        for project in self:
            project.milestone_count = len(project.milestone_ids)
    
    @api.depends('okr_ids')
    def _compute_okr_count(self):
        for project in self:
            project.okr_count = len(project.okr_ids)
    
    @api.depends('user_id', 'partner_id')
    def _compute_current_team_size(self):
        for project in self:
            # Đếm số thành viên từ tasks
            members = project.tasks.mapped('user_ids')
            project.current_team_size = len(set(members.ids))
    
    @api.depends('tasks.actual_hours')
    def _compute_actual_cost(self):
        """Tính chi phí thực tế từ timesheet (giả định $50/h)"""
        for project in self:
            total_hours = sum(project.tasks.mapped('actual_hours'))
            # TODO: Lấy hourly rate từ HR module
            hourly_rate = 50.0
            project.actual_cost = total_hours * hourly_rate
    
    @api.depends('planned_budget', 'actual_cost')
    def _compute_budget_usage(self):
        for project in self:
            if project.planned_budget > 0:
                project.budget_usage_percentage = (project.actual_cost / project.planned_budget) * 100
            else:
                project.budget_usage_percentage = 0.0
    
    @api.depends('budget_usage_percentage')
    def _compute_budget_status(self):
        for project in self:
            usage = project.budget_usage_percentage
            if usage < 70:
                project.budget_status = 'safe'
            elif usage < 90:
                project.budget_status = 'warning'
            else:
                project.budget_status = 'critical'
    
    @api.depends('tasks', 'tasks.stage_id')
    def _compute_completion_percentage(self):
        for project in self:
            total = len(project.tasks)
            if total == 0:
                project.completion_percentage = 0.0
            else:
                done = len(project.tasks.filtered(lambda t: t.stage_id.fold))
                project.completion_percentage = (done / total) * 100
    
    @api.depends('completion_percentage', 'budget_status')
    def _compute_project_health(self):
        for project in self:
            completion = project.completion_percentage
            budget = project.budget_status
            
            if budget == 'critical' or completion < 30:
                project.project_health = 'critical'
            elif budget == 'warning' or completion < 50:
                project.project_health = 'at_risk'
            elif completion >= 80:
                project.project_health = 'excellent'
            else:
                project.project_health = 'good'

    # ==================
    # BUSINESS LOGIC
    # ==================
    def action_view_milestones(self):
        """Mở danh sách Milestone"""
        self.ensure_one()
        return {
            'name': _('Các Giai đoạn - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'project.milestone',
            'view_mode': 'tree,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id}
        }
    
    def action_view_okrs(self):
        """Mở danh sách OKR"""
        self.ensure_one()
        return {
            'name': _('OKR - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'project.okr',
            'view_mode': 'tree,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id}
        }
