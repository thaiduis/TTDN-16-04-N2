# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class NhanVienIntegration(models.Model):
    """Tích hợp Nhân viên với Project & Task"""
    _inherit = 'nhan_vien'

    # === TASK & PROJECT TRACKING ===
    task_ids = fields.Many2many(
        'project.task',
        string='Công việc Được giao',
        compute='_compute_task_ids',
        help='Danh sách task được giao cho nhân viên này'
    )
    
    task_count = fields.Integer(
        string='Số Công việc',
        compute='_compute_task_count'
    )
    
    project_ids = fields.Many2many(
        'project.project',
        'project_nhan_vien_rel',
        'nhan_vien_id',
        'project_id',
        string='Dự án Tham gia'
    )
    
    project_count = fields.Integer(
        string='Số Dự án',
        compute='_compute_project_count'
    )
    
    # === PERFORMANCE METRICS ===
    total_tasks_completed = fields.Integer(
        string='Tasks Hoàn thành',
        compute='_compute_performance_metrics',
        help='Tổng số task đã hoàn thành'
    )
    
    total_tasks_late = fields.Integer(
        string='Tasks Trễ hạn',
        compute='_compute_performance_metrics'
    )
    
    avg_task_score = fields.Float(
        string='Điểm TB',
        compute='_compute_performance_metrics',
        help='Điểm trung bình từ task.score.card'
    )
    
    total_xp_earned = fields.Integer(
        string='Tổng XP',
        compute='_compute_performance_metrics',
        help='Tổng XP từ các task hoàn thành'
    )
    
    # === SKILL MATCHING ===
    skill_gap_count = fields.Integer(
        string='Kỹ năng Thiếu',
        compute='_compute_skill_gaps',
        help='Số kỹ năng cần học để match với tasks'
    )
    
    # === WORKLOAD ===
    current_workload_hours = fields.Float(
        string='Khối lượng Hiện tại (h)',
        compute='_compute_workload',
        help='Tổng giờ từ tasks đang làm'
    )
    
    overload_warning = fields.Boolean(
        string='Cảnh báo Quá tải',
        compute='_compute_workload'
    )

    def _compute_task_ids(self):
        """Tìm tasks được giao cho nhân viên"""
        for nv in self:
            if 'nhan_vien_assigned_id' in self.env['project.task']._fields:
                tasks = self.env['project.task'].search([
                    ('nhan_vien_assigned_id', '=', nv.id)
                ])
                nv.task_ids = tasks
            else:
                nv.task_ids = self.env['project.task']

    @api.depends('task_ids')
    def _compute_task_count(self):
        for nv in self:
            nv.task_count = len(nv.task_ids)
    
    @api.depends('project_ids')
    def _compute_project_count(self):
        for nv in self:
            nv.project_count = len(nv.project_ids)
    
    def _compute_performance_metrics(self):
        """Tính metrics từ tasks - không dùng depends vì field có thể chưa tồn tại"""
        for nv in self:
            tasks = nv.task_ids
            completed_tasks = tasks.filtered(lambda t: t.stage_id.fold)
            
            nv.total_tasks_completed = len(completed_tasks)
            nv.total_tasks_late = len(tasks.filtered(
                lambda t: t.date_deadline and t.date_deadline < fields.Date.today() and not t.stage_id.fold
            ))
            
            # Điểm trung bình từ score cards
            score_cards = completed_tasks.mapped('score_card_id')
            if score_cards:
                nv.avg_task_score = sum(score_cards.mapped('final_score')) / len(score_cards)
            else:
                nv.avg_task_score = 0.0
            
            # Tổng XP
            nv.total_xp_earned = sum(completed_tasks.mapped('xp_reward'))
    
    def _compute_skill_gaps(self):
        """Tính kỹ năng thiếu - không dùng depends"""
        for nv in self:
            if not nv.task_ids:
                nv.skill_gap_count = 0
                continue
            
            # Kỹ năng yêu cầu từ tasks
            required_skills = nv.task_ids.mapped('required_skill_ids')
            # Kỹ năng nhân viên có
            employee_skills = nv.ky_nang_ids.mapped('ky_nang_id') if hasattr(nv, 'ky_nang_ids') else self.env['hr.skill'].browse()
            
            # Kỹ năng thiếu
            missing_skills = required_skills - employee_skills
            nv.skill_gap_count = len(missing_skills)
    
    def _compute_workload(self):
        """Tính khối lượng công việc hiện tại - không dùng depends"""
        """Tính khối lượng công việc hiện tại"""
        for nv in self:
            # Tasks chưa hoàn thành
            active_tasks = nv.task_ids.filtered(lambda t: not t.stage_id.fold)
            nv.current_workload_hours = sum(active_tasks.mapped('planned_hours'))
            
            # Cảnh báo nếu >160h/tháng (40h/tuần * 4 tuần)
            nv.overload_warning = nv.current_workload_hours > 160
    
    def action_view_tasks(self):
        """Mở danh sách tasks của nhân viên"""
        self.ensure_one()
        return {
            'name': f'Công việc của {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'project.task',
            'view_mode': 'tree,form,kanban',
            'domain': [('nhan_vien_assigned_id', '=', self.id)],
            'context': {'default_nhan_vien_assigned_id': self.id}
        }
    
    def action_view_projects(self):
        """Mở danh sách dự án"""
        self.ensure_one()
        return {
            'name': f'Dự án của {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'project.project',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.project_ids.ids)],
        }


class ChamCongIntegration(models.Model):
    """Tích hợp Chấm công với Task"""
    _inherit = 'cham.cong'

    task_id = fields.Many2one(
        'project.task',
        string='Công việc',
        help='Task liên quan đến giờ làm này'
    )
    
    project_id = fields.Many2one(
        'project.project',
        string='Dự án',
        related='task_id.project_id',
        store=True
    )

    @api.onchange('task_id')
    def _onchange_task_id(self):
        """Tự động điền thông tin từ task"""
        if self.task_id:
            self.mo_ta = f"Làm việc cho task: {self.task_id.name}"


class BangLuongIntegration(models.Model):
    """Tích hợp Bảng lương với Task Performance"""
    _inherit = 'bang.luong'

    # === PERFORMANCE BONUS ===
    task_completion_bonus = fields.Float(
        string='Thưởng Task',
        compute='_compute_task_bonus',
        help='Thưởng dựa trên số task hoàn thành'
    )
    
    quality_bonus = fields.Float(
        string='Thưởng Chất lượng',
        compute='_compute_quality_bonus',
        help='Thưởng dựa trên điểm task trung bình'
    )
    
    project_bonus = fields.Float(
        string='Thưởng Dự án',
        help='Thưởng từ hoàn thành dự án/milestone',
        default=0.0
    )

    @api.depends('nhan_vien_id.total_tasks_completed')
    def _compute_task_bonus(self):
        """Thưởng 100k/task hoàn thành trong tháng"""
        for luong in self:
            if not luong.nhan_vien_id:
                luong.task_completion_bonus = 0
                continue
            
            # Đếm tasks hoàn thành trong tháng này
            tasks = self.env['project.task'].search([
                ('nhan_vien_assigned_id', '=', luong.nhan_vien_id.id),
                ('stage_id.fold', '=', True),
                ('write_date', '>=', f'{luong.thang.year}-{luong.thang.month:02d}-01'),
                ('write_date', '<', fields.Date.today())
            ])
            
            luong.task_completion_bonus = len(tasks) * 100000  # 100k/task
    
    @api.depends('nhan_vien_id.avg_task_score')
    def _compute_quality_bonus(self):
        """Thưởng dựa trên điểm trung bình: >80 = 500k, >90 = 1tr"""
        for luong in self:
            if not luong.nhan_vien_id:
                luong.quality_bonus = 0
                continue
            
            avg_score = luong.nhan_vien_id.avg_task_score
            if avg_score >= 90:
                luong.quality_bonus = 1000000
            elif avg_score >= 80:
                luong.quality_bonus = 500000
            else:
                luong.quality_bonus = 0

    # ==================
    # ACTION METHODS
    # ==================
    def action_view_tasks(self):
        """Xem danh sách tasks của nhân viên"""
        self.ensure_one()
        
        # Tìm res.users tương ứng với nhân viên
        user = self.env['res.users'].search([
            '|',
            ('login', '=', self.email),
            ('name', '=', self.name)
        ], limit=1)
        
        return {
            'name': f'Tasks của {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'project.task',
            'view_mode': 'tree,form,kanban',
            'domain': [('user_ids', 'in', user.ids)] if user else [],
            'context': {'default_user_ids': [(6, 0, user.ids)]} if user else {},
        }
    
    def action_view_projects(self):
        """Xem danh sách dự án"""
        self.ensure_one()
        
        return {
            'name': f'Dự án của {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'project.project',
            'view_mode': 'tree,form,kanban',
            'domain': [('id', 'in', self.project_ids.ids)],
        }
    
    def action_view_performance(self):
        """Xem chi tiết performance"""
        self.ensure_one()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': f'Performance: {self.name}',
                'message': f"""Điểm trung bình: {self.avg_task_score:.1f}
Tasks hoàn thành: {self.total_tasks_completed}
Tasks trễ hạn: {self.total_tasks_late}
Tỷ lệ đúng hạn: {100 - (self.total_tasks_late / max(self.total_tasks_completed, 1) * 100):.0f}%""",
                'type': 'info',
                'sticky': True,
            }
        }
    
    def action_view_xp(self):
        """Xem chi tiết XP"""
        self.ensure_one()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': f'🏆 XP của {self.name}',
                'message': f"""Total XP: {self.total_xp_earned}
Level estimate: {int(self.total_xp_earned / 1000) + 1}
Next level: {((int(self.total_xp_earned / 1000) + 1) * 1000) - self.total_xp_earned} XP""",
                'type': 'success',
                'sticky': True,
            }
        }