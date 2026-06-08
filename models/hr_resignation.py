from odoo import models, fields, api, _
from odoo.exceptions import AccessError

class HrResignation(models.Model):
    _name = 'hr.resignation'
    _description = 'Employee Resignation'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'employee_id'

    # --- Security Visibility Fields (Hidden in UI) ---
    is_direct_manager = fields.Boolean(compute='_compute_access_rights')
    is_hr_manager = fields.Boolean(compute='_compute_access_rights')
    can_reject = fields.Boolean(compute='_compute_access_rights')

    @api.depends('manager_id.user_id', 'state')
    @api.depends_context('uid')
    def _compute_access_rights(self):
        for rec in self:
            is_admin = self.env.user.has_group('base.group_system')
            
            # Match by direct User object linkage OR match by name safely as a backup
            is_manager = False
            if rec.manager_id and rec.manager_id.user_id:
                is_manager = (rec.manager_id.user_id.id == self.env.user.id)
            
            rec.is_direct_manager = is_manager or is_admin
            rec.is_hr_manager = self.env.user.has_group('hr.group_hr_manager') or is_admin
            
            if rec.state == 'submitted' and rec.is_direct_manager:
                rec.can_reject = True
            elif rec.state == 'approved_manager' and rec.is_hr_manager:
                rec.can_reject = True
            else:
                rec.can_reject = False

    # --- Standard Fields ---
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)
    requested_by = fields.Many2one('res.users', string='Requested By', tracking=True, default=lambda self: self.env.user)
    department_id = fields.Many2one('hr.department', string='Department', related='employee_id.department_id', store=True)
    job_id = fields.Many2one('hr.job', string='Job Position', related='employee_id.job_id', store=True)
    manager_id = fields.Many2one('hr.employee', string='Manager', related='employee_id.parent_id', store=True)
    
    resignation_date = fields.Date(string='Resignation Date', default=fields.Date.today, required=True)
    last_working_day = fields.Date(string='Last Working Day', required=True)
    notice_period = fields.Integer(string='Notice Period (Days)', compute='_compute_notice_period', store=True)
    reason = fields.Text(string='Reason', required=True)
    remarks = fields.Text(string='Remarks')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved_manager', 'Manager Approved'),
        ('approved_hr', 'HR Approved'),
        ('rejected', 'Rejected'),
        ('done', 'Done'),
        ('cancel', 'Cancelled')
    ], string='Status', default='draft', tracking=True)

    clearance_business_unit_ids = fields.Many2many(
        "hr.clearance.checklist.type",
        string="Branch",
        required=True,
        tracking=True,
    )

    @api.depends('resignation_date', 'last_working_day')
    def _compute_notice_period(self):
        for rec in self:
            if rec.resignation_date and rec.last_working_day:
                delta = rec.last_working_day - rec.resignation_date
                rec.notice_period = delta.days
            else:
                rec.notice_period = 0

    # --- Actions ---
    def action_submit(self):
        self.ensure_one()
        self.write({'state': 'submitted'})

    def action_approve_manager(self):
        self.ensure_one()
        is_admin = self.env.user.has_group('base.group_system')
        is_manager = False
        if self.manager_id and self.manager_id.user_id:
            is_manager = (self.manager_id.user_id.id == self.env.user.id)

        if not (is_manager or is_admin):
            raise AccessError("Only the employee's direct manager can approve this initial stage.")
            
        self.write({'state': 'approved_manager'})

    def action_approve_hr(self):
        self.ensure_one()
        if not self.env.user.has_group('hr.group_hr_manager'):
            raise AccessError("Access Denied: Only users with 'HR Manager' privileges can approve the final stage.")
        
        self.write({'state': 'approved_hr'})
        if hasattr(self, 'create_clearance_request'):
            self.create_clearance_request()

    def action_reject(self):
        for rec in self:
            is_manager = (rec.manager_id and rec.manager_id.user_id == self.env.user)
            is_hr = self.env.user.has_group('hr.group_hr_manager')
            
            if not (is_manager or is_hr):
                raise AccessError("You do not have permission to reject this request.")
            rec.write({'state': 'rejected'})

    def action_cancel(self):
        self.write({'state': 'cancel'})
        
    def action_reset_to_draft(self):
        self.write({'state': 'draft'})

    def create_clearance_request(self):
        if not self.env['hr.clearance'].sudo().search([('resignation_id', '=', self.id)]):
            clearance = self.env['hr.clearance'].sudo().create({
                'employee_id': self.employee_id.id,
                'resignation_id': self.id,
                'checklist_type_ids': [(6, 0, self.clearance_business_unit_ids.ids)],
                'company_id': self.company_id.id,
            })
            clearance.sudo()._oncreate_populate_checklist()
            return clearance