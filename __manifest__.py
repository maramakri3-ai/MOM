{
    'name': 'Meeting Minutes (MOM)',
    'version': '17.0.1.0.0',
    'category': 'Project',
    'summary': 'Manage Meeting Minutes and Action Plans',
    'description': """
        Memorandum of Meeting Management System
        - Create and manage meeting minutes
        - Track action plans
        - Approval workflow
        - Follow-up activities
    """,
    'depends': [
        'base', 
        'mail', 
        'hr', 
        # 'board',  # Temporarily disabled
    ],
    'data': [
        'security/mom_security.xml',
        'security/ir.model.access.csv',
        'data/ir.sequence.data.xml',  # Add sequence data
        'data/mail_activity_data.xml',  # Add activity types
        'data/ir_cron_data.xml',  # Add cron data
        'data/mom_stages.xml',
        'views/mom_views.xml',
        'views/mom_action_plan_views.xml',
        'views/mom_stage_views.xml',  # Add this line
        'views/mom_meeting_type_views.xml',  # Add this line
        # 'views/mom_dashboard_views.xml',  # Temporarily disabled
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
    'web_icon': "MOM,static/description/icon.png",
    'assets': {
        'web.assets_backend': [
            '/MOM/static/src/css/mom_styles.css',
        ],
    },
}
