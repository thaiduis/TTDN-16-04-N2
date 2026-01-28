from odoo import models, fields, api


class HrIdOcrConnector(models.Model):
    _name = 'hr.id.ocr.connector'
    _description = 'OCR Connector for ID card extraction'

    name = fields.Char(string='Connector Name', required=True)
    provider = fields.Selection([
        ('local', 'Local (pytesseract)'),
        ('google', 'Google Vision'),
        ('aws', 'AWS Rekognition'),
        ('azure', 'Azure OCR'),
        ('custom', 'Custom HTTP API'),
    ], string='Provider', default='local', required=True)
    api_key = fields.Char(string='API Key')
    endpoint = fields.Char(string='Endpoint / URL')
    active = fields.Boolean(string='Active', default=True)
    default_for_new = fields.Boolean(string='Default connector for ID OCR', default=False)
    note = fields.Text(string='Notes / configuration')

    @api.model
    def get_default_connector(self):
        """Return a single active default connector if set, otherwise active local connector."""
        connector = self.search([('default_for_new', '=', True), ('active', '=', True)], limit=1)
        if connector:
            return connector
        return self.search([('provider', '=', 'local'), ('active', '=', True)], limit=1)

    def test_connection(self):
        """Simple test action for cloud providers. Local has no external check."""
        for rec in self:
            if rec.provider == 'local':
                return True
            if rec.provider == 'custom' and not rec.endpoint:
                raise ValueError('Custom provider requires an endpoint.')
            # For cloud connectors, we just attempt a minimal HTTP HEAD/GET if endpoint exists.
            if rec.endpoint:
                import requests
                try:
                    r = requests.get(rec.endpoint, timeout=5, headers={'Authorization': f'Bearer {rec.api_key}'} if rec.api_key else {})
                    if r.status_code in (200, 204):
                        return True
                    else:
                        raise ValueError(f'Connector test failed: HTTP {r.status_code}')
                except Exception as e:
                    raise
            else:
                raise ValueError('No endpoint configured for this connector.')

