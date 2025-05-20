from odoo import models, fields

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    enable_sale_order_limit = fields.Boolean(
        string="Enable Sale Order Limit",
        config_parameter='sale_admin_access.enable_sale_order_limit',
        help="Enable this option to restrict confirmation of sale orders exceeding a certain limit."
    )

    sale_order_limit = fields.Float(
        string="Sale Order Limit",
        config_parameter='sale_admin_access.sale_order_limit',
        help="Maximum amount allowed for confirming sale orders. Orders above this limit will be restricted if enabled."
    )
