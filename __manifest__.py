{
    'name': 'Sale Admin Access Customization',
    'version': '17.0.1.0.0',
    'category': 'Sales',
    'summary': "Enhanced Administrative Access for Sales Module",
    'description': """
    This module provides elevated administrative access rights for users managing the Sales module in Odoo.
    It enables advanced control over sales operations, including configuration, pricing, and reporting features,
    ensuring sales administrators can perform their tasks with greater efficiency and authority.
    """,
    'author': '',
    'company': '',
    'maintainer': '',
    'website': "",
    'depends': ['sale_management'],
    'data': [
        'security/res_groups.xml',
        'views/sale_order.xml',
        'views/res_config_settings.xml'
    ],
    'images': '',
    'license': 'LGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False,
}