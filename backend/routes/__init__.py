def register_routes(app):
    from .auth import auth
    from .rooms import rooms
    from .tenants import tenants
    from .contracts import contracts
    from .invoices import invoices
    from .reports import reports

    for blueprint in (auth, rooms, tenants, contracts, invoices, reports):
        app.register_blueprint(blueprint)
