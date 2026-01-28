# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import requests
import json
from datetime import datetime

class TaskGitIntegration(models.Model):
    _name = 'task.git.integration'
    _description = 'Git Repository Integration'
    _order = 'create_date desc'

    name = fields.Char('Repository Name', required=True, help='Format: owner/repo (e.g., thaiduis/my-project)')
    platform = fields.Selection([
        ('github', 'GitHub'),
        ('gitlab', 'GitLab'),
    ], string='Platform', default='github', required=True)
    
    api_token = fields.Char('API Token', required=True, help='Personal Access Token for API authentication')
    repository_url = fields.Char('Repository URL', compute='_compute_repository_url', store=True)
    
    # Sync Settings
    auto_sync = fields.Boolean('Auto Sync', default=False, help='Automatically sync every 30 minutes')
    last_sync_date = fields.Datetime('Last Sync', readonly=True)
    sync_interval = fields.Integer('Sync Interval (minutes)', default=30)
    
    # Statistics
    total_commits = fields.Integer('Total Commits', readonly=True)
    total_branches = fields.Integer('Total Branches', readonly=True)
    total_prs = fields.Integer('Total Pull Requests', readonly=True)
    total_issues = fields.Integer('Total Issues', readonly=True)
    
    # Relations
    commit_ids = fields.One2many('task.git.commit', 'integration_id', string='Commits')
    branch_ids = fields.One2many('task.git.branch', 'integration_id', string='Branches')
    pr_ids = fields.One2many('task.git.pullrequest', 'integration_id', string='Pull Requests')
    issue_ids = fields.One2many('task.git.issue', 'integration_id', string='Issues')
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('connected', 'Connected'),
        ('error', 'Error'),
    ], string='State', default='draft', readonly=True)
    
    error_message = fields.Text('Error Message', readonly=True)
    
    @api.depends('platform', 'name')
    def _compute_repository_url(self):
        for record in self:
            if record.platform == 'github':
                record.repository_url = f'https://github.com/{record.name}'
            elif record.platform == 'gitlab':
                record.repository_url = f'https://gitlab.com/{record.name}'
            else:
                record.repository_url = ''
    
    @api.constrains('name')
    def _check_repository_name(self):
        for record in self:
            if record.name and '/' not in record.name:
                raise ValidationError(_('Repository name must be in format: owner/repo (e.g., thaiduis/my-project)'))
    
    def _get_api_headers(self):
        """Get API headers for authentication"""
        self.ensure_one()
        if self.platform == 'github':
            return {
                'Authorization': f'token {self.api_token}',
                'Accept': 'application/vnd.github.v3+json'
            }
        elif self.platform == 'gitlab':
            return {
                'PRIVATE-TOKEN': self.api_token
            }
        return {}
    
    def _get_api_url(self, endpoint=''):
        """Get API URL for the platform"""
        self.ensure_one()
        if self.platform == 'github':
            base_url = 'https://api.github.com'
            return f'{base_url}/repos/{self.name}{endpoint}'
        elif self.platform == 'gitlab':
            # GitLab needs URL encoding for project path
            import urllib.parse
            project_path = urllib.parse.quote(self.name, safe='')
            base_url = 'https://gitlab.com/api/v4'
            return f'{base_url}/projects/{project_path}{endpoint}'
        return ''
    
    def action_test_connection(self):
        """Test connection to Git platform"""
        self.ensure_one()
        try:
            url = self._get_api_url()
            headers = self._get_api_headers()
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                self.write({
                    'state': 'connected',
                    'error_message': False
                })
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Success'),
                        'message': _('Successfully connected to %s') % self.platform.upper(),
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                error_msg = f'Connection failed: {response.status_code} - {response.text}'
                self.write({
                    'state': 'error',
                    'error_message': error_msg
                })
                raise UserError(error_msg)
                
        except Exception as e:
            error_msg = str(e)
            self.write({
                'state': 'error',
                'error_message': error_msg
            })
            raise UserError(_('Connection failed: %s') % error_msg)
    
    def action_sync_all(self):
        """Sync all data from repository"""
        self.ensure_one()
        try:
            self.action_sync_commits()
            self.action_sync_branches()
            self.action_sync_pull_requests()
            self.action_sync_issues()
            
            self.write({
                'last_sync_date': fields.Datetime.now(),
                'state': 'connected',
                'error_message': False
            })
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Sync completed successfully'),
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            self.write({
                'state': 'error',
                'error_message': str(e)
            })
            raise UserError(_('Sync failed: %s') % str(e))
    
    def action_sync_commits(self):
        """Sync commits from repository"""
        self.ensure_one()
        try:
            if self.platform == 'github':
                url = self._get_api_url('/commits')
            else:  # gitlab
                url = self._get_api_url('/repository/commits')
            
            headers = self._get_api_headers()
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code != 200:
                raise UserError(_('Failed to fetch commits: %s') % response.text)
            
            commits_data = response.json()
            
            # Clear existing commits
            self.commit_ids.unlink()
            
            # Create new commits
            Commit = self.env['task.git.commit']
            for commit_data in commits_data[:50]:  # Limit to 50 most recent
                if self.platform == 'github':
                    commit_info = commit_data.get('commit', {})
                    author_info = commit_info.get('author', {})
                    commit_date = self._parse_datetime(author_info.get('date', ''))
                    
                    Commit.create({
                        'integration_id': self.id,
                        'sha': commit_data.get('sha', ''),
                        'message': commit_info.get('message', ''),
                        'author_name': author_info.get('name', ''),
                        'author_email': author_info.get('email', ''),
                        'commit_date': commit_date,
                        'url': commit_data.get('html_url', ''),
                    })
                else:  # gitlab
                    commit_date = self._parse_datetime(commit_data.get('created_at', ''))
                    
                    Commit.create({
                        'integration_id': self.id,
                        'sha': commit_data.get('id', ''),
                        'message': commit_data.get('message', ''),
                        'author_name': commit_data.get('author_name', ''),
                        'author_email': commit_data.get('author_email', ''),
                        'commit_date': commit_date,
                        'url': commit_data.get('web_url', ''),
                    })
            
            self.total_commits = len(self.commit_ids)
            
        except Exception as e:
            raise UserError(_('Failed to sync commits: %s') % str(e))
    
    def _parse_datetime(self, date_str):
        """Parse datetime string from Git API to Odoo datetime format
        
        Handles formats like:
        - GitHub: 2026-01-13T15:44:27Z
        - GitLab: 2026-01-13T15:44:27.000+00:00
        
        Returns naive datetime (without timezone) for Odoo
        """
        if not date_str:
            return False
        
        try:
            # Remove 'Z', replace 'T' with space, remove timezone and microseconds
            date_str_clean = date_str.replace('Z', '').replace('T', ' ').split('+')[0].split('.')[0]
            # Parse to datetime object (naive)
            dt = datetime.strptime(date_str_clean, '%Y-%m-%d %H:%M:%S')
            return dt
        except:
            return False
    
    def action_sync_branches(self):
        """Sync branches from repository"""
        self.ensure_one()
        try:
            if self.platform == 'github':
                url = self._get_api_url('/branches')
            else:  # gitlab
                url = self._get_api_url('/repository/branches')
            
            headers = self._get_api_headers()
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code != 200:
                raise UserError(_('Failed to fetch branches: %s') % response.text)
            
            branches_data = response.json()
            
            # Clear existing branches
            self.branch_ids.unlink()
            
            # Create new branches
            Branch = self.env['task.git.branch']
            for branch_data in branches_data:
                Branch.create({
                    'integration_id': self.id,
                    'name': branch_data.get('name', ''),
                    'protected': branch_data.get('protected', False),
                })
            
            self.total_branches = len(self.branch_ids)
            
        except Exception as e:
            raise UserError(_('Failed to sync branches: %s') % str(e))
    
    def action_sync_pull_requests(self):
        """Sync pull requests from repository"""
        self.ensure_one()
        try:
            if self.platform == 'github':
                url = self._get_api_url('/pulls')
            else:  # gitlab
                url = self._get_api_url('/merge_requests')
            
            headers = self._get_api_headers()
            response = requests.get(url, headers=headers, params={'state': 'all'}, timeout=30)
            
            if response.status_code != 200:
                raise UserError(_('Failed to fetch pull requests: %s') % response.text)
            
            prs_data = response.json()
            
            # Clear existing PRs
            self.pr_ids.unlink()
            
            # Create new PRs
            PR = self.env['task.git.pullrequest']
            for pr_data in prs_data[:50]:  # Limit to 50
                if self.platform == 'github':
                    created_at = self._parse_datetime(pr_data.get('created_at', ''))
                    updated_at = self._parse_datetime(pr_data.get('updated_at', ''))
                    
                    PR.create({
                        'integration_id': self.id,
                        'number': pr_data.get('number', 0),
                        'title': pr_data.get('title', ''),
                        'state': pr_data.get('state', 'open'),
                        'author': pr_data.get('user', {}).get('login', ''),
                        'created_at': created_at,
                        'updated_at': updated_at,
                        'url': pr_data.get('html_url', ''),
                    })
                else:  # gitlab
                    created_at = self._parse_datetime(pr_data.get('created_at', ''))
                    updated_at = self._parse_datetime(pr_data.get('updated_at', ''))
                    
                    PR.create({
                        'integration_id': self.id,
                        'number': pr_data.get('iid', 0),
                        'title': pr_data.get('title', ''),
                        'state': pr_data.get('state', 'opened'),
                        'author': pr_data.get('author', {}).get('username', ''),
                        'created_at': created_at,
                        'updated_at': updated_at,
                        'url': pr_data.get('web_url', ''),
                    })
            
            self.total_prs = len(self.pr_ids)
            
        except Exception as e:
            raise UserError(_('Failed to sync pull requests: %s') % str(e))
    
    def action_sync_issues(self):
        """Sync issues from repository"""
        self.ensure_one()
        try:
            url = self._get_api_url('/issues')
            headers = self._get_api_headers()
            response = requests.get(url, headers=headers, params={'state': 'all'}, timeout=30)
            
            if response.status_code != 200:
                raise UserError(_('Failed to fetch issues: %s') % response.text)
            
            issues_data = response.json()
            
            # Clear existing issues
            self.issue_ids.unlink()
            
            # Create new issues
            Issue = self.env['task.git.issue']
            for issue_data in issues_data[:50]:  # Limit to 50
                # Skip pull requests (GitHub includes PRs in issues endpoint)
                if self.platform == 'github' and 'pull_request' in issue_data:
                    continue
                
                created_at = self._parse_datetime(issue_data.get('created_at', ''))
                updated_at = self._parse_datetime(issue_data.get('updated_at', ''))
                
                if self.platform == 'github':
                    author = issue_data.get('user', {}).get('login', '')
                else:  # gitlab
                    author = issue_data.get('author', {}).get('username', '')
                
                Issue.create({
                    'integration_id': self.id,
                    'number': issue_data.get('number') if self.platform == 'github' else issue_data.get('iid', 0),
                    'title': issue_data.get('title', ''),
                    'state': issue_data.get('state', 'open'),
                    'author': author,
                    'created_at': created_at,
                    'updated_at': updated_at,
                    'url': issue_data.get('html_url') if self.platform == 'github' else issue_data.get('web_url', ''),
                })
            
            self.total_issues = len(self.issue_ids)
            
        except Exception as e:
            raise UserError(_('Failed to sync issues: %s') % str(e))


class TaskGitCommit(models.Model):
    _name = 'task.git.commit'
    _description = 'Git Commit'
    _order = 'commit_date desc'

    integration_id = fields.Many2one('task.git.integration', string='Integration', required=True, ondelete='cascade')
    sha = fields.Char('SHA', required=True)
    message = fields.Text('Message')
    author_name = fields.Char('Author Name')
    author_email = fields.Char('Author Email')
    commit_date = fields.Datetime('Commit Date')
    url = fields.Char('URL')
    
    _sql_constraints = [
        ('sha_unique', 'unique(integration_id, sha)', 'Commit SHA must be unique per integration!')
    ]


class TaskGitBranch(models.Model):
    _name = 'task.git.branch'
    _description = 'Git Branch'
    _order = 'name'

    integration_id = fields.Many2one('task.git.integration', string='Integration', required=True, ondelete='cascade')
    name = fields.Char('Branch Name', required=True)
    protected = fields.Boolean('Protected')
    
    _sql_constraints = [
        ('name_unique', 'unique(integration_id, name)', 'Branch name must be unique per integration!')
    ]


class TaskGitPullRequest(models.Model):
    _name = 'task.git.pullrequest'
    _description = 'Git Pull Request'
    _order = 'number desc'

    integration_id = fields.Many2one('task.git.integration', string='Integration', required=True, ondelete='cascade')
    number = fields.Integer('PR Number', required=True)
    title = fields.Char('Title')
    state = fields.Char('State')
    author = fields.Char('Author')
    created_at = fields.Datetime('Created At')
    updated_at = fields.Datetime('Updated At')
    url = fields.Char('URL')
    
    _sql_constraints = [
        ('number_unique', 'unique(integration_id, number)', 'PR number must be unique per integration!')
    ]


class TaskGitIssue(models.Model):
    _name = 'task.git.issue'
    _description = 'Git Issue'
    _order = 'number desc'

    integration_id = fields.Many2one('task.git.integration', string='Integration', required=True, ondelete='cascade')
    number = fields.Integer('Issue Number', required=True)
    title = fields.Char('Title')
    state = fields.Char('State')
    author = fields.Char('Author')
    created_at = fields.Datetime('Created At')
    updated_at = fields.Datetime('Updated At')
    url = fields.Char('URL')
    
    _sql_constraints = [
        ('number_unique', 'unique(integration_id, number)', 'Issue number must be unique per integration!')
    ]
