# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, fields
from odoo.exceptions import UserError

class SaleOrder(models.Model):
    _inherit = ['sale.order']

    manager_reference = fields.Text(
        string="Manager Reference",
        help="Additional notes or reference provided by the manager related to the sale order or approval process."
    )

    is_sale_admin = fields.Boolean(
        string="Is Sale Admin",
        compute="_compute_is_sale_admin",
        store=False,
        help="Determines if the current user has Sale Admin access. Used during form view rendering; not stored in the database."
    )

    is_check_sale_admin = fields.Boolean(
        string="Is Check Sale Admin",
        help="Used to check Sale Admin status in views when 'is_sale_admin' is not stored in the database."
    )

    is_auto_workflow = fields.Boolean(
        string="Auto Workflow",
        help="Enable this to allow sale orders to follow a predefined automated workflow without manual confirmation."
    )

    def _compute_is_sale_admin(self):
        """
        Compute whether the current user is a Sale Admin.

        This method checks if the current user belongs to the group
        'sale_admin_access.group_sale_admin_access'. If the user is
        part of the group, both 'is_check_sale_admin' and
        'is_sale_admin' fields are set to True. Otherwise, they are set to False.

        Note:
            - 'is_sale_admin' is a computed field (not stored).
            - 'is_check_sale_admin' is used where a stored value is needed
              for evaluation in views or logic.
        """
        for record in self:
            if self.env.user.has_group('sale_admin_access.group_sale_admin_access'):
                record.is_check_sale_admin = True
                record.is_sale_admin = True
            else:
                record.is_check_sale_admin = False
                record.is_sale_admin = False

    def action_confirm(self):
        """
        Overrides the default `action_confirm` method to introduce custom logic
        for auto workflow and sale order limit enforcement.

        Features:
        ---------
        1. **Auto Workflow Logic (when `is_auto_workflow` is enabled):**
            - Validates that the quotation contains at least two different products.
            - Groups sale order lines by product and sums their quantities.
            - Creates separate stock pickings and stock moves for each unique product.
            - Confirms and validates the deliveries.
            - Automatically creates and posts an invoice.
            - Registers full payment for the invoice using the first available bank journal.

        2. **Sale Order Limit Validation:**
            - If the `sale_admin_access.enable_sale_order_limit` config parameter is enabled
              and a `sale_order_limit` is set:
                - Blocks confirmation for users **not in** the `group_sale_admin_access` group
                  if the order total exceeds the configured limit.

        Returns:
            res (super): The result of the original `action_confirm` call.

        Raises:
            UserError:
                - If the quotation contains fewer than two different products.
                - If the sale order amount exceeds the allowed limit for non-admin users.
        """
        res = super().action_confirm()
        for order in self:
            if order.is_auto_workflow:
                # Ensure at least 2 different products
                product_ids = order.order_line.mapped('product_id.id')
                if len(set(product_ids)) < 2:
                    raise UserError("The quotation must contain at least two different products.")

                # 1. Group lines by product and sum their quantities
                product_map = {}
                for line in order.order_line:
                    product_id = line.product_id.id
                    if product_id not in product_map:
                        product_map[product_id] = {
                            'product': line.product_id,
                            'uom': line.product_uom,
                            'total_qty': 0.0,
                            'name': line.name,
                            'sale_lines': [],
                        }
                    product_map[product_id]['total_qty'] += line.product_uom_qty
                    product_map[product_id]['sale_lines'].append(line)

                custom_pickings = []
                for product_id, data in product_map.items():
                    # Create picking
                    picking = self.env['stock.picking'].create({
                        'partner_id': order.partner_id.id,
                        'picking_type_id': order.picking_ids[:1].picking_type_id.id,
                        'location_id': order.warehouse_id.lot_stock_id.id,
                        'location_dest_id': order.partner_id.property_stock_customer.id,
                        'origin': order.name,
                        'sale_id': order.id,
                    })

                    # Create a single stock move for the summed quantity
                    self.env['stock.move'].create({
                        'name': data['name'],
                        'product_id': product_id,
                        'product_uom_qty': data['total_qty'],
                        'product_uom': data['uom'].id,
                        'picking_id': picking.id,
                        'location_id': order.warehouse_id.lot_stock_id.id,
                        'location_dest_id': order.partner_id.property_stock_customer.id,
                        'sale_line_id': data['sale_lines'][0].id,
                    })

                    picking.action_confirm()
                    custom_pickings.append(picking.id)

                order.write({'picking_ids': [(6, 0, custom_pickings)]})

                # 2. Validate all deliveries
                pickings = order.picking_ids.filtered(lambda p: p.state not in ('done', 'cancel'))
                for picking in pickings:
                    if picking.state == 'draft':
                        picking.with_context(skip_immediate=True).action_confirm()
                    if picking.state in ('draft', 'confirmed', 'assigned'):
                        for move in picking.move_ids_without_package:
                            move.quantity = move.product_uom_qty
                        picking.with_context(skip_immediate=True).button_validate()

                # 3. Create and post invoice
                if order.invoice_status == 'to invoice':
                    invoice = order._create_invoices()
                    invoice.action_post()

                    # 4. Register full payment
                    if invoice.amount_residual > 0:
                        payment_register = self.env['account.payment.register'].with_context(
                            active_model='account.move',
                            active_ids=invoice.ids,
                        ).create({
                            'payment_date': fields.Date.today(),
                            'journal_id': self.env['account.journal'].search([('type', '=', 'bank')], limit=1).id,
                            'amount': invoice.amount_residual,
                        })
                        payment_register.action_create_payments()

            # Enforce sale order limit check for non-admin users
            enable_limit = self.env['ir.config_parameter'].sudo().get_param('sale_admin_access.enable_sale_order_limit',
                                                                            False)
            limit = self.env['ir.config_parameter'].sudo().get_param('sale_admin_access.sale_order_limit', False)
            if (
                    not self.env.user.has_group('sale_admin_access.group_sale_admin_access')
                    and limit is not False
                    and enable_limit is not False
                    and self.amount_total > float(limit)
            ):
                raise UserError(f"Sale Order total exceeds the configured limit of {limit}.")

        return res
