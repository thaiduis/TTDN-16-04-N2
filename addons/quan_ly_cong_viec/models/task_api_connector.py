# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import requests
import json
import logging

_logger = logging.getLogger(__name__)


class TaskAPIConnector(models.Model):
    _name = 'task.api.connector'
    _description = 'API Connector cho Task Management'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Tên Connector',
        required=True,
        help='VD: Jira, GitHub, Slack...'
    )
    
    api_type = fields.Selection([
        ('jira', 'Jira'),
        ('github', 'GitHub'),
        ('slack', 'Slack'),
        ('trello', 'Trello'),
        ('asana', 'Asana'),
        ('openai', 'OpenAI'),
        ('custom', 'Custom API'),
    ], string='Loại API', required=True)
    
    base_url = fields.Char(
        string='Base URL',
        required=True,
        help='VD: https://api.github.com'
    )
    
    api_key = fields.Char(
        string='API Key',
        help='API Key hoặc Token'
    )
    
    api_secret = fields.Char(
        string='API Secret',
        help='Secret key (nếu cần)'
    )
    
    webhook_url = fields.Char(
        string='Webhook URL',
        help='URL nhận webhook từ hệ thống ngoài'
    )
    
    is_active = fields.Boolean(
        string='Kích hoạt',
        default=True
    )
    
    # Config JSON
    config_json = fields.Text(
        string='Config JSON',
        help='Cấu hình thêm dưới dạng JSON'
    )
    
    # Sync settings
    auto_sync = fields.Boolean(
        string='Tự động Sync',
        default=False,
        help='Tự động đồng bộ task với hệ thống ngoài'
    )
    
    sync_interval = fields.Integer(
        string='Sync Interval (phút)',
        default=30,
        help='Thời gian giữa các lần sync tự động'
    )
    
    last_sync = fields.Datetime(
        string='Lần sync cuối',
        readonly=True
    )
    
    # Stats
    total_requests = fields.Integer(
        string='Tổng Request',
        default=0,
        readonly=True
    )
    
    failed_requests = fields.Integer(
        string='Request Lỗi',
        default=0,
        readonly=True
    )

    def action_test_connection(self):
        """Test kết nối API"""
        self.ensure_one()
        
        try:
            headers = self._get_headers()
            response = requests.get(
                self.base_url,
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                self.message_post(
                    body=_('✅ Kết nối thành công! Status: %s') % response.status_code,
                    subject=_('API Test Success')
                )
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Thành công'),
                        'message': _('Kết nối API thành công!'),
                        'type': 'success',
                    }
                }
            else:
                raise UserError(_('API trả về status: %s') % response.status_code)
                
        except Exception as e:
            _logger.error(f'API connection failed: {str(e)}')
            raise UserError(_('Lỗi kết nối: %s') % str(e))

    def _get_headers(self):
        """Tạo headers cho API request"""
        self.ensure_one()
        
        headers = {'Content-Type': 'application/json'}
        
        if self.api_type == 'github':
            headers['Authorization'] = f'token {self.api_key}'
        elif self.api_type == 'jira':
            headers['Authorization'] = f'Basic {self.api_key}'
        elif self.api_type == 'openai':
            headers['Authorization'] = f'Bearer {self.api_key}'
        elif self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'
        
        return headers

    def send_request(self, endpoint, method='GET', data=None):
        """Gửi API request"""
        self.ensure_one()
        
        if not self.is_active:
            raise UserError(_('Connector chưa được kích hoạt'))
        
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        headers = self._get_headers()
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=30)
            elif method == 'POST':
                response = requests.post(url, headers=headers, json=data, timeout=30)
            elif method == 'PUT':
                response = requests.put(url, headers=headers, json=data, timeout=30)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=30)
            
            self.total_requests += 1
            
            if response.status_code >= 400:
                self.failed_requests += 1
                raise UserError(_('API Error: %s - %s') % (response.status_code, response.text))
            
            return response.json() if response.text else {}
            
        except requests.exceptions.RequestException as e:
            self.failed_requests += 1
            _logger.error(f'API request failed: {str(e)}')
            raise UserError(_('Request failed: %s') % str(e))

    def sync_tasks(self):
        """Đồng bộ tasks với hệ thống ngoài"""
        self.ensure_one()
        
        tasks = self.env['project.task'].search([
            ('external_task_id', '!=', False)
        ])
        
        synced_count = 0
        for task in tasks:
            try:
                if self.api_type == 'jira' and task.jira_ticket:
                    self._sync_jira_task(task)
                    synced_count += 1
                elif self.api_type == 'github' and task.github_link:
                    self._sync_github_task(task)
                    synced_count += 1
            except Exception as e:
                _logger.error(f'Failed to sync task {task.id}: {str(e)}')
        
        self.last_sync = fields.Datetime.now()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Sync hoàn tất'),
                'message': _('Đã sync %d tasks') % synced_count,
                'type': 'success',
            }
        }

    def _sync_jira_task(self, task):
        """Sync với Jira"""
        # Lấy thông tin từ Jira
        response = self.send_request(f'issue/{task.jira_ticket}')
        
        # Update task từ Jira data
        if response:
            task.write({
                'name': response.get('fields', {}).get('summary', task.name),
                'description': response.get('fields', {}).get('description', task.description),
            })

    def _sync_github_task(self, task):
        """Sync với GitHub"""
        # Parse GitHub link to get owner/repo/issue_number
        # VD: https://github.com/owner/repo/issues/123
        if '/issues/' in task.github_link or '/pull/' in task.github_link:
            parts = task.github_link.split('/')
            issue_num = parts[-1]
            repo = f"{parts[-4]}/{parts[-3]}"
            
            endpoint = f'repos/{repo}/issues/{issue_num}'
            response = self.send_request(endpoint)
            
            if response:
                task.write({
                    'name': response.get('title', task.name),
                })


class TaskAIAssistant(models.Model):
    _name = 'task.ai.assistant'
    _description = 'AI Assistant cho Task'

    name = fields.Char(
        string='Tên AI Model',
        required=True,
        default='OpenAI GPT-4'
    )
    
    ai_provider = fields.Selection([
        ('openai', 'OpenAI'),
        ('claude', 'Claude AI'),
        ('gemini', 'Google Gemini'),
        ('local', 'Local Model'),
    ], string='AI Provider', default='openai')
    
    api_connector_id = fields.Many2one(
        'task.api.connector',
        string='API Connector',
        domain=[('api_type', '=', 'openai')]
    )
    
    model_name = fields.Char(
        string='Model Name',
        default='gpt-4',
        help='VD: gpt-4, gpt-3.5-turbo, claude-3-opus...'
    )
    
    is_active = fields.Boolean(
        string='Kích hoạt',
        default=True
    )

    def analyze_task_risk(self, task):
        """AI phân tích rủi ro task"""
        self.ensure_one()
        
        if not self.api_connector_id:
            return "No AI connector configured"
        
        prompt = f"""
        Phân tích rủi ro cho task sau:
        - Tên: {task.name}
        - Mô tả: {task.description or 'N/A'}
        - Thời gian dự kiến: {task.planned_hours}h
        - Thời gian thực tế: {task.actual_hours}h
        - Số bug: {task.bug_count}
        - Số lần rework: {task.rework_count}
        
        Đánh giá rủi ro và đưa ra gợi ý cải thiện.
        """
        
        try:
            response = self.api_connector_id.send_request(
                'chat/completions',
                method='POST',
                data={
                    'model': self.model_name,
                    'messages': [
                        {'role': 'system', 'content': 'You are a project management AI assistant.'},
                        {'role': 'user', 'content': prompt}
                    ],
                    'max_tokens': 500
                }
            )
            
            ai_response = response.get('choices', [{}])[0].get('message', {}).get('content', '')
            return ai_response
            
        except Exception as e:
            _logger.error(f'AI analysis failed: {str(e)}')
            return f"AI analysis failed: {str(e)}"

    def predict_task_duration(self, task):
        """AI dự đoán thời gian hoàn thành"""
        self.ensure_one()
        
        # Lấy historical data
        similar_tasks = self.env['project.task'].search([
            ('complexity', '=', task.complexity),
            ('actual_hours', '>', 0),
        ], limit=10)
        
        if similar_tasks:
            avg_hours = sum(similar_tasks.mapped('actual_hours')) / len(similar_tasks)
            return avg_hours
        
        return task.planned_hours or 8.0

    def analyze_sentiment(self, text):
        """Phân tích cảm xúc từ text"""
        self.ensure_one()
        
        if not self.api_connector_id:
            return 0.0
        
        try:
            response = self.api_connector_id.send_request(
                'chat/completions',
                method='POST',
                data={
                    'model': self.model_name,
                    'messages': [
                        {
                            'role': 'system',
                            'content': 'Analyze sentiment of text. Reply only with a score from -1 (very negative) to 1 (very positive).'
                        },
                        {'role': 'user', 'content': text}
                    ],
                    'max_tokens': 10
                }
            )
            
            score_text = response.get('choices', [{}])[0].get('message', {}).get('content', '0')
            return float(score_text.strip())
            
        except:
            return 0.0
