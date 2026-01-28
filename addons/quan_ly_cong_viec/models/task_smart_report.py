# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
import re

_logger = logging.getLogger(__name__)


class TaskSmartReport(models.Model):
    _name = 'task.smart.report'
    _description = 'Báo cáo Tiến độ Thông minh'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'
    _rec_name = 'task_id'

    # === BASIC INFO ===
    task_id = fields.Many2one(
        'project.task',
        string='Công việc',
        required=True,
        ondelete='cascade'
    )
    
    user_id = fields.Many2one(
        'res.users',
        string='Người báo cáo',
        default=lambda self: self.env.user,
        required=True
    )
    
    report_date = fields.Datetime(
        string='Ngày giờ báo cáo',
        default=fields.Datetime.now,
        required=True
    )
    
    # === REPORT CONTENT ===
    report_content = fields.Text(
        string='Nội dung Báo cáo',
        required=True,
        help='Nhập tự do: Bạn đã làm được gì? Gặp khó khăn gì?'
    )
    
    time_spent = fields.Float(
        string='Thời gian làm việc (h)',
        required=True,
        help='Số giờ thực tế làm việc trong kỳ báo cáo này'
    )
    
    progress_percentage = fields.Integer(
        string='% Hoàn thành',
        readonly=True,
        help='SNAPSHOT % tại thời điểm báo cáo (không thay đổi khi checklist update sau này)'
    )
    
    # === AI ANALYSIS ===
    ai_summary = fields.Text(
        string='Tóm tắt AI',
        readonly=True,
        help='AI tự động tóm tắt nội dung báo cáo'
    )
    
    sentiment_score = fields.Selection([
        ('positive', 'Tích cực'),
        ('neutral', 'Trung lập'),
        ('negative', 'Tiêu cực'),
    ], string='Cảm xúc', readonly=True, help='AI phân tích cảm xúc')
    
    blocker_detected = fields.Boolean(
        string='Phát hiện Vướng mắc',
        default=False,
        readonly=True,
        help='AI tự động đánh dấu nếu phát hiện khó khăn'
    )
    
    risk_keywords = fields.Char(
        string='Từ khóa Rủi ro',
        readonly=True,
        help='Các từ khóa AI phát hiện được'
    )
    
    # === RELATIONS ===
    attachment_ids = fields.Many2many(
        'ir.attachment',
        string='Tệp đính kèm',
        help='Ảnh chụp màn hình, file kết quả...'
    )
    
    # === HELPER FIELDS FOR VIEW ===
    checklist_ids = fields.One2many(
        related='task_id.checklist_ids',
        string='Checklist',
        readonly=False,
        help='Checklist của task - có thể tick/untick trong form báo cáo'
    )

    # ==================
    # BUSINESS LOGIC
    # ==================
    @api.model_create_multi
    def create(self, vals_list):
        """Override: Tự động phân tích AI khi tạo báo cáo"""
        # AI Processing for each report
        for vals in vals_list:
            if vals.get('report_content'):
                ai_result = self._ai_analyze_report(vals['report_content'])
                vals.update(ai_result)
            
            # SNAPSHOT % hoàn thành tại thời điểm này (không đổi sau này)
            if vals.get('task_id'):
                task = self.env['project.task'].browse(vals['task_id'])
                progress = self._calculate_progress_snapshot(task, vals)
                vals['progress_percentage'] = progress
        
        reports = super(TaskSmartReport, self).create(vals_list)
        
        # Update task status based on AI analysis
        for report in reports:
            # 🤖 AI AUTO-TICK CHECKLIST (KILLER FEATURE!)
            if report.task_id.checklist_ids and report.report_content:
                auto_ticked = report._ai_auto_tick_checklist()
                if auto_ticked:
                    report.message_post(
                        body=f"🤖 AI đã tự động tick {len(auto_ticked)} checklist items: {', '.join(auto_ticked)}",
                        message_type='notification',
                    )
            
            if report.blocker_detected:
                # Phát hiện vấn đề → Set blocker flag
                report.task_id.write({
                    'blocker_flag': True,
                    'risk_level': 'high',
                })
                report._notify_manager_about_blocker()
            else:
                # Báo cáo tốt → Tự động xóa cảnh báo blocker
                if report.task_id.blocker_flag:
                    report.task_id.write({
                        'blocker_flag': False,
                        'risk_level': 'low',
                    })
                    # Thông báo trên Chatter
                    report.task_id.message_post(
                        body=f"✅ Cảnh báo đã được gỡ bỏ! Báo cáo mới cho thấy tiến độ tốt.<br/>"
                             f"<b>AI Analysis:</b> {report.ai_summary}",
                        message_type='notification',
                        subtype_xmlid='mail.mt_note',
                    )
            
            # Post to Chatter
            report._post_to_chatter()
            
            # Trigger Milestone completion percentage update
            if report.task_id.milestone_id:
                report.task_id.milestone_id._compute_completion_percentage()
        
        return reports
    
    @api.onchange('report_content')
    def _onchange_report_content_auto_tick(self):
        """
        🤖 AI AUTO-TICK REAL-TIME khi gõ báo cáo
        """
        if not self.report_content or not self.task_id.checklist_ids:
            return
        
        # Call AI auto-tick (không lưu DB, chỉ preview)
        auto_ticked = self._ai_auto_tick_checklist_preview()
        
        if auto_ticked:
            # Show notification trong form
            return {
                'warning': {
                    'title': '🤖 AI đã phát hiện',
                    'message': f'AI sẽ tự động tick {len(auto_ticked)} items:\n' + '\n'.join([f'✓ {item}' for item in auto_ticked])
                }
            }
    
    def action_submit_and_auto_tick(self):
        """
        🚀 GỬI BÁO CÁO + AI AUTO-TICK (One-click submit!)
        
        Workflow:
        1. Lưu báo cáo (auto AI analysis)
        2. AI auto-tick checklist
        3. Update task progress
        4. Show notification
        5. Close wizard
        """
        self.ensure_one()
        
        # Nếu là record mới (chưa save)
        if not self.id:
            # Create sẽ tự động trigger AI analysis và auto-tick
            self.create({
                'task_id': self.task_id.id,
                'user_id': self.env.user.id,
                'report_date': self.report_date or fields.Datetime.now(),
                'report_content': self.report_content,
                'time_spent': self.time_spent,
                'attachment_ids': [(6, 0, self.attachment_ids.ids)],
            })
        else:
            # Update existing record
            self.write({
                'report_content': self.report_content,
                'time_spent': self.time_spent,
            })
            
            # Trigger AI analysis manually
            ai_result = self._ai_analyze_report(self.report_content)
            self.write(ai_result)
            
            # Auto-tick checklist
            if self.task_id.checklist_ids:
                auto_ticked = self._ai_auto_tick_checklist()
                if auto_ticked:
                    self.message_post(
                        body=f"🤖 AI đã tự động tick {len(auto_ticked)} items: {', '.join(auto_ticked)}",
                        message_type='notification',
                    )
        
        # Get updated stats
        task = self.task_id
        checklist_done = len(task.checklist_ids.filtered('is_done'))
        checklist_total = len(task.checklist_ids)
        progress = int(task.checklist_progress) if task.checklist_ids else int(self.progress_percentage)
        
        # Show success notification
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': '✅ Báo cáo đã gửi thành công!',
                'message': f"""📊 Tiến độ cập nhật: {progress}%
✅ Checklist: {checklist_done}/{checklist_total} items hoàn thành
🤖 AI: {self.ai_summary or 'Đã phân tích'}""",
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }
    
    def action_submit_report(self):
        """Submit report from wizard - just close the wizard"""
        return {'type': 'ir.actions.act_window_close'}

    def _ai_analyze_report(self, content):
        """
        AI phân tích nội dung báo cáo sử dụng Sentiment Analyzer nâng cao
        """
        # Lấy sentiment analyzer
        analyzer = self.env['task.sentiment.analyzer']
        
        # Phân tích nội dung báo cáo
        analysis = analyzer.analyze_text(content or '')
        
        result = {
            'ai_summary': analysis.get('summary', ''),
            'sentiment_score': analysis['sentiment'],
            'blocker_detected': False,
            'risk_keywords': '',
        }
        
        # Phát hiện blocker nếu sentiment rất tiêu cực
        if analysis['score'] < -0.5:
            result['blocker_detected'] = True
            # Lấy các từ tiêu cực tìm thấy
            negative_words = [
                detail['word'] for detail in analysis.get('details', [])
                if detail['final_score'] < 0
            ]
            result['risk_keywords'] = ', '.join(negative_words[:5])  # Lấy 5 từ đầu
        
        # Tạo summary ngắn gọn
        if analysis['score'] > 0.5:
            result['ai_summary'] = f"✓ Tiến độ tốt (Score: {analysis['score']}). Tìm thấy {analysis['keyword_count']} từ khóa tích cực."
        elif analysis['score'] < -0.5:
            result['ai_summary'] = f"⚠ Có vấn đề (Score: {analysis['score']}). Phát hiện {len(negative_words)} từ khóa cảnh báo."
        else:
            result['ai_summary'] = f"→ Tiến độ ổn định (Score: {analysis['score']}). Confidence: {analysis['confidence']*100:.0f}%"
        
        _logger.info(f'AI Analysis Result: {result} | Details: {analysis}')
        
        return result

    def _calculate_progress_snapshot(self, task, vals):
        """
        📸 Tính SNAPSHOT % hoàn thành tại thời điểm báo cáo
        % này sẽ LƯU CỐ ĐỊNH, không thay đổi khi checklist update sau
        """
        progress = 0
        
        # Ưu tiên 1: CHECKLIST (chính xác nhất)
        if task.checklist_ids:
            total_weight = sum(task.checklist_ids.mapped('weight'))
            done_weight = sum(task.checklist_ids.filtered('is_done').mapped('weight'))
            if total_weight > 0:
                progress = int((done_weight / total_weight) * 100)
            else:
                total = len(task.checklist_ids)
                done = len(task.checklist_ids.filtered('is_done'))
                progress = int((done / total * 100)) if total > 0 else 0
            
            _logger.info(f'📸 SNAPSHOT Progress from checklist: {progress}%')
        
        # Fallback: Stage + Time
        else:
            if task.stage_id:
                if task.stage_id.is_closed:
                    progress = 100
                elif 'progress' in task.stage_id.name.lower() or 'doing' in task.stage_id.name.lower():
                    progress = 50
                else:
                    progress = 0
            
            if progress < 100 and task.planned_hours > 0:
                total_time_spent = sum(task.smart_report_ids.mapped('time_spent')) + vals.get('time_spent', 0)
                time_progress = min(int((total_time_spent / task.planned_hours) * 100), 95)
                progress = max(progress, time_progress)
        
        # Điều chỉnh dựa trên AI sentiment
        sentiment = vals.get('sentiment_score', 'neutral')
        blocker = vals.get('blocker_detected', False)
        
        if sentiment == 'positive':
            progress = min(progress + 5, 95)
        elif blocker:
            progress = max(progress - 10, 0)
        
        return max(0, min(progress, 100))

    def _ai_auto_tick_checklist(self):
        """
        🤖 AI TỰ ĐỘNG TICK CHECKLIST (KILLER FEATURE!)
        
        Cách hoạt động:
        1. Parse report_content → Extract completed tasks
        2. Fuzzy match với checklist items
        3. Auto-tick items match (>70% similarity)
        4. Return list of auto-ticked items
        
        VD: "Hôm nay tôi đã hoàn thành design UI và code backend"
        → AI tick: ✓ "Design UI", ✓ "Code backend"
        """
        self.ensure_one()
        
        _logger.info(f'=== AI AUTO-TICK CHECKLIST START ===')
        _logger.info(f'Task ID: {self.task_id.id}')
        _logger.info(f'Checklist items count: {len(self.task_id.checklist_ids)}')
        _logger.info(f'Report content: {self.report_content[:200]}...')
        
        if not self.task_id.checklist_ids:
            _logger.warning('No checklist items found!')
            return []
            
        if not self.report_content:
            _logger.warning('No report content!')
            return []
        
        # Import difflib for fuzzy matching
        from difflib import SequenceMatcher
        
        content_lower = self.report_content.lower()
        auto_ticked = []
        
        # Từ khóa completion - RELAXED (bỏ yêu cầu bắt buộc)
        completion_keywords = [
            'hoàn thành', 'xong', 'done', 'completed', 'finished',
            'làm xong', 'đã làm', 'đã hoàn thành', 'complete',
            'fix xong', 'solved', 'resolved', 'implemented',
            'đã', 'rồi', 'được', 'finish'
        ]
        
        # Check if có từ khóa completion trong content
        has_completion = any(kw in content_lower for kw in completion_keywords)
        
        # Các checklist items chưa done
        pending_items = self.task_id.checklist_ids.filtered(lambda c: not c.is_done)
        _logger.info(f'Pending checklist items: {len(pending_items)}')
        
        for item in pending_items:
            item_name_lower = item.name.lower()
            _logger.info(f'Checking item: "{item.name}"')
            
            # Method 1: SUPER RELAXED - Direct substring match (không cần completion keyword)
            # VD: "Design UI" in "Tôi đang design UI"
            if item_name_lower in content_lower or any(word in content_lower for word in item_name_lower.split() if len(word) > 3):
                item.write({'is_done': True})
                auto_ticked.append(item.name)
                _logger.info(f'✓ Auto-ticked (relaxed match): {item.name}')
                continue
            
            # Method 2: Fuzzy matching - Giảm threshold xuống 50%
            item_words = item_name_lower.split()
            max_similarity = 0
            best_match = ''
            
            # Chia content thành các cụm 2-6 từ
            words = content_lower.split()
            for i in range(len(words)):
                for window_size in [2, 3, 4, 5, 6]:
                    if i + window_size > len(words):
                        continue
                    
                    phrase = ' '.join(words[i:i+window_size])
                    
                    # Tính similarity
                    similarity = SequenceMatcher(None, item_name_lower, phrase).ratio()
                    if similarity > max_similarity:
                        max_similarity = similarity
                        best_match = phrase
                    
                    # Nếu match >50% (đã giảm từ 70%)
                    if similarity > 0.5:
                        item.write({'is_done': True})
                        auto_ticked.append(item.name)
                        _logger.info(f'✓ Auto-ticked (fuzzy {similarity:.0%}): {item.name} ~ "{phrase}"')
                        break
                if item.is_done:
                    break
            
            if not item.is_done and max_similarity > 0:
                _logger.info(f'  Best match: "{best_match}" (similarity: {max_similarity:.0%}) - Not enough')
            
            # Method 3: Keyword extraction - Tìm 1 từ khóa quan trọng là đủ
            if not item.is_done:
                important_words = [w for w in item_words if len(w) > 3]
                if important_words:
                    # Nếu tìm thấy BẤT KỲ từ quan trọng nào
                    found_words = [w for w in important_words if w in content_lower]
                    if found_words:
                        item.write({'is_done': True})
                        auto_ticked.append(item.name)
                        _logger.info(f'✓ Auto-ticked (keyword match): {item.name} (found: {found_words})')
        
        _logger.info(f'=== AI AUTO-TICK RESULT: {len(auto_ticked)} items ticked ===')
        return auto_ticked

    def _ai_auto_tick_checklist_preview(self):
        """
        Preview version - không lưu DB, chỉ return danh sách items sẽ được tick
        Dùng cho onchange
        """
        if not self.task_id.checklist_ids or not self.report_content:
            return []
        
        from difflib import SequenceMatcher
        
        content_lower = self.report_content.lower()
        will_tick = []
        
        completion_keywords = [
            'hoàn thành', 'xong', 'done', 'completed', 'finished',
            'làm xong', 'đã làm', 'đã hoàn thành', 'complete',
            'fix xong', 'solved', 'resolved', 'implemented'
        ]
        
        pending_items = self.task_id.checklist_ids.filtered(lambda c: not c.is_done)
        
        for item in pending_items:
            item_name_lower = item.name.lower()
            matched = False
            
            # Direct match
            if item_name_lower in content_lower:
                for keyword in completion_keywords:
                    if keyword in content_lower:
                        will_tick.append(item.name)
                        matched = True
                        break
            
            if matched:
                continue
            
            # Fuzzy match
            words = content_lower.split()
            for i in range(len(words)):
                for window_size in [3, 4, 5]:
                    if i + window_size > len(words):
                        continue
                    phrase = ' '.join(words[i:i+window_size])
                    similarity = SequenceMatcher(None, item_name_lower, phrase).ratio()
                    
                    if similarity > 0.7:
                        for keyword in completion_keywords:
                            if keyword in content_lower:
                                will_tick.append(item.name)
                                matched = True
                                break
                    if matched:
                        break
                if matched:
                    break
        
        return will_tick

    def _notify_manager_about_blocker(self):
        """Gửi thông báo cho PM khi phát hiện vướng mắc"""
        self.ensure_one()
        
        if not self.task_id.project_id.user_id:
            return
        
        # Create activity for PM
        self.env['mail.activity'].create({
            'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
            'summary': f'Cảnh báo: Task bị vướng mắc',
            'note': f'''
                <p><strong>{self.user_id.name}</strong> báo cáo có khó khăn trong task 
                <a href="/web#id={self.task_id.id}&model=project.task">{self.task_id.name}</a></p>
                <p><em>"{self.report_content[:100]}..."</em></p>
                <p>Từ khóa rủi ro: <strong>{self.risk_keywords}</strong></p>
            ''',
            'user_id': self.task_id.project_id.user_id.id,
            'res_id': self.task_id.id,
            'res_model_id': self.env.ref('project.model_project_task').id,
        })

    def _post_to_chatter(self):
        """Đăng báo cáo lên Chatter của Task"""
        self.ensure_one()
        
        message = f'''
            <div style="background:#f0f0f0; padding:10px; border-radius:5px;">
                <h4>📝 Báo cáo tiến độ</h4>
                <p><strong>Tiến độ:</strong> {self.progress_percentage}%</p>
                <p><strong>Thời gian:</strong> {self.time_spent}h</p>
                <p><strong>Nội dung:</strong><br/>{self.report_content}</p>
        '''
        
        if self.ai_summary:
            message += f'<p style="color:#666;"><em>AI tóm tắt: {self.ai_summary}</em></p>'
        
        if self.blocker_detected:
            message += '<p style="color:red;"><strong>⚠️ Phát hiện vướng mắc!</strong></p>'
        
        message += '</div>'
        
        self.task_id.message_post(
            body=message,
            message_type='notification',
            subtype_xmlid='mail.mt_note',
        )

    def action_mark_as_blocker(self):
        """Đánh dấu thủ công là Blocker"""
        self.write({'blocker_detected': True})
        self.task_id.write({
            'blocker_flag': True,
            'risk_level': 'high',
        })
        self._notify_manager_about_blocker()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Đã đánh dấu Vướng mắc'),
                'message': _('Quản lý dự án đã được thông báo.'),
                'type': 'warning',
            }
        }
