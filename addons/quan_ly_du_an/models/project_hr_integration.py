# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class ProjectIntegration(models.Model):
    """Tích hợp Project với HR"""
    _inherit = 'project.project'

    # === HR TEAM ===
    nhan_vien_ids = fields.Many2many(
        'nhan_vien',
        'project_nhan_vien_rel',
        'project_id',
        'nhan_vien_id',
        string='Thành viên'
    )
    
    phong_ban_id = fields.Many2one(
        'phong.ban',
        string='Phòng ban Chủ trì',
        help='Phòng ban chịu trách nhiệm chính'
    )
    
    # === BUDGET & PAYROLL ===
    labor_budget = fields.Monetary(
        string='Ngân sách Nhân sự',
        currency_field='currency_id',
        help='Ngân sách cho chi phí nhân sự'
    )
    
    actual_labor_cost = fields.Monetary(
        string='Chi phí NS Thực tế',
        currency_field='currency_id',
        compute='_compute_labor_cost',
        help='Tổng lương team trong dự án'
    )
    
    # === PERFORMANCE ===
    avg_team_score = fields.Float(
        string='Điểm TB Team',
        compute='_compute_team_performance',
        help='Điểm trung bình từ task score cards'
    )
    
    team_xp_total = fields.Integer(
        string='Tổng XP Team',
        compute='_compute_team_performance'
    )

    @api.depends('nhan_vien_ids')
    def _compute_labor_cost(self):
        """Tính chi phí nhân sự dựa trên lương team"""
        for project in self:
            if not project.nhan_vien_ids:
                project.actual_labor_cost = 0
                continue
            
            # Tổng lương cơ bản của team
            total_salary = sum(project.nhan_vien_ids.mapped('luong_co_ban'))
            
            # Ước tính theo số tháng dự án
            if project.date_start and project.date:
                months = (project.date - project.date_start).days / 30
                project.actual_labor_cost = total_salary * max(months, 1)
            else:
                project.actual_labor_cost = total_salary
    
    @api.depends('task_ids.score_card_id', 'task_ids.xp_reward')
    def _compute_team_performance(self):
        """Tính performance team"""
        for project in self:
            score_cards = project.task_ids.mapped('score_card_id')
            
            if score_cards:
                project.avg_team_score = sum(score_cards.mapped('final_score')) / len(score_cards)
            else:
                project.avg_team_score = 0.0
            
            # Tổng XP
            completed_tasks = project.task_ids.filtered(lambda t: t.stage_id.fold)
            project.team_xp_total = sum(completed_tasks.mapped('xp_reward'))
    
    def action_view_team_members(self):
        """Xem danh sách nhân viên"""
        self.ensure_one()
        return {
            'name': f'Team - {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'nhan_vien',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.nhan_vien_ids.ids)],
        }
    
    def action_generate_payroll_report(self):
        """Tạo báo cáo lương cho dự án"""
        self.ensure_one()
        # TODO: Implement payroll report generation
        return {
            'type': 'ir.actions.act_window',
            'name': 'Báo cáo Lương Dự án',
            'res_model': 'project.payroll.report',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_project_id': self.id}
        }


class ProjectMilestoneIntegration(models.Model):
    """Tích hợp Milestone với HR Performance"""
    _inherit = 'project.milestone'

    # === BONUS ON COMPLETION ===
    completion_bonus = fields.Float(
        string='Thưởng Hoàn thành',
        help='Thưởng cho team khi hoàn thành milestone đúng hạn'
    )
    
    bonus_distributed = fields.Boolean(
        string='Đã Phân bổ Thưởng',
        default=False
    )
    
    def action_distribute_bonus(self):
        """Phân chia thưởng cho team members"""
        self.ensure_one()
        
        if self.bonus_distributed:
            raise UserError('Thưởng đã được phân bổ!')
        
        if not self.completion_bonus:
            raise UserError('Chưa có số tiền thưởng!')
        
        # Lấy team từ tasks trong milestone
        team_members = self.task_ids.mapped('nhan_vien_assigned_id')
        
        if not team_members:
            raise UserError('Không có nhân viên nào trong milestone!')
        
        # Chia đều thưởng
        bonus_per_member = self.completion_bonus / len(team_members)
        
        # Tạo log thưởng
        for member in team_members:
            self.env['hr.bonus.log'].create({
                'nhan_vien_id': member.id,
                'amount': bonus_per_member,
                'milestone_id': self.id,
                'reason': f'Hoàn thành milestone: {self.name}',
                'date': fields.Date.today()
            })
        
        self.bonus_distributed = True
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Thành công!',
                'message': f'Đã phân bổ {self.completion_bonus:,.0f} VND cho {len(team_members)} nhân viên',
                'type': 'success',
                'sticky': False,
            }
        }


class ProjectOKRIntegration(models.Model):
    """Tích hợp OKR với HR KPI"""
    _inherit = 'project.okr'

    # === ASSIGNED OWNER ===
    owner_id = fields.Many2one(
        'nhan_vien',
        string='Người Chịu trách nhiệm',
        help='Nhân viên chịu trách nhiệm OKR này'
    )
    
    # === KPI INTEGRATION ===
    affects_kpi = fields.Boolean(
        string='Ảnh hưởng KPI',
        default=True,
        help='OKR này tính vào KPI cá nhân'
    )
    
    kpi_weight = fields.Float(
        string='Trọng số KPI (%)',
        default=100.0,
        help='Trọng số trong đánh giá KPI'
    )
    
    @api.constrains('kpi_weight')
    def _check_kpi_weight(self):
        for okr in self:
            if okr.kpi_weight < 0 or okr.kpi_weight > 100:
                raise UserError('Trọng số KPI phải từ 0-100%')
    
    def action_sync_to_kpi(self):
        """Đồng bộ progress vào KPI nhân viên"""
        self.ensure_one()
        
        if not self.owner_id:
            raise UserError('Chưa có người chịu trách nhiệm!')
        
        # TODO: Tạo hoặc update KPI record
        _logger.info(f'Sync OKR {self.name} progress {self.progress}% to KPI of {self.owner_id.name}')
        
        return True
