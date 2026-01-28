from odoo import models, fields, api


class HrIdOcrWizard(models.TransientModel):
    _name = 'hr.id.ocr.wizard'
    _description = 'Wizard for ID Card OCR'

    employee_id = fields.Many2one('nhan_vien', string='Nhân viên')
    connector_id = fields.Many2one('hr.id.ocr.connector', string='OCR Connector',
                                   default=lambda self: self.env['hr.id.ocr.connector'].get_default_connector().id if self.env['hr.id.ocr.connector'].search([], limit=1) else False)
    image = fields.Binary(string='Ảnh CCCD', required=True)
    filename = fields.Char(string='Tên file')
    result_text = fields.Text(string='Nội dung trích xuất')
    id_number = fields.Char(string='Số CCCD')
    id_name = fields.Char(string='Tên trên CCCD')
    confidence = fields.Float(string='Độ chính xác')
    apply_to_employee = fields.Boolean(string='Cập nhật vào hồ sơ nhân viên', default=True)

    def action_run_ocr(self):
        """Run OCR using the selected connector and populate result fields."""
        self.ensure_one()
        connector = self.connector_id or self.env['hr.id.ocr.connector'].get_default_connector()
        service = self.env['hr.id.ocr.service']
        res = service.perform_ocr(self.image, connector.id if connector else False)
        # res expected: {'text': str, 'id_number': str, 'id_name': str, 'confidence': float}
        self.result_text = res.get('text', '')
        self.id_number = res.get('id_number', False)
        self.id_name = res.get('id_name', False)
        self.confidence = res.get('confidence', 0.0)
        if self.apply_to_employee and self.employee_id:
            vals = {
                'id_card_text': self.result_text,
                'id_number': self.id_number,
                'id_name': self.id_name,
                'id_confidence': self.confidence,
                'id_verified': bool(self.id_number and (self.id_number == (self.employee_id.cmnd or self.id_number))),
            }
            # only write image fields if employee has no image or filenames differ
            if self.employee_id and self.image:
                vals.update({'id_card_image': self.image, 'id_card_filename': self.filename})
            self.employee_id.write(vals)
        return {'type': 'ir.actions.act_window_close'}

