# -*- coding: utf-8 -*-

from odoo import models, fields, tools

class TaskAnalyticsReport(models.Model):
    _name = 'task.analytics.report'
    _description = 'Task Analytics Report'
    _auto = False
    _order = 'date desc'

    # Dimensions
    date = fields.Date('Date', readonly=True)
    week = fields.Char('Week', readonly=True)
    month = fields.Char('Month', readonly=True)
    quarter = fields.Char('Quarter', readonly=True)
    year = fields.Char('Year', readonly=True)
    
    project_id = fields.Many2one('project.project', string='Project', readonly=True)
    user_id = fields.Many2one('res.users', string='Assigned To', readonly=True)
    stage_id = fields.Many2one('project.task.type', string='Stage', readonly=True)
    priority = fields.Selection([
        ('0', 'Normal'),
        ('1', 'Low'),
        ('2', 'High'),
        ('3', 'Urgent')
    ], string='Priority', readonly=True)
    
    # Metrics
    task_count = fields.Integer('# Tasks', readonly=True)
    completed_count = fields.Integer('# Completed', readonly=True)
    overdue_count = fields.Integer('# Overdue', readonly=True)
    avg_completion_days = fields.Float('Avg Completion Days', readonly=True)
    total_score = fields.Float('Total Score', readonly=True)
    avg_score = fields.Float('Average Score', readonly=True)
    
    def init(self):
        """Create SQL view for analytics"""
        tools.drop_view_if_exists(self.env.cr, self._table)
        
        # Drop table if exists (for migration)
        self.env.cr.execute(f"DROP TABLE IF EXISTS {self._table} CASCADE")
        
        query = """
            CREATE OR REPLACE VIEW task_analytics_report AS (
                SELECT
                    ROW_NUMBER() OVER (ORDER BY DATE(t.create_date), t.project_id, tu.user_id, t.stage_id, t.priority) AS id,
                    DATE(t.create_date) AS date,
                    TO_CHAR(t.create_date, 'IYYY-IW') AS week,
                    TO_CHAR(t.create_date, 'YYYY-MM') AS month,
                    TO_CHAR(t.create_date, 'YYYY-Q') AS quarter,
                    TO_CHAR(t.create_date, 'YYYY') AS year,
                    t.project_id,
                    tu.user_id,
                    t.stage_id,
                    t.priority,
                    COUNT(DISTINCT t.id) AS task_count,
                    COUNT(DISTINCT CASE WHEN pts.is_closed = true THEN t.id END) AS completed_count,
                    COUNT(DISTINCT CASE WHEN t.date_deadline < CURRENT_DATE AND pts.is_closed = false THEN t.id END) AS overdue_count,
                    AVG(CASE 
                        WHEN pts.is_closed = true AND t.date_deadline IS NOT NULL THEN 
                            EXTRACT(EPOCH FROM (t.date_deadline::timestamp - t.create_date)) / 86400
                        ELSE NULL 
                    END) AS avg_completion_days,
                    SUM(COALESCE(sc.final_score, 0)) AS total_score,
                    AVG(COALESCE(sc.final_score, 0)) AS avg_score
                FROM
                    project_task t
                    LEFT JOIN project_task_user_rel tu ON tu.task_id = t.id
                    LEFT JOIN project_task_type pts ON pts.id = t.stage_id
                    LEFT JOIN task_score_card sc ON sc.task_id = t.id
                GROUP BY
                    DATE(t.create_date),
                    TO_CHAR(t.create_date, 'IYYY-IW'),
                    TO_CHAR(t.create_date, 'YYYY-MM'),
                    TO_CHAR(t.create_date, 'YYYY-Q'),
                    TO_CHAR(t.create_date, 'YYYY'),
                    t.project_id,
                    tu.user_id,
                    t.stage_id,
                    t.priority
            )
        """
        self.env.cr.execute(query)
