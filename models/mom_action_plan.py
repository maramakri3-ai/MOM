from odoo import models, fields, api, _
from datetime import datetime, timedelta
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)

class MomActionPlan(models.Model):
    _name = 'mom.action.plan'
    _description = 'Action Plan'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'  # Add this line for default ordering

    # Update all fields to enable tracking
    name = fields.Char('Action Item', required=True, tracking=True)
    mom_id = fields.Many2one('mom.meeting', string='Meeting', required=False, ondelete='cascade', tracking=True)
    meeting_type_id = fields.Many2one(
        'mom.meeting.type', 
        string='Meeting Type', 
        store=True, 
        readonly=False,
        tracking=True,
        related='mom_id.meeting_type_id',
        compute='_compute_meeting_data',
        inverse='_inverse_meeting_type')
    meeting_date = fields.Date(
        related='mom_id.meeting_date', 
        string='Meeting Date', 
        store=True, 
        readonly=False,
        compute='_compute_meeting_data',
        tracking=True)
    responsible_id = fields.Many2one('hr.employee', string='Responsible Person', required=True, tracking=True)
    notes = fields.Text('Notes', tracking=True)
    department_id = fields.Many2one(
        'hr.department', 
        compute='_compute_department',
        compute_sudo=True,
        store=True,
        tracking=True
    )
    state = fields.Selection([
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('hold', 'Hold'),
        ('completed', 'Completed')
    ], string='Status', default='pending', tracking=True)
    
    # Fields for action item management
    can_manage_action_items = fields.Boolean(
        string='Can Manage Action Items',
        compute='_compute_can_manage_action_items',
        store=False
    )
    can_edit_state = fields.Boolean(
        string='Can Edit State',
        compute='_compute_can_edit_state',
        store=False
    )
    
    # New fields for deadline tracking
    deadline = fields.Date('Block Time (Deadline)', required=True, tracking=True)
    completion_date = fields.Date('Completion Date', tracking=True)
    time_status = fields.Selection([
        ('lead_time', 'Lead Time'),
        ('lag_time', 'Lag Time'),
        ('buffer_time', 'Buffer Time'),
        ('cycle_time_1', 'Cycle Time 1'),
        ('cycle_time_2', 'Cycle Time 2'),
        ('cycle_time_3', 'Cycle Time 3'),
        ('cycle_time_4+', 'Cycle Time 4+')
    ], string='Time Status', compute='_compute_time_status', store=True, tracking=True)
    cycle_count = fields.Integer('Cycle Extensions', default=0, tracking=True)
    extension_reason = fields.Text('Extension Reason', tracking=True)
    
    # Add recurring fields
    is_recurring = fields.Boolean('Recurring Task', default=False, tracking=True)
    recurrence_days = fields.Integer('Recur Every (Days)', default=1, tracking=True)
    next_deadline = fields.Date('Next Deadline', compute='_compute_next_deadline', store=True)
    
    # New countdown fields
    days_to_deadline = fields.Integer(
        string='Days Left', 
        compute='_compute_days_to_deadline',
        store=True
    )
    countdown_status = fields.Selection([
        ('green', 'Green'),
        ('yellow', 'Yellow'),
        ('orange', 'Orange'),
        ('red', 'Red'),
    ], string='Countdown Status', compute='_compute_days_to_deadline', store=True)
    
    @api.depends('deadline', 'is_recurring', 'recurrence_days', 'state')
    def _compute_next_deadline(self):
        for record in self:
            if record.is_recurring and record.deadline and record.state != 'completed':
                today = fields.Date.today()
                if today > record.deadline:
                    days_since = (today - record.deadline).days
                    days_to_add = ((days_since // record.recurrence_days) + 1) * record.recurrence_days
                    record.next_deadline = record.deadline + timedelta(days=days_to_add)
                else:
                    record.next_deadline = record.deadline
            else:
                record.next_deadline = record.deadline
    
    @api.constrains('recurrence_days')
    def _check_recurrence_days(self):
        for record in self:
            if record.is_recurring and record.recurrence_days < 1:
                raise ValidationError(_("Recurrence days must be at least 1"))
    
    # Override the time status computation for recurring tasks
    @api.depends('deadline', 'completion_date', 'state', 'cycle_count', 'is_recurring', 'next_deadline')
    def _compute_time_status(self):
        today = fields.Date.today()
        for record in self:
            if not record.deadline:
                record.time_status = False
                continue
            
            check_date = record.next_deadline if record.is_recurring else record.deadline
            
            if record.state == 'completed' and record.completion_date:
                if record.completion_date <= check_date:
                    record.time_status = 'lead_time'
                else:
                    days_late = (record.completion_date - check_date).days
                    record.time_status = record._get_time_status(days_late)
            elif record.state != 'completed':
                if today <= check_date:
                    record.time_status = 'lead_time'
                elif not self.env.user.has_group('MOM.group_mom_manager'):
                    # Only auto-move to lag time for non-managers
                    record.time_status = 'lag_time'
                else:
                    days_late = (today - check_date).days
                    record.time_status = record._get_time_status(days_late)
    
    def _get_time_status(self, days_late):
        if days_late <= 2:
            return 'lag_time'
        elif days_late <= 4:
            return 'buffer_time'
        else:
            cycle = (days_late - 4) // 2 + 1
            if cycle >= 4:
                return 'cycle_time_4+'
            return f'cycle_time_{cycle}'
    
    def write(self, vals):
        if 'state' in vals:
            old_state = self.state
            new_state = vals['state']
            
            # Auto-set completion date
            if new_state == 'completed':
                vals['completion_date'] = fields.Date.today()
            elif old_state == 'completed' and new_state != 'completed':
                vals['completion_date'] = False
            
            result = super().write(vals)
            
            # Log the state change
            if result:
                message = _(
                    "Status changed from '%(old)s' to '%(new)s' by %(user)s",
                    old=dict(self._fields['state'].selection).get(old_state),
                    new=dict(self._fields['state'].selection).get(new_state),
                    user=self.env.user.name
                )
                self.message_post(body=message)
            return result
        
        return super().write(vals)
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Only require mom_id for non-managers
            if not self.env.user.has_group('MOM.group_mom_manager') and not vals.get('mom_id'):
                return False
            elif vals.get('mom_id') and not self.env.user.has_group('MOM.group_mom_manager'):
                mom = self.env['mom.meeting'].browse(vals.get('mom_id'))
                if mom.prepared_by_id.user_id != self.env.user:
                    return False
        
        records = super().create(vals_list)
        
        # Send email notification to responsible person
        for record in records:
            if record.responsible_id and record.responsible_id.user_id:
                record._send_action_plan_notification()
        
        return records
    
    def _send_action_plan_notification(self):
        """Send email notification to responsible person when action plan is created"""
        self.ensure_one()
        
        if not self.responsible_id or not self.responsible_id.user_id:
            return
        
        # Build email body
        meeting_info = f"<strong>Meeting:</strong> {self.mom_id.name}<br/>" if self.mom_id else ""
        meeting_date_info = f"<strong>Meeting Date:</strong> {self.meeting_date.strftime('%B %d, %Y')}<br/>" if self.meeting_date else ""
        
        body_html = f"""
        <div style="font-family: Arial, sans-serif; padding: 20px;">
            <h2 style="color: #875A7B;">New Action Plan Assigned</h2>
            <p>Hello {self.responsible_id.name},</p>
            <p>You have been assigned a new action plan:</p>
            
            <div style="background-color: #f9f9f9; padding: 15px; border-left: 4px solid #875A7B; margin: 20px 0;">
                <h3 style="margin-top: 0; color: #875A7B;">{self.name}</h3>
                {meeting_info}
                {meeting_date_info}
                <strong>Deadline:</strong> {self.deadline.strftime('%B %d, %Y')}<br/>
                <strong>Status:</strong> {dict(self._fields['state'].selection).get(self.state)}<br/>
                {f'<strong>Notes:</strong> {self.notes}<br/>' if self.notes else ''}
            </div>
            
            <p>Please review and work on this action plan before the deadline.</p>
            <p>You can access the action plan by clicking the link below:</p>
            <p style="margin: 20px 0;">
                <a href="{self.get_base_url()}/web#id={self.id}&model=mom.action.plan&view_type=form" 
                   style="background-color: #875A7B; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                    View Action Plan
                </a>
            </p>
            
            <p style="color: #666; font-size: 12px; margin-top: 30px;">
                This is an automated notification from the Meeting Minutes (MOM) system.
            </p>
        </div>
        """
        
        # Send email
        mail_values = {
            'subject': f'New Action Plan: {self.name}',
            'body_html': body_html,
            'email_to': self.responsible_id.user_id.email or self.responsible_id.work_email,
            'email_from': self.env.user.email or self.env.company.email,
            'author_id': self.env.user.partner_id.id,
            'auto_delete': False,
        }
        
        mail = self.env['mail.mail'].sudo().create(mail_values)
        mail.send()
        
        # Also post a message in the chatter
        self.message_post(
            body=f"Action plan assigned to {self.responsible_id.name}. Email notification sent.",
            subject="Action Plan Assigned",
            message_type='notification',
            subtype_xmlid='mail.mt_note',
        )
    
    def unlink(self):
        if not self.env.user.has_group('MOM.group_mom_manager'):
            for record in self:
                if record.mom_id.prepared_by_id.user_id != self.env.user:
                    return False
        return super().unlink()
    
    @api.depends('mom_id.prepared_by_id', 'responsible_id')
    def _compute_can_manage_action_items(self):
        for record in self:
            record.can_manage_action_items = (
                record.mom_id.prepared_by_id.user_id == self.env.user or
                record.responsible_id.user_id == self.env.user or 
                self.env.user.has_group('MOM.group_mom_manager')
            )
    
    @api.depends('responsible_id', 'mom_id.prepared_by_id')
    def _compute_can_edit_state(self):
        for record in self:
            record.can_edit_state = (
                record.responsible_id.user_id == self.env.user or
                record.mom_id.prepared_by_id.user_id == self.env.user or
                self.env.user.has_group('MOM.group_mom_manager')
            )
    
    @api.depends('responsible_id.department_id')
    def _compute_department(self):
        for record in self:
            record.department_id = record.responsible_id.department_id
    
    @api.depends('mom_id')
    def _compute_meeting_data(self):
        for record in self:
            if record.mom_id:
                record.meeting_type_id = record.mom_id.meeting_type_id
                record.meeting_date = record.mom_id.meeting_date
            elif not record.meeting_type_id:
                # Set default meeting type
                meeting_type = self.env['mom.meeting.type'].search([], limit=1)
                if meeting_type:
                    record.meeting_type_id = meeting_type.id
    
    def _inverse_meeting_type(self):
        # This method is required for the inverse field to work properly
        pass
    
    @api.depends('deadline')
    def _compute_days_to_deadline(self):
        today = fields.Date.today()
        for record in self:
            if not record.deadline:
                record.days_to_deadline = 0
                record.countdown_status = 'green'
                continue
            
            days = (record.deadline - today).days
            record.days_to_deadline = days
            
            # Set countdown status based on days left
            if days <= 0:
                record.countdown_status = 'red'
            elif days <= 3:
                record.countdown_status = 'orange'
            elif days <= 7:
                record.countdown_status = 'yellow'
            else:
                record.countdown_status = 'green'
                
    # Method for cron job to update countdown days
    @api.model
    def update_countdown_days(self):
        """Update countdown days for all active action plans"""
        # Only update non-completed action plans
        action_plans = self.search([('state', '!=', 'completed')])
        for plan in action_plans:
            # Trigger compute method by writing to a dummy field
            # This avoids having to duplicate the logic
            plan._compute_days_to_deadline()
            
        _logger.info(f"Updated countdown days for {len(action_plans)} action plans")
        return True
