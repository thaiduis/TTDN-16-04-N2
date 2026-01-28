# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class TaskChecklist(models.Model):
    _name = 'task.checklist'
    _description = 'Checklist Công việc'
    _order = 'sequence, id'
    _rec_name = 'name'

    # === BASIC INFO ===
    name = fields.Char(
        string='Công việc cần làm',
        required=True,
        help='Mô tả chi tiết bước công việc'
    )
    
    task_id = fields.Many2one(
        'project.task',
        string='Task',
        required=True,
        ondelete='cascade'
    )
    
    sequence = fields.Integer(
        string='Thứ tự',
        default=10,
        help='Thứ tự hiển thị'
    )
    
    # === STATUS ===
    is_done = fields.Boolean(
        string='Hoàn thành',
        default=False,
        tracking=True
    )
    
    done_date = fields.Datetime(
        string='Ngày hoàn thành',
        readonly=True
    )
    
    done_by = fields.Many2one(
        'res.users',
        string='Người hoàn thành',
        readonly=True
    )
    
    # === WEIGHT & PRIORITY ===
    weight = fields.Integer(
        string='Trọng số',
        default=1,
        help='Độ quan trọng (1-5). Item quan trọng hơn = trọng số cao hơn'
    )
    
    estimated_hours = fields.Float(
        string='Giờ dự kiến',
        help='Thời gian ước tính để hoàn thành item này'
    )
    
    # === AI FIELDS ===
    ai_suggested = fields.Boolean(
        string='AI Đề xuất',
        default=False,
        help='Item này được AI tự động tạo'
    )
    
    ai_risk_level = fields.Selection([
        ('low', 'Thấp'),
        ('medium', 'Trung bình'),
        ('high', 'Cao'),
    ], string='Rủi ro AI', compute='_compute_ai_risk', store=True)
    
    # === RELATIONS ===
    dependency_ids = fields.Many2many(
        'task.checklist',
        'checklist_dependency_rel',
        'checklist_id',
        'dependency_id',
        string='Phụ thuộc vào',
        help='Các item cần hoàn thành trước'
    )
    
    notes = fields.Text(
        string='Ghi chú',
        help='Hướng dẫn, tài liệu tham khảo...'
    )

    # ==================
    # COMPUTED FIELDS
    # ==================
    @api.depends('is_done', 'dependency_ids', 'dependency_ids.is_done', 'estimated_hours')
    def _compute_ai_risk(self):
        """AI tự động đánh giá rủi ro của item"""
        for item in self:
            risk = 'low'
            
            # Nếu item chưa done và có dependency chưa done → Risk cao
            if not item.is_done and item.dependency_ids:
                pending_deps = item.dependency_ids.filtered(lambda d: not d.is_done)
                if len(pending_deps) >= 2:
                    risk = 'high'
                elif len(pending_deps) == 1:
                    risk = 'medium'
            
            # Nếu estimate quá cao → Risk
            if item.estimated_hours > 8:
                risk = 'high'
            
            item.ai_risk_level = risk

    # ==================
    # BUSINESS LOGIC
    # ==================
    def write(self, vals):
        """Override: Track completion"""
        if 'is_done' in vals and vals['is_done']:
            vals['done_date'] = fields.Datetime.now()
            vals['done_by'] = self.env.user.id
            
            # Notify user khi complete
            self.task_id.message_post(
                body=f"✅ Checklist item hoàn thành: <b>{self.name}</b>",
                message_type='notification',
            )
        
        result = super(TaskChecklist, self).write(vals)
        
        # Update task progress
        self.task_id._compute_checklist_progress()
        
        return result

    @api.model
    def ai_suggest_checklist(self, task):
        """
        🤖 AI tự động đề xuất checklist dựa trên tên/mô tả task
        """
        # Import OpenAI nếu có
        try:
            ai_assistant = self.env['task.ai.assistant'].search([
                ('active', '=', True)
            ], limit=1)
            
            if not ai_assistant or not ai_assistant.api_key:
                # Fallback: Rule-based suggestions
                return self._rule_based_suggestions(task)
            
            # Call OpenAI để generate checklist
            prompt = f"""
Bạn là trợ lý quản lý dự án. Hãy tạo checklist chi tiết cho task sau:

Task: {task.name}
Mô tả: {task.description or 'Không có'}
Dự kiến: {task.planned_hours or 0} giờ

Yêu cầu:
1. Chia thành 5-10 bước cụ thể
2. Sắp xếp theo thứ tự logic
3. Ước tính giờ cho mỗi bước
4. Đánh trọng số (1-5) dựa trên độ quan trọng

Trả về JSON format:
[
  {{"name": "Bước 1", "hours": 2, "weight": 3, "sequence": 1}},
  ...
]
"""
            
            response = ai_assistant._call_openai(
                messages=[{'role': 'user', 'content': prompt}],
                temperature=0.7
            )
            
            # Parse JSON response
            import json
            import re
            
            # Extract JSON từ response
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                suggestions = json.loads(json_match.group())
                
                # Create checklist items
                for item in suggestions:
                    self.create({
                        'task_id': task.id,
                        'name': item.get('name', ''),
                        'estimated_hours': item.get('hours', 0),
                        'weight': item.get('weight', 1),
                        'sequence': item.get('sequence', 10),
                        'ai_suggested': True,
                    })
                
                _logger.info(f'AI created {len(suggestions)} checklist items for task {task.id}')
                return True
            
        except Exception as e:
            _logger.warning(f'AI suggestion failed: {e}. Using rule-based.')
            return self._rule_based_suggestions(task)
        
        return self._rule_based_suggestions(task)

    def _rule_based_suggestions(self, task):
        """Fallback: Rule-based checklist suggestions"""
        suggestions = []
        task_name_lower = (task.name or '').lower()
        
        # Common software development checklist
        if any(word in task_name_lower for word in ['code', 'develop', 'làm', 'tạo', 'build']):
            suggestions = [
                {'name': '1. Phân tích yêu cầu & thiết kế', 'hours': 2, 'weight': 3, 'seq': 1},
                {'name': '2. Setup môi trường & tools', 'hours': 1, 'weight': 2, 'seq': 2},
                {'name': '3. Code chức năng chính', 'hours': 4, 'weight': 5, 'seq': 3},
                {'name': '4. Viết unit tests', 'hours': 2, 'weight': 3, 'seq': 4},
                {'name': '5. Code review & refactor', 'hours': 1, 'weight': 2, 'seq': 5},
                {'name': '6. Integration test', 'hours': 1, 'weight': 3, 'seq': 6},
                {'name': '7. Viết documentation', 'hours': 1, 'weight': 2, 'seq': 7},
                {'name': '8. Deploy & verify', 'hours': 1, 'weight': 4, 'seq': 8},
            ]
        
        # Bug fix checklist
        elif any(word in task_name_lower for word in ['bug', 'fix', 'lỗi', 'sửa']):
            suggestions = [
                {'name': '1. Reproduce bug & xác định nguyên nhân', 'hours': 1, 'weight': 4, 'seq': 1},
                {'name': '2. Viết test case cho bug', 'hours': 0.5, 'weight': 3, 'seq': 2},
                {'name': '3. Fix code', 'hours': 2, 'weight': 5, 'seq': 3},
                {'name': '4. Verify fix works', 'hours': 0.5, 'weight': 4, 'seq': 4},
                {'name': '5. Regression test', 'hours': 1, 'weight': 3, 'seq': 5},
                {'name': '6. Deploy & monitor', 'hours': 0.5, 'weight': 3, 'seq': 6},
            ]
        
        # Research/Learning task
        elif any(word in task_name_lower for word in ['research', 'học', 'tìm hiểu', 'nghiên cứu']):
            suggestions = [
                {'name': '1. Xác định mục tiêu research', 'hours': 0.5, 'weight': 3, 'seq': 1},
                {'name': '2. Thu thập tài liệu & nguồn', 'hours': 2, 'weight': 3, 'seq': 2},
                {'name': '3. Đọc & phân tích', 'hours': 4, 'weight': 4, 'seq': 3},
                {'name': '4. Làm POC/Demo nhỏ', 'hours': 2, 'weight': 3, 'seq': 4},
                {'name': '5. Viết báo cáo tổng hợp', 'hours': 1, 'weight': 2, 'seq': 5},
            ]
        
        # Generic checklist
        else:
            suggestions = [
                {'name': '1. Lên kế hoạch chi tiết', 'hours': 1, 'weight': 3, 'seq': 1},
                {'name': '2. Chuẩn bị tài nguyên', 'hours': 1, 'weight': 2, 'seq': 2},
                {'name': '3. Thực hiện công việc chính', 'hours': 5, 'weight': 5, 'seq': 3},
                {'name': '4. Review & kiểm tra chất lượng', 'hours': 1, 'weight': 3, 'seq': 4},
                {'name': '5. Hoàn thiện & bàn giao', 'hours': 1, 'weight': 3, 'seq': 5},
            ]
        
        # Create items
        for item in suggestions:
            self.create({
                'task_id': task.id,
                'name': item['name'],
                'estimated_hours': item['hours'],
                'weight': item['weight'],
                'sequence': item['seq'],
                'ai_suggested': True,
            })
        
        return True

    def action_toggle_done(self):
        """Quick toggle done/undone"""
        for item in self:
            item.is_done = not item.is_done
