# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import requests
import json

class TaskAIAssistant(models.Model):
    _name = 'task.ai.assistant'
    _description = 'AI Assistant for Task Management'

    name = fields.Char('Name', default='AI Assistant', readonly=True)
    
    # OpenAI Settings
    api_key = fields.Char('OpenAI API Key', required=True, help='Your OpenAI API Key')
    model = fields.Selection([
        ('gpt-3.5-turbo', 'GPT-3.5 Turbo'),
        ('gpt-4', 'GPT-4'),
        ('gpt-4-turbo', 'GPT-4 Turbo'),
    ], string='Model', default='gpt-3.5-turbo', required=True)
    
    temperature = fields.Float('Temperature', default=0.7, help='Controls randomness (0-1)')
    max_tokens = fields.Integer('Max Tokens', default=1000, help='Maximum response length')
    
    # Statistics
    total_requests = fields.Integer('Total Requests', readonly=True, default=0)
    successful_requests = fields.Integer('Successful Requests', readonly=True, default=0)
    failed_requests = fields.Integer('Failed Requests', readonly=True, default=0)
    
    active = fields.Boolean('Active', default=True)
    
    def _call_openai_api(self, messages, temperature=None, max_tokens=None):
        """Call OpenAI API with given messages"""
        self.ensure_one()
        
        if not self.api_key:
            raise UserError(_('OpenAI API Key is not configured'))
        
        url = 'https://api.openai.com/v1/chat/completions'
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        data = {
            'model': self.model,
            'messages': messages,
            'temperature': temperature or self.temperature,
            'max_tokens': max_tokens or self.max_tokens,
        }
        
        try:
            self.total_requests += 1
            response = requests.post(url, headers=headers, json=data, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                self.successful_requests += 1
                return result['choices'][0]['message']['content']
            else:
                self.failed_requests += 1
                error_msg = response.json().get('error', {}).get('message', response.text)
                raise UserError(_('OpenAI API Error: %s') % error_msg)
                
        except requests.exceptions.Timeout:
            self.failed_requests += 1
            raise UserError(_('OpenAI API request timed out'))
        except requests.exceptions.RequestException as e:
            self.failed_requests += 1
            raise UserError(_('OpenAI API request failed: %s') % str(e))
    
    def action_chat(self):
        """Open chat interface with AI"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Chat with AI Assistant'),
            'res_model': 'task.ai.chat.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_assistant_id': self.id}
        }
    
    def suggest_task_breakdown(self, task_id):
        """Suggest how to break down a task into subtasks"""
        self.ensure_one()
        task = self.env['project.task'].browse(task_id)
        
        if not task.exists():
            raise UserError(_('Task not found'))
        
        prompt = f"""You are a project management expert. Given the following task, suggest how to break it down into smaller, actionable subtasks.

Task Name: {task.name}
Description: {task.description or 'No description'}
Priority: {task.priority}

Please provide 3-5 subtasks with clear, actionable titles. Format each subtask as:
- [Subtask Title]: [Brief description]

Be specific and practical."""
        
        messages = [
            {'role': 'system', 'content': 'You are a helpful project management assistant.'},
            {'role': 'user', 'content': prompt}
        ]
        
        response = self._call_openai_api(messages)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('AI Suggestions'),
                'message': response,
                'type': 'info',
                'sticky': True,
            }
        }
    
    def analyze_task_progress(self, task_id):
        """Analyze task progress and provide insights"""
        self.ensure_one()
        task = self.env['project.task'].browse(task_id)
        
        if not task.exists():
            raise UserError(_('Task not found'))
        
        # Gather task data
        task_data = {
            'name': task.name,
            'stage': task.stage_id.name if task.stage_id else 'N/A',
            'priority': task.priority,
            'assigned_to': task.user_ids.mapped('name'),
            'deadline': str(task.date_deadline) if task.date_deadline else 'No deadline',
            'subtasks_total': len(task.child_ids),
            'subtasks_done': len(task.child_ids.filtered(lambda t: t.stage_id.is_closed)),
        }
        
        prompt = f"""Analyze this task and provide insights on its progress:

Task: {task_data['name']}
Stage: {task_data['stage']}
Priority: {task_data['priority']}
Assigned to: {', '.join(task_data['assigned_to']) if task_data['assigned_to'] else 'Unassigned'}
Deadline: {task_data['deadline']}
Subtasks: {task_data['subtasks_done']}/{task_data['subtasks_total']} completed

Please provide:
1. Progress assessment (on track, at risk, delayed)
2. Key concerns or blockers
3. Actionable recommendations

Be concise and practical."""
        
        messages = [
            {'role': 'system', 'content': 'You are a project management expert analyzing task progress.'},
            {'role': 'user', 'content': prompt}
        ]
        
        response = self._call_openai_api(messages)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Progress Analysis'),
                'message': response,
                'type': 'info',
                'sticky': True,
            }
        }
    
    def smart_task_search(self, query):
        """Intelligent task search using AI to understand intent"""
        self.ensure_one()
        
        # Get all tasks
        tasks = self.env['project.task'].search([])
        
        # Create task summary for AI
        task_list = []
        for task in tasks[:50]:  # Limit to 50 for token efficiency
            task_list.append({
                'id': task.id,
                'name': task.name,
                'description': task.description or '',
                'stage': task.stage_id.name if task.stage_id else '',
                'priority': task.priority,
            })
        
        prompt = f"""Given this search query: "{query}"

Find the most relevant tasks from this list:
{json.dumps(task_list, indent=2, ensure_ascii=False)}

Return only the IDs of the 5 most relevant tasks as a JSON array, e.g., [1, 5, 12, 23, 45]"""
        
        messages = [
            {'role': 'system', 'content': 'You are a smart search assistant. Understand user intent and find relevant items.'},
            {'role': 'user', 'content': prompt}
        ]
        
        response = self._call_openai_api(messages, temperature=0.3)
        
        try:
            # Parse task IDs from response
            task_ids = json.loads(response)
            
            return {
                'type': 'ir.actions.act_window',
                'name': _('Search Results: %s') % query,
                'res_model': 'project.task',
                'view_mode': 'tree,form',
                'domain': [('id', 'in', task_ids)],
            }
        except:
            raise UserError(_('Failed to parse AI response: %s') % response)
    
    def generate_task_report_summary(self, task_ids):
        """Generate a summary report for multiple tasks"""
        self.ensure_one()
        
        tasks = self.env['project.task'].browse(task_ids)
        
        if not tasks:
            raise UserError(_('No tasks selected'))
        
        # Gather tasks data
        tasks_data = []
        for task in tasks:
            tasks_data.append({
                'name': task.name,
                'stage': task.stage_id.name if task.stage_id else 'N/A',
                'priority': task.priority,
                'assigned': task.user_ids.mapped('name'),
            })
        
        prompt = f"""Create a concise executive summary for these {len(tasks)} tasks:

{json.dumps(tasks_data, indent=2, ensure_ascii=False)}

Include:
1. Overall status overview
2. Key highlights
3. Potential risks
4. Recommendations

Keep it professional and actionable."""
        
        messages = [
            {'role': 'system', 'content': 'You are a project manager writing executive summaries.'},
            {'role': 'user', 'content': prompt}
        ]
        
        response = self._call_openai_api(messages, max_tokens=1500)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Tasks Summary Report'),
                'message': response,
                'type': 'info',
                'sticky': True,
            }
        }


class TaskAIChatWizard(models.TransientModel):
    _name = 'task.ai.chat.wizard'
    _description = 'AI Chat Wizard'

    assistant_id = fields.Many2one('task.ai.assistant', string='Assistant', required=True)
    user_message = fields.Text('Your Message', required=True)
    ai_response = fields.Text('AI Response', readonly=True)
    
    def action_send_message(self):
        """Send message to AI and get response"""
        self.ensure_one()
        
        messages = [
            {'role': 'system', 'content': 'You are a helpful assistant for task and project management in Odoo.'},
            {'role': 'user', 'content': self.user_message}
        ]
        
        response = self.assistant_id._call_openai_api(messages)
        self.ai_response = response
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
