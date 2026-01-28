# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class ProjectTaskIntegration(models.Model):
    """Tích hợp Task với HR System"""
    _inherit = 'project.task'

    # === HR INTEGRATION ===
    nhan_vien_assigned_id = fields.Many2one(
        'nhan_vien',
        string='Nhân viên Phụ trách',
        tracking=True,
        help='Nhân viên được giao task này'
    )
    
    phong_ban_id = fields.Many2one(
        'phong.ban',
        string='Phòng ban',
        related='nhan_vien_assigned_id.phong_ban_id',
        store=True
    )
    
    # === TIMESHEET FROM CHAM_CONG ===
    cham_cong_ids = fields.Many2many(
        'cham.cong',
        string='Chấm công',
        compute='_compute_cham_cong_ids',
        help='Các bản ghi chấm công liên quan đến task này'
    )
    
    total_attendance_hours = fields.Float(
        string='Tổng giờ Chấm công',
        compute='_compute_attendance_hours',
        help='Tổng giờ từ chấm công'
    )
    
    def _compute_cham_cong_ids(self):
        """Tìm các bản ghi chấm công liên quan"""
        for task in self:
            if 'task_id' in self.env['cham.cong']._fields:
                cham_cong = self.env['cham.cong'].search([('task_id', '=', task.id)])
                task.cham_cong_ids = cham_cong
            else:
                task.cham_cong_ids = self.env['cham.cong']

    # === PROJECT INTEGRATION ===
    # Note: These fields require quan_ly_du_an module
    milestone_id = fields.Many2one(
        'project.milestone',
        string='Milestone',
        help='Cột mốc dự án',
        ondelete='set null'
    )
    
    okr_id = fields.Many2one(
        'project.okr',
        string='OKR',
        help='OKR liên quan',
        ondelete='set null'
    )

    @api.depends('cham_cong_ids.so_gio_lam')
    def _compute_attendance_hours(self):
        """Tính tổng giờ từ chấm công"""
        for task in self:
            try:
                task.total_attendance_hours = sum(task.cham_cong_ids.mapped('so_gio_lam') or [0.0])
            except Exception:
                task.total_attendance_hours = 0.0
    
    @api.onchange('nhan_vien_assigned_id')
    def _onchange_nhan_vien_assigned(self):
        """Kiểm tra skill khi giao task"""
        # Disabled skill checking due to model incompatibility
        # quan_ly_nhan_su uses 'ky.nang' model, not 'hr.skill'
        # TODO: Implement skill checking with ky.nang model if needed
        pass
    
    def action_assign_to_nhan_vien(self):
        """Wizard giao task cho nhân viên"""
        return {
            'name': 'Giao Task cho Nhân viên',
            'type': 'ir.actions.act_window',
            'res_model': 'task.assign.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_task_id': self.id}
        }
    
    @api.model_create_multi
    def create(self, vals_list):
        """Auto sync với project members"""
        tasks = super().create(vals_list)
        
        # Tự động thêm nhân viên vào dự án nếu chưa có
        for task in tasks:
            if task.nhan_vien_assigned_id and task.project_id:
                if task.nhan_vien_assigned_id not in task.project_id.nhan_vien_ids:
                    task.project_id.write({
                        'nhan_vien_ids': [(4, task.nhan_vien_assigned_id.id)]
                    })
        
        return tasks


class TaskSmartReportIntegration(models.Model):
    """Tích hợp Smart Report với HR"""
    _inherit = 'task.smart.report'

    nhan_vien_id = fields.Many2one(
        'nhan_vien',
        string='Nhân viên',
        related='task_id.nhan_vien_assigned_id',
        store=True
    )
    
    # Auto create cham_cong record when report submitted
    @api.model_create_multi
    def create(self, vals_list):
        """Tự động tạo chấm công khi báo cáo"""
        reports = super().create(vals_list)
        
        # Tạo bản ghi chấm công nếu có thời gian làm việc
        for report in reports:
            if report.time_spent > 0 and report.nhan_vien_id:
                self.env['cham.cong'].create({
                    'nhan_vien_id': report.nhan_vien_id.id,
                    'ngay_cham': report.report_date,
                    'gio_vao_sang': 8.0,
                    'gio_ra_chieu': 8.0 + report.time_spent,
                    'task_id': report.task_id.id,
                    'ghi_chu': f'Auto from Smart Report'
                })
        
        return reports


class TaskScoreCardIntegration(models.Model):
    """Tích hợp Score Card với HR Performance"""
    _inherit = 'task.score.card'

    nhan_vien_id = fields.Many2one(
        'nhan_vien',
        string='Nhân viên',
        related='task_id.nhan_vien_assigned_id',
        store=True
    )
    
    # Performance impact
    affect_performance_review = fields.Boolean(
        string='Ảnh hưởng Đánh giá',
        default=True,
        help='Điểm này sẽ tính vào đánh giá cuối kỳ'
    )
