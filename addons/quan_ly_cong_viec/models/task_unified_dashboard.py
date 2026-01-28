# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import json
from datetime import datetime, timedelta

class TaskUnifiedDashboard(models.Model):
    _name = 'task.unified.dashboard'
    _description = 'Unified Task Dashboard'

    name = fields.Char('Dashboard Name', default='Task Dashboard', required=True)
    
    # Date Range
    date_from = fields.Date('Date From', default=lambda self: fields.Date.today() - timedelta(days=30))
    date_to = fields.Date('Date To', default=fields.Date.today)
    
    # User/Team Filter
    user_ids = fields.Many2many('res.users', string='Users')
    project_ids = fields.Many2many('project.project', string='Projects')
    
    # KPI Cards
    total_tasks = fields.Integer('Total Tasks', compute='_compute_kpis', store=False)
    tasks_completed = fields.Integer('Completed Tasks', compute='_compute_kpis', store=False)
    tasks_in_progress = fields.Integer('In Progress', compute='_compute_kpis', store=False)
    tasks_overdue = fields.Integer('Overdue Tasks', compute='_compute_kpis', store=False)
    
    completion_rate = fields.Float('Completion Rate (%)', compute='_compute_kpis', store=False)
    avg_completion_time = fields.Float('Avg Completion Time (days)', compute='_compute_kpis', store=False)
    avg_score = fields.Float('Average Score', compute='_compute_kpis', store=False)
    
    # Charts Data (JSON)
    tasks_by_stage_chart = fields.Text('Tasks by Stage Chart', compute='_compute_charts', store=False)
    tasks_by_priority_chart = fields.Text('Tasks by Priority Chart', compute='_compute_charts', store=False)
    completion_trend_chart = fields.Text('Completion Trend Chart', compute='_compute_charts', store=False)
    team_performance_chart = fields.Text('Team Performance Chart', compute='_compute_charts', store=False)
    
    # Top Performers
    top_performers_data = fields.Text('Top Performers', compute='_compute_top_performers', store=False)
    
    @api.depends('date_from', 'date_to', 'user_ids', 'project_ids')
    def _compute_kpis(self):
        for record in self:
            domain = record._get_base_domain()
            
            tasks = self.env['project.task'].search(domain)
            
            record.total_tasks = len(tasks)
            record.tasks_completed = len(tasks.filtered(lambda t: t.stage_id.is_closed))
            record.tasks_in_progress = len(tasks.filtered(lambda t: not t.stage_id.is_closed and not t.stage_id.fold))
            
            # Overdue tasks
            today = fields.Date.today()
            record.tasks_overdue = len(tasks.filtered(lambda t: t.date_deadline and t.date_deadline < today and not t.stage_id.is_closed))
            
            # Completion rate
            if record.total_tasks > 0:
                record.completion_rate = (record.tasks_completed / record.total_tasks) * 100
            else:
                record.completion_rate = 0.0
            
            # Average completion time
            completed_tasks = tasks.filtered(lambda t: t.stage_id.is_closed and t.date_deadline and t.create_date)
            if completed_tasks:
                total_days = 0
                count = 0
                for task in completed_tasks:
                    if task.date_deadline and task.create_date:
                        create_date = task.create_date.date()
                        days = (task.date_deadline - create_date).days
                        if days >= 0:
                            total_days += days
                            count += 1
                record.avg_completion_time = total_days / count if count > 0 else 0
            else:
                record.avg_completion_time = 0.0
            
            # Average score (from task_score_card)
            ScoreCard = self.env['task.score.card']
            score_domain = [('task_id', 'in', tasks.ids)]
            scores = ScoreCard.search(score_domain)
            if scores:
                record.avg_score = sum(scores.mapped('final_score')) / len(scores)
            else:
                record.avg_score = 0.0
    
    @api.depends('date_from', 'date_to', 'user_ids', 'project_ids')
    def _compute_charts(self):
        for record in self:
            domain = record._get_base_domain()
            tasks = self.env['project.task'].search(domain)
            
            # Tasks by Stage
            stages_data = {}
            for task in tasks:
                stage_name = task.stage_id.name if task.stage_id else 'No Stage'
                stages_data[stage_name] = stages_data.get(stage_name, 0) + 1
            
            record.tasks_by_stage_chart = json.dumps({
                'labels': list(stages_data.keys()),
                'data': list(stages_data.values()),
                'type': 'pie'
            })
            
            # Tasks by Priority
            priority_map = {'0': 'Normal', '1': 'Low', '2': 'High', '3': 'Urgent'}
            priority_data = {'Normal': 0, 'Low': 0, 'High': 0, 'Urgent': 0}
            for task in tasks:
                priority_name = priority_map.get(task.priority, 'Normal')
                priority_data[priority_name] += 1
            
            record.tasks_by_priority_chart = json.dumps({
                'labels': list(priority_data.keys()),
                'data': list(priority_data.values()),
                'type': 'bar'
            })
            
            # Completion Trend (last 7 days)
            trend_data = record._get_completion_trend_data()
            record.completion_trend_chart = json.dumps(trend_data)
            
            # Team Performance
            team_data = record._get_team_performance_data()
            record.team_performance_chart = json.dumps(team_data)
    
    @api.depends('date_from', 'date_to', 'user_ids', 'project_ids')
    def _compute_top_performers(self):
        for record in self:
            domain = record._get_base_domain()
            tasks = self.env['project.task'].search(domain)
            
            # Count completed tasks per user
            user_stats = {}
            for task in tasks:
                for user in task.user_ids:
                    if user.id not in user_stats:
                        user_stats[user.id] = {
                            'name': user.name,
                            'total': 0,
                            'completed': 0,
                        }
                    user_stats[user.id]['total'] += 1
                    if task.stage_id.is_closed:
                        user_stats[user.id]['completed'] += 1
            
            # Sort by completed tasks
            sorted_users = sorted(user_stats.values(), key=lambda x: x['completed'], reverse=True)[:5]
            
            record.top_performers_data = json.dumps(sorted_users)
    
    def _get_base_domain(self):
        """Get base domain for filtering tasks"""
        domain = []
        
        if self.date_from:
            domain.append(('create_date', '>=', self.date_from))
        if self.date_to:
            domain.append(('create_date', '<=', self.date_to))
        if self.user_ids:
            domain.append(('user_ids', 'in', self.user_ids.ids))
        if self.project_ids:
            domain.append(('project_id', 'in', self.project_ids.ids))
        
        return domain
    
    def _get_completion_trend_data(self):
        """Get completion trend for last 7 days"""
        trend_labels = []
        trend_data = []
        
        for i in range(6, -1, -1):
            date = fields.Date.today() - timedelta(days=i)
            trend_labels.append(date.strftime('%m/%d'))
            
            # Count tasks completed on this date
            domain = [
                ('stage_id.is_closed', '=', True),
                ('write_date', '>=', datetime.combine(date, datetime.min.time())),
                ('write_date', '<=', datetime.combine(date, datetime.max.time())),
            ]
            
            if self.user_ids:
                domain.append(('user_ids', 'in', self.user_ids.ids))
            if self.project_ids:
                domain.append(('project_id', 'in', self.project_ids.ids))
            
            count = self.env['project.task'].search_count(domain)
            trend_data.append(count)
        
        return {
            'labels': trend_labels,
            'data': trend_data,
            'type': 'line'
        }
    
    def _get_team_performance_data(self):
        """Get team performance comparison"""
        domain = self._get_base_domain()
        tasks = self.env['project.task'].search(domain)
        
        team_stats = {}
        for task in tasks:
            for user in task.user_ids:
                if user.id not in team_stats:
                    team_stats[user.id] = {
                        'name': user.name,
                        'completed': 0,
                        'in_progress': 0,
                    }
                
                if task.stage_id.is_closed:
                    team_stats[user.id]['completed'] += 1
                else:
                    team_stats[user.id]['in_progress'] += 1
        
        # Prepare chart data
        labels = [stat['name'] for stat in team_stats.values()]
        completed = [stat['completed'] for stat in team_stats.values()]
        in_progress = [stat['in_progress'] for stat in team_stats.values()]
        
        return {
            'labels': labels,
            'datasets': [
                {'label': 'Completed', 'data': completed},
                {'label': 'In Progress', 'data': in_progress},
            ],
            'type': 'bar'
        }
    
    def action_refresh_dashboard(self):
        """Refresh dashboard data"""
        self.ensure_one()
        # Recompute all computed fields
        self._compute_kpis()
        self._compute_charts()
        self._compute_top_performers()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Dashboard refreshed successfully'),
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_view_all_tasks(self):
        """View all tasks in current filter"""
        self.ensure_one()
        domain = self._get_base_domain()
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('All Tasks'),
            'res_model': 'project.task',
            'view_mode': 'tree,form',
            'domain': domain,
        }
    
    def action_view_overdue_tasks(self):
        """View overdue tasks"""
        self.ensure_one()
        domain = self._get_base_domain()
        domain.append(('date_deadline', '<', fields.Date.today()))
        domain.append(('stage_id.is_closed', '=', False))
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Overdue Tasks'),
            'res_model': 'project.task',
            'view_mode': 'tree,form',
            'domain': domain,
        }
