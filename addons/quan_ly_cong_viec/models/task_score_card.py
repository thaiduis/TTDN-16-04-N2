# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class TaskScoreCard(models.Model):
    _name = 'task.score.card'
    _description = 'Phiếu Điểm Task'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    # === RELATION ===
    task_id = fields.Many2one(
        'project.task',
        string='Công việc',
        required=True,
        ondelete='cascade'
    )
    
    user_id = fields.Many2one(
        'res.users',
        string='Nhân viên',
        compute='_compute_user_id',
        store=True,
        help='Người được assign task (người đầu tiên nếu có nhiều)'
    )
    
    project_id = fields.Many2one(
        related='task_id.project_id',
        string='Dự án',
        store=True
    )
    
    task_stage_id = fields.Many2one(
        'project.task.type',
        string='Giai đoạn Task',
        compute='_compute_task_stage',
        inverse='_inverse_task_stage',
        store=False,
        help='Giai đoạn của task - có thể chỉnh sửa trực tiếp'
    )
    
    # === SCORING ===
    timeliness_score = fields.Integer(
        string='Điểm Đúng hạn',
        default=0,
        help='Điểm chấm dựa trên deadline (0-100)'
    )
    
    efficiency_score = fields.Integer(
        string='Điểm Hiệu suất',
        default=0,
        help='So sánh thời gian ước lượng vs thực tế (0-100)'
    )
    
    quality_score = fields.Integer(
        string='Điểm Chất lượng',
        default=0,
        help='Dựa trên số lần re-open, bug report (0-100)'
    )
    
    final_score = fields.Float(
        string='Điểm Tổng kết',
        compute='_compute_final_score',
        store=True,
        help='Weighted average của 3 điểm trên'
    )
    
    grade = fields.Selection([
        ('S', 'S - Xuất sắc (>95)'),
        ('A', 'A - Tốt (85-95)'),
        ('B', 'B - Khá (70-85)'),
        ('C', 'C - Trung bình (60-70)'),
        ('D', 'D - Yếu (<60)'),
    ], string='Xếp loại', compute='_compute_grade', store=True)
    
    # === AI FEEDBACK ===
    ai_feedback = fields.Text(
        string='Nhận xét AI',
        help='Lời khuyên cải thiện cho lần sau'
    )
    
    # === METADATA ===
    create_date = fields.Datetime(
        string='Ngày chấm điểm',
        readonly=True
    )

    # ==================
    # COMPUTED FIELDS
    # ==================
    @api.depends('task_id.stage_id')
    def _compute_task_stage(self):
        """Lấy stage từ task"""
        for record in self:
            record.task_stage_id = record.task_id.stage_id if record.task_id else False
    
    def _inverse_task_stage(self):
        """Cập nhật stage cho task"""
        for record in self:
            if record.task_id and record.task_stage_id:
                record.task_id.stage_id = record.task_stage_id
    
    @api.depends('task_id.user_ids')
    def _compute_user_id(self):
        """Lấy người được assign đầu tiên trong danh sách"""
        for record in self:
            if record.task_id and record.task_id.user_ids:
                record.user_id = record.task_id.user_ids[0]
            else:
                record.user_id = False
    
    @api.depends('timeliness_score', 'efficiency_score', 'quality_score')
    def _compute_final_score(self):
        for record in self:
            # Weighted average: 40% Timeliness, 30% Efficiency, 30% Quality
            record.final_score = (
                record.timeliness_score * 0.4 +
                record.efficiency_score * 0.3 +
                record.quality_score * 0.3
            )

    @api.depends('final_score')
    def _compute_grade(self):
        for record in self:
            if record.final_score >= 95:
                record.grade = 'S'
            elif record.final_score >= 85:
                record.grade = 'A'
            elif record.final_score >= 70:
                record.grade = 'B'
            elif record.final_score >= 60:
                record.grade = 'C'
            else:
                record.grade = 'D'

    # ==================
    # BUSINESS LOGIC
    # ==================
    @api.model
    def create(self, vals):
        """Override: Post notification when score is created"""
        score_card = super(TaskScoreCard, self).create(vals)
        score_card._post_score_to_chatter()
        score_card._reward_xp_to_employee()
        return score_card

    def _post_score_to_chatter(self):
        """Đăng điểm lên Chatter"""
        self.ensure_one()
        
        # Choose color based on grade
        color_map = {
            'S': '#FFD700',  # Gold
            'A': '#4CAF50',  # Green
            'B': '#2196F3',  # Blue
            'C': '#FF9800',  # Orange
            'D': '#F44336',  # Red
        }
        
        color = color_map.get(self.grade, '#999')
        
        message = f'''
            <div style="background:{color}; color:white; padding:15px; border-radius:8px; text-align:center;">
                <h2 style="margin:0;">🏆 Xếp loại: {self.grade}</h2>
                <h3 style="margin:10px 0;">Điểm: {self.final_score:.1f}/100</h3>
                <div style="background:rgba(255,255,255,0.2); padding:10px; border-radius:5px; margin-top:10px;">
                    <p style="margin:5px;">⏰ Đúng hạn: {self.timeliness_score}/100</p>
                    <p style="margin:5px;">⚡ Hiệu suất: {self.efficiency_score}/100</p>
                    <p style="margin:5px;">✨ Chất lượng: {self.quality_score}/100</p>
                </div>
                <p style="margin-top:15px; font-style:italic;">"{self.ai_feedback}"</p>
            </div>
        '''
        
        self.task_id.message_post(
            body=message,
            message_type='notification',
            subtype_xmlid='mail.mt_note',
        )

    def _reward_xp_to_employee(self):
        """Cộng XP cho nhân viên dựa trên điểm task (HR Integration với quan_ly_nhan_su)"""
        self.ensure_one()
        
        if not self.user_id:
            return
        
        # Check if quan_ly_nhan_su module is installed
        if 'nhan_vien' not in self.env:
            _logger.info('Module quan_ly_nhan_su not installed, skipping XP reward')
            return
        
        # Tìm nhan_vien từ quan_ly_nhan_su
        nhan_vien = self.env['nhan_vien'].search([
            '|',
            ('email', '=', self.user_id.login),
            ('name', '=', self.user_id.name)
        ], limit=1)
        
        if not nhan_vien:
            _logger.warning(f'Không tìm thấy nhân viên cho user {self.user_id.name}')
            return
        
        # Tính XP dựa trên grade
        xp_rewards = {
            'S': 100,
            'A': 80,
            'B': 60,
            'C': 40,
            'D': 20,
        }
        
        xp_amount = xp_rewards.get(self.grade, 0)
        
        # Bonus XP nếu task có xp_reward
        if self.task_id.xp_reward:
            xp_amount += self.task_id.xp_reward
        
        # Gửi thông báo cho nhân viên (thay vì cộng XP trực tiếp vì quan_ly_nhan_su chưa có field total_xp)
        nhan_vien.message_post(
            body=_('🎉 Hoàn thành task "%s" với xếp hạng %s. Nhận %d XP!') % (
                self.task_id.name,
                self.grade,
                xp_amount
            ),
            subject=_('XP Reward'),
            message_type='notification'
        )

    def action_view_task(self):
        """Mở Task liên quan"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'project.task',
            'res_id': self.task_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
