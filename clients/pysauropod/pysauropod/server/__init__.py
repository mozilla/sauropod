# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
"""

Pyramid-based server to support the Sauropod web API.

This package implements a simple pyramid/mozsvc-based WSGI application
which will expose an ISauropodBackend via a HTTP-based API.

"""

from mozsvc import plugin
from mozsvc.config import get_configurator


def includeme(config):
    config.include("cornice")
    config.include("mozsvc")
    config.include("pysauropod.server.security")
    config.include("pysauropod.server.session")
    config.include("pysauropod.server.credentials")
    config.scan("pysauropod.server.views")
    settings = config.get_settings()
    if "sauropod.storage.backend" not in settings:
        default_backend = "pysauropod.backends.sql:SQLBackend"
        settings["sauropod.storage.backend"] = default_backend
        #settings["sauropod.storage.sqluri"] = "sqlite:///:memory:"
        settings["sauropod.storage.sqluri"] = "sqlite:////tmp/sauropod.db"
        settings["sauropod.storage.create_tables"] = True
    plugin.load_and_register("sauropod.storage", config)


def main(global_config={}, **settings):
    config = get_configurator(global_config, **settings)
    config.include(includeme)
    return config.make_wsgi_app()


if __name__ == '__main__':
    from paste.httpserver import serve
    app = main()
    serve(app, host='0.0.0.0')
