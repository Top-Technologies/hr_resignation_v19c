import odoo
odoo.tools.config.parse_config(['-c', '/opt/odoo19/odoo.conf', '-d', 'stest'])
registry = odoo.registry('stest')
with registry.cursor() as cr:
    env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
    print("Has employee_id:", hasattr(env.user, 'employee_id'))
