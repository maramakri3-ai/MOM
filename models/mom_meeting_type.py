from odoo import models, fields

class MOMMeetingType(models.Model):
    _name = 'mom.meeting.type'
    _description = 'Meeting Type'
    _order = 'sequence'

    name = fields.Char('Meeting Type', required=True)
    sequence = fields.Integer('Sequence', default=10)
    description = fields.Text('Description')
    active = fields.Boolean('Active', default=True)
