from odoo import models, fields, api


class HrIdOcrLog(models.Model):
    _name = 'hr.id.ocr.log'
    _description = 'ID OCR Log'
    _order = 'create_date desc'

    employee_id = fields.Many2one('nhan_vien', string='Nhân viên', ondelete='set null')
    connector_id = fields.Many2one('hr.id.ocr.connector', string='Connector', ondelete='set null')
    user_id = fields.Many2one('res.users', string='Thao tác bởi', default=lambda self: self.env.uid)
    create_date = fields.Datetime(string='Thời gian', readonly=True)
    result_text = fields.Text(string='Nội dung trích xuất')
    id_number = fields.Char(string='Số CCCD')
    id_name = fields.Char(string='Tên trên CCCD')
    confidence = fields.Float(string='Độ chính xác')
    status = fields.Selection([('success', 'Success'), ('failed', 'Failed'), ('partial', 'Partial')], default='success')
    error_message = fields.Text(string='Lỗi (nếu có)')

    @api.model
    def create(self, vals):
        # ensure user_id is set
        if 'user_id' not in vals:
            vals['user_id'] = self.env.uid
        return super(HrIdOcrLog, self).create(vals)

