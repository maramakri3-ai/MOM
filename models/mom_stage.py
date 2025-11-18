from odoo import models, fields

class MOMStage(models.Model):
    _name = 'mom.stage'
    _description = 'MOM Stage'
    _order = 'sequence'

    name = fields.Char('Stage Name', required=True)
    sequence = fields.Integer('Sequence', default=1)
    fold = fields.Boolean('Folded in Kanban')
    description = fields.Text('Description')
