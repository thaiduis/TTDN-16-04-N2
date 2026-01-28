# -*- coding: utf-8 -*-
{
    'name': 'Quản lý Dự án Thông minh',
    'version': '15.0.1.0.0',
    'category': 'Project',
    'summary': 'Smart Project Management - Milestone, OKR, Budget Control',
    'description': """
Module Quản lý Dự án Nâng cao
==============================

Tính năng chính
---------------
* Quản lý Milestone (Các giai đoạn dự án)
* Thiết lập OKR (Objective & Key Results)
* Real-time Budget Tracking (Theo dõi ngân sách)
* Smart Dependency Management (Quản lý phụ thuộc thông minh)
* Resource Allocation (Phân bổ nguồn lực từ HR)
* Risk Alert Dashboard (Cảnh báo rủi ro)

Tích hợp
--------
* Liên kết với quan_ly_cong_viec (Task Execution)
* Liên kết với quan_ly_nhan_su (HR Resources)
* Tự động tính chi phí từ Timesheet
    """,
    'author': 'Văn Bảo',
    'website': 'https://www.yourcompany.com',
    'depends': [
        'base',
        'project',
        'hr',
        'mail',
        'quan_ly_cong_viec',
        'quan_ly_nhan_su',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/project_project_views.xml',
        'views/project_milestone_views.xml',
        'views/project_okr_views.xml',
        'views/project_hr_integration_views.xml',  # Re-enabled
        'views/menu_views.xml',
    ],
    'demo': [],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
