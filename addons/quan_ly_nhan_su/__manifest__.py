# -*- coding: utf-8 -*-
{
    'name': "Quản lý Nhân sự Nâng cao",

    'summary': """
        Quản lý nhân sự với tính năng Quản lý Năng lực, Kỹ năng và Hiệu suất làm việc""",

    'description': """
        Module quản lý nhân sự nâng cao bao gồm:
        - Quản lý hồ sơ nhân viên
        - Quản lý kỹ năng và năng lực
        - Đo lường tải công việc (workload)
        - Theo dõi lịch sử hiệu suất
        - Tích hợp với module Quản lý Dự án
    """,

    'author': "Smart HR Team",
    'website': "http://www.yourcompany.com",

    'category': 'Human Resources',
    'version': '2.0.0',

    # any module necessary for this one to work correctly
    'depends': ['base', 'mail', 'hr', 'hr_skills', 'project'],

    # always loaded
    'data': [
        'data/sequence_data.xml',
        'security/ir.model.access.csv',
        'wizard/tao_cham_cong_wizard.xml',
        'views/ky_nang.xml',
        'views/nhan_vien.xml',
        'views/phong_ban.xml',
        'views/cham_cong.xml',
        'views/bang_luong.xml',
        'views/hr_id_ocr_connector_views.xml',
        'views/id_ocr_log_views.xml',
        'views/hr_integration_views.xml',  # Re-enabled
        'views/menu.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
