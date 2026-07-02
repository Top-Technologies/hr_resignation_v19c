import odoo
odoo.tools.config.parse_config(['-c', '/opt/odoo19/odoo.conf', '-d', 'stest'])
registry = odoo.registry('stest')
with registry.cursor() as cr:
    env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
    if 'hr.employee.public' in env:
        print("Model exists!")
        print("Fields:", env['hr.employee.public']._fields.keys())
