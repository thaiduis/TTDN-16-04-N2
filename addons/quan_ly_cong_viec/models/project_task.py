# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class ProjectTask(models.Model):
    _inherit = 'project.task'

    # === SMART FIELDS ===
    smart_report_ids = fields.One2many(
        'task.smart.report',
        'task_id',
        string='Báo cáo Tiến độ',
        help='Lịch sử các lần nhân viên báo cáo công việc'
    )
    
    checklist_ids = fields.One2many(
        'task.checklist',
        'task_id',
        string='Checklist',
        help='Danh sách công việc cần làm'
    )
    
    checklist_progress = fields.Float(
        string='% Checklist',
        compute='_compute_checklist_progress',
        store=True,
        help='% hoàn thành dựa trên checklist (weighted)'
    )
    
    checklist_count = fields.Integer(
        string='Số Items',
        compute='_compute_checklist_stats'
    )
    
    checklist_done = fields.Integer(
        string='Đã xong',
        compute='_compute_checklist_stats'
    )
    
    score_card_id = fields.Many2one(
        'task.score.card',
        string='Phiếu Điểm',
        help='Điểm đánh giá tự động khi hoàn thành',
        readonly=True
    )
    
    # === RISK & BLOCKER ===
    blocker_flag = fields.Boolean(
        string='Đang bị Chặn',
        default=False,
        help='Tự động đánh dấu khi AI phát hiện vướng mắc'
    )
    
    risk_level = fields.Selection([
        ('low', 'Thấp'),
        ('medium', 'Trung bình'),
        ('high', 'Cao'),
        ('critical', 'Nghiêm trọng'),
    ], string='Mức độ Rủi ro', default='low', tracking=True)
    
    # === SKILL REQUIREMENTS ===
    required_skill_ids = fields.Many2many(
        'hr.skill',
        string='Kỹ năng Yêu cầu',
        help='Kỹ năng cần có để thực hiện task này'
    )    
    skill_match_warning = fields.Text(
        string='Cảnh báo Kỹ năng',
        compute='_compute_skill_match',
        help='Cảnh báo nếu người được gán thiếu kỹ năng'
    )    
    skill_level_required = fields.Integer(
        string='Mức độ Kỹ năng',
        default=1,
        help='Cấp độ kỹ năng tối thiểu (1-5)'
    )
    
    # === TIME TRACKING ===
    # estimated_hours đã có sẵn trong project.task (planned_hours hoặc estimated_hours tùy version)
    
    actual_hours = fields.Float(
        string='Thời gian Thực tế (h)',
        compute='_compute_actual_hours',
        store=True,
        help='Tổng thời gian từ các báo cáo'
    )
    
    efficiency_ratio = fields.Float(
        string='Tỷ lệ Hiệu suất',
        compute='_compute_efficiency_ratio',
        help='Estimated / Actual (>1 = Tốt, <1 = Chậm)'
    )
    
    # === GAMIFICATION ===
    xp_reward = fields.Integer(
        string='XP Thưởng',
        default=0,
        help='Điểm kinh nghiệm cộng cho nhân viên khi hoàn thành'
    )

    # === CHI TIẾT THỰC TẾ ===
    priority_level = fields.Selection([
        ('0', 'Rất thấp'),
        ('1', 'Thấp'),
        ('2', 'Bình thường'),
        ('3', 'Cao'),
        ('4', 'Khẩn cấp'),
    ], string='Độ ưu tiên', default='2', tracking=True)
    
    complexity = fields.Selection([
        ('easy', 'Dễ (1-2 ngày)'),
        ('medium', 'Trung bình (3-5 ngày)'),
        ('hard', 'Khó (1-2 tuần)'),
        ('epic', 'Epic (>2 tuần)'),
    ], string='Độ phức tạp', default='medium')
    
    testing_status = fields.Selection([
        ('not_started', 'Chưa test'),
        ('in_testing', 'Đang test'),
        ('passed', 'Pass'),
        ('failed', 'Fail'),
    ], string='Trạng thái Test', default='not_started')
    
    code_review_status = fields.Selection([
        ('not_required', 'Không cần'),
        ('pending', 'Chờ review'),
        ('approved', 'Đã duyệt'),
        ('rejected', 'Yêu cầu sửa'),
    ], string='Code Review', default='not_required')
    
    bug_count = fields.Integer(
        string='Số Bug',
        default=0,
        help='Số lỗi phát hiện trong task'
    )
    
    rework_count = fields.Integer(
        string='Số lần Rework',
        default=0,
        help='Số lần phải làm lại'
    )
    
    github_link = fields.Char(
        string='GitHub PR/Issue',
        help='Link đến Pull Request hoặc Issue'
    )
    
    jira_ticket = fields.Char(
        string='Jira Ticket',
        help='Mã ticket Jira (nếu có)'
    )
    
    external_task_id = fields.Char(
        string='External Task ID',
        help='ID task từ hệ thống bên ngoài'
    )
    
    # === AI FEATURES ===
    ai_risk_score = fields.Float(
        string='AI Risk Score',
        compute='_compute_ai_risk_score',
        help='Điểm rủi ro do AI tính (0-100)'
    )
    
    ai_suggestions = fields.Text(
        string='AI Suggestions',
        help='Gợi ý từ AI để cải thiện task'
    )
    
    ai_estimated_hours = fields.Float(
        string='AI Dự đoán (giờ)',
        help='Thời gian AI dự đoán dựa trên lịch sử'
    )
    
    sentiment_score = fields.Float(
        string='Sentiment Score',
        help='Điểm cảm xúc từ báo cáo (-1 đến 1)'
    )

    # === DEPENDENCIES ===
    dependent_task_ids = fields.Many2many(
        'project.task',
        'task_dependency_rel',
        'task_id',
        'depends_on_id',
        string='Phụ thuộc vào Task',
        help='Task này chỉ bắt đầu được khi các task khác hoàn thành'
    )
    
    # === PROJECT STRUCTURE INTEGRATION ===
    milestone_id = fields.Many2one(
        'project.milestone',
        string='Milestone',
        help='Cột mốc dự án mà task này thuộc về'
    )
    
    # === HELPERS FOR VIEW ===
    is_task_closed = fields.Boolean(
        string='Task đã đóng',
        compute='_compute_is_task_closed',
        help='Kiểm tra xem stage có fold=True không (dùng cho attrs)'
    )

    @api.depends('checklist_ids', 'checklist_ids.is_done')
    def _compute_checklist_stats(self):
        """Thống kê checklist"""
        for task in self:
            task.checklist_count = len(task.checklist_ids)
            task.checklist_done = len(task.checklist_ids.filtered('is_done'))
    
    @api.depends('checklist_ids', 'checklist_ids.is_done', 'checklist_ids.weight')
    def _compute_checklist_progress(self):
        """
        🎯 Tính % hoàn thành dựa trên CHECKLIST (weighted)
        Đây là phương pháp CHÍNH XÁC NHẤT!
        """
        for task in self:
            if not task.checklist_ids:
                task.checklist_progress = 0.0
                continue
            
            # Tính weighted progress
            total_weight = sum(task.checklist_ids.mapped('weight'))
            done_weight = sum(task.checklist_ids.filtered('is_done').mapped('weight'))
            
            if total_weight > 0:
                task.checklist_progress = (done_weight / total_weight) * 100
            else:
                # Fallback: simple count
                total = len(task.checklist_ids)
                done = len(task.checklist_ids.filtered('is_done'))
                task.checklist_progress = (done / total * 100) if total > 0 else 0

    @api.depends('required_skill_ids', 'user_ids')
    def _compute_skill_match(self):
        """Kiểm tra kỹ năng nhân viên vs yêu cầu công việc"""
        for task in self:
            if not task.required_skill_ids or not task.user_ids:
                task.skill_match_warning = False
                continue
            
            # Check if quan_ly_nhan_su module is installed
            if 'nhan_vien' not in self.env:
                task.skill_match_warning = False
                continue
            
            warnings = []
            for user in task.user_ids:
                # Tìm nhan_vien tương ứng
                nhan_vien = self.env['nhan_vien'].search([
                    '|',
                    ('email', '=', user.login),
                    ('name', '=', user.name)
                ], limit=1)
                
                if not nhan_vien:
                    continue
                
                # Kiểm tra từng skill yêu cầu
                for required_skill in task.required_skill_ids:
                    # Tìm trong ky_nang_ids của nhan_vien
                    emp_skill = nhan_vien.ky_nang_ids.filtered(
                        lambda s: s.ky_nang_id.name == required_skill.name
                    )
                    
                    if not emp_skill:
                        warnings.append(f"⚠️ {nhan_vien.name} chưa có kỹ năng '{required_skill.name}'")
                    else:
                        # Kiểm tra trình độ
                        level_map = {
                            'moi_hoc': 1, 'co_ban': 2, 'trung_binh': 3,
                            'kha': 4, 'gioi': 5, 'chuyen_gia': 6
                        }
                        emp_level = level_map.get(emp_skill[0].trinh_do, 0)
                        
                        if emp_level < task.skill_level_required:
                            warnings.append(
                                f"⚠️ {nhan_vien.name} có '{required_skill.name}' "
                                f"ở mức {emp_skill[0].trinh_do}, task yêu cầu level {task.skill_level_required}"
                            )
            
            task.skill_match_warning = '\n'.join(warnings) if warnings else False

    @api.depends('stage_id.fold')
    def _compute_is_task_closed(self):
        """Computed field thay thế cho stage_id.fold trong attrs"""
        for task in self:
            task.is_task_closed = task.stage_id.fold if task.stage_id else False
    
    @api.depends('bug_count', 'rework_count', 'actual_hours', 'planned_hours', 'blocker_flag', 'sentiment_score')
    def _compute_ai_risk_score(self):
        """AI tính điểm rủi ro dựa trên các chỉ số"""
        for task in self:
            risk_score = 0.0
            
            # Bug nhiều = rủi ro cao
            if task.bug_count > 5:
                risk_score += 30
            elif task.bug_count > 2:
                risk_score += 15
            
            # Rework nhiều = rủi ro cao
            if task.rework_count > 3:
                risk_score += 25
            elif task.rework_count > 1:
                risk_score += 10
            
            # Vượt deadline = rủi ro
            if task.planned_hours > 0 and task.actual_hours > task.planned_hours * 1.5:
                risk_score += 20
            
            # Blocker = rủi ro
            if task.blocker_flag:
                risk_score += 15
            
            # Sentiment tiêu cực
            if task.sentiment_score and task.sentiment_score < -0.3:
                risk_score += 10
            
            task.ai_risk_score = min(risk_score, 100)
    
    @api.depends('smart_report_ids.time_spent')
    def _compute_actual_hours(self):
        for task in self:
            task.actual_hours = sum(task.smart_report_ids.mapped('time_spent'))

    @api.depends('planned_hours', 'actual_hours')
    def _compute_efficiency_ratio(self):
        for task in self:
            if task.actual_hours > 0:
                task.efficiency_ratio = task.planned_hours / task.actual_hours
            else:
                task.efficiency_ratio = 0.0

    # ==================
    # BUSINESS LOGIC
    # ==================
    def action_start_task(self):
        """Bắt đầu công việc - Kiểm tra điều kiện"""
        self.ensure_one()
        
        # Check: Dependencies
        if self.dependent_task_ids:
            unfinished = self.dependent_task_ids.filtered(lambda t: not t.is_task_closed)
            if unfinished:
                raise UserError(_(
                    'Không thể bắt đầu! Task này phụ thuộc vào:\n%s'
                ) % '\n'.join(unfinished.mapped('name')))
        
        # Check: Skill Gap (HR Integration)
        if self.required_skill_ids and self.user_ids:
            self._check_skill_gap()
        
        # Check: Workload (Prevent Overload)
        self._check_workload()
        
        # Update stage to "In Progress"
        in_progress_stage = self.env['project.task.type'].search([
            ('name', '=', 'In Progress')
        ], limit=1)
        
        if in_progress_stage:
            self.stage_id = in_progress_stage
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Bắt đầu công việc!'),
                'message': _('Chúc bạn làm việc hiệu quả. Hãy báo cáo tiến độ thường xuyên nhé!'),
                'type': 'success',
                'sticky': False,
            }
        }

    def _check_skill_gap(self):
        """Kiểm tra kỹ năng nhân viên vs yêu cầu công việc"""
        self.ensure_one()
        
        # Lấy nhân viên từ user_ids (có thể là nhiều user)
        if not self.user_ids:
            return
        
        # Check if quan_ly_nhan_su module is installed
        if 'nhan_vien' not in self.env:
            _logger.info('Module quan_ly_nhan_su not installed, skipping skill check')
            return
            
        user = self.user_ids[0]
        
        # Tìm nhan_vien tương ứng với user
        nhan_vien = self.env['nhan_vien'].search([
            '|',
            ('email', '=', user.login),
            ('name', '=', user.name)
        ], limit=1)
        
        if not nhan_vien:
            _logger.warning(f'Không tìm thấy nhân viên cho user {user.name}')
            return
        
        # Kiểm tra từng kỹ năng yêu cầu
        for skill in self.required_skill_ids:
            # Tìm trong ky_nang_ids của nhan_vien
            employee_skill = nhan_vien.ky_nang_ids.filtered(
                lambda s: s.ky_nang_id.name == skill.name
            )
            
            if not employee_skill:
                _logger.warning(
                    f'Skill Gap: {nhan_vien.name} chưa có kỹ năng {skill.name}'
                )
            else:
                # Kiểm tra trình độ
                level_map = {
                    'moi_hoc': 1, 
                    'co_ban': 2, 
                    'trung_binh': 3, 
                    'kha': 4, 
                    'gioi': 5, 
                    'chuyen_gia': 6
                }
                emp_level = level_map.get(employee_skill[0].trinh_do, 0)
                
                if emp_level < self.skill_level_required:
                    _logger.warning(
                        f'Skill Gap: {nhan_vien.name} có {skill.name} '
                        f'trình độ {employee_skill[0].trinh_do} '
                        f'nhưng task yêu cầu level {self.skill_level_required}'
                    )

    def _check_workload(self):
        """Kiểm tra khối lượng công việc hiện tại"""
        self.ensure_one()
        
        if not self.user_ids:
            return
        
        # Đếm số task đang làm
        active_tasks = self.search([
            ('user_ids', 'in', self.user_ids.ids),
            ('is_task_closed', '=', False),
            ('id', '!=', self.id),
        ])
        
        if len(active_tasks) >= 3:
            raise UserError(_(
                'Cảnh báo: Bạn đang có %d task chưa hoàn thành.\n'
                'Hãy hoàn thành bớt công việc trước khi nhận thêm!'
            ) % len(active_tasks))

    def action_open_smart_report_wizard(self):
        """Mở popup Smart Report Wizard"""
        self.ensure_one()
        
        return {
            'name': _('Báo cáo Tiến độ Thông minh'),
            'type': 'ir.actions.act_window',
            'res_model': 'task.smart.report',
            'view_mode': 'form',
            'view_id': self.env.ref('quan_ly_cong_viec.view_task_smart_report_wizard').id,
            'target': 'new',
            'context': {
                'default_task_id': self.id,
            }
        }

    def write(self, vals):
        """Override: Tự động chấm điểm khi chuyển sang Done"""
        res = super(ProjectTask, self).write(vals)
        
        # Trigger scoring when task is marked as done
        if vals.get('stage_id'):
            new_stage = self.env['project.task.type'].browse(vals['stage_id'])
            if new_stage.fold:  # Stage is "Done"
                for task in self:
                    if not task.score_card_id:
                        task._auto_generate_score_card()
        
        return res

    def _auto_generate_score_card(self):
        """Tự động tạo Phiếu điểm khi hoàn thành"""
        self.ensure_one()
        
        ScoreCard = self.env['task.score.card']
        
        # Calculate scores
        timeliness_score = self._calculate_timeliness_score()
        efficiency_score = self._calculate_efficiency_score()
        quality_score = self._calculate_quality_score()
        
        # Weighted average
        final_score = (
            timeliness_score * 0.4 +
            efficiency_score * 0.3 +
            quality_score * 0.3
        )
        
        # Create score card
        score_card = ScoreCard.create({
            'task_id': self.id,
            'timeliness_score': timeliness_score,
            'efficiency_score': efficiency_score,
            'quality_score': quality_score,
            'final_score': final_score,
            'ai_feedback': self._generate_ai_feedback(final_score),
        })
        
        self.score_card_id = score_card
        
        # Award XP to employee
        if self.user_ids and self.user_ids[0].employee_id:
            self._award_xp_to_employee(final_score)
        
        return score_card

    def _calculate_timeliness_score(self):
        """Tính điểm Đúng hạn"""
        if not self.date_deadline:
            return 100
        
        # Convert date_deadline (Date field) to datetime for comparison
        from datetime import datetime, time
        deadline_datetime = datetime.combine(self.date_deadline, time.max)
        
        if fields.Datetime.now() <= deadline_datetime:
            return 100  # Đúng hạn hoặc sớm
        
        # Tính độ trễ (giờ)
        delay_hours = (fields.Datetime.now() - deadline_datetime).total_seconds() / 3600
        
        if delay_hours < 24:
            return 80
        elif delay_hours < 48:
            return 60
        else:
            return 50

    def _calculate_efficiency_score(self):
        """Tính điểm Hiệu suất"""
        if not self.planned_hours or not self.actual_hours:
            return 70
        
        ratio = self.efficiency_ratio
        
        if ratio >= 1.2:
            return 100  # Hoàn thành nhanh hơn dự kiến
        elif ratio >= 0.8:
            return 90  # Đúng ước lượng
        elif ratio >= 0.5:
            return 70  # Hơi chậm
        else:
            return 50  # Chậm đáng kể

    def _calculate_quality_score(self):
        """Tính điểm Chất lượng"""
        # Placeholder: Trong thực tế sẽ check số lần re-open, bug reports
        return 100

    def _generate_ai_feedback(self, score):
        """Tạo feedback từ AI (Placeholder)"""
        if score >= 90:
            return "Xuất sắc! Bạn đã hoàn thành công việc một cách hiệu quả."
        elif score >= 70:
            return "Tốt! Hãy cố gắng cải thiện tốc độ trong lần tới."
        else:
            return "Cần cải thiện. Hãy ước lượng thời gian chính xác hơn."

    def _award_xp_to_employee(self, score):
        """Cộng XP cho nhân viên"""
        # Calculate XP based on score
        xp = int(score)  # 1 point = 1 XP
        
        # Placeholder: Thực tế sẽ cập nhật vào hr.employee hoặc gamification
        _logger.info(f'Award {xp} XP to employee for task {self.name}')
        
        self.xp_reward = xp

    # ==================
    # CHECKLIST ACTIONS
    # ==================
    def action_ai_suggest_checklist(self):
        """🤖 AI tự động tạo checklist"""
        self.ensure_one()
        
        if self.checklist_ids:
            raise UserError(
                'Task này đã có checklist!\n'
                'Bạn có thể xóa checklist cũ trước khi tạo mới.'
            )
        
        Checklist = self.env['task.checklist']
        Checklist.ai_suggest_checklist(self)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': '🤖 AI đã tạo Checklist!',
                'message': f'Đã tạo {len(self.checklist_ids)} items cho task này',
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_view_checklist(self):
        """Mở popup checklist"""
        self.ensure_one()
        
        return {
            'name': f'Checklist: {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'task.checklist',
            'view_mode': 'tree',
            'domain': [('task_id', '=', self.id)],
            'context': {
                'default_task_id': self.id,
                'search_default_group_by_sequence': 1,
            },
            'target': 'new',
        }

