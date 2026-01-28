# -*- coding: utf-8 -*-
{
    'name': 'Quản lý Công việc Thông minh',
    'version': '15.0.1.0.0',
    'category': 'Project',
    'summary': 'Smart Task Execution với AI Report & Scoring',
    'description': """
Module Quản lý Công việc Nâng cao
==================================

Tính năng chính
---------------
* Báo cáo tiến độ thông minh (Smart Report)
* AI phân tích cảm xúc & phát hiện rủi ro
* Chấm điểm tự động (Auto Scoring)
* Tích hợp HR: Skill Gap Warning
* Tích hợp Project: Real-time Job Costing
* Dashboard thông minh cho PM và Nhân viên
* Gamification Profile

Technical Highlights
--------------------
* Kế thừa project.task của Odoo
* Model mới: task.smart.report (Lưu lịch sử báo cáo)
* Model mới: task.score.card (Phiếu điểm)
* API tích hợp AI (Sentiment Analysis - Placeholder)
    """,
    'author': 'Văn Bảo',
    'website': 'https://www.yourcompany.com',
    'depends': [
        'base',
        'project',
        'hr',
        'hr_skills',
        'mail',
        'quan_ly_nhan_su',
    ],
    'external_dependencies': {
        'python': ['requests'],
    },
    'data': [
        'security/ir.model.access.csv',
        # Load actions first before using them
        'views/task_checklist_views.xml',
        'views/task_smart_report_views.xml',
        'views/task_score_card_views.xml',
        'views/task_api_connector_views.xml',
        # Then load views that reference those actions
        'views/project_task_views.xml',
        'views/task_hr_integration_views.xml',  # Re-enabled for HR integration
        'views/menu_views.xml',
        # Load access rules for new models after all models are created
        'security/new_models_access.xml',
    ],
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
