# ***** BEGIN LICENSE BLOCK *****
# Version: MPL 1.1/GPL 2.0/LGPL 2.1
#
# The contents of this file are subject to the Mozilla Public License Version
# 1.1 (the "License"); you may not use this file except in compliance with
# the License. You may obtain a copy of the License at
# http://www.mozilla.org/MPL/
#
# Software distributed under the License is distributed on an "AS IS" basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
# for the specific language governing rights and limitations under the
# License.
#
# The Original Code is Sauropod.
#
# The Initial Developer of the Original Code is the Mozilla Foundation.
# Portions created by the Initial Developer are Copyright (C) 2010
# the Initial Developer. All Rights Reserved.
#
# Contributor(s):
#   Ryan Kelly (rkelly@mozilla.com)
#
# Alternatively, the contents of this file may be used under the terms of
# either the GNU General Public License Version 2 or later (the "GPL"), or
# the GNU Lesser General Public License Version 2.1 or later (the "LGPL"),
# in which case the provisions of the GPL or the LGPL are applicable instead
# of those above. If you wish to allow use of your version of this file only
# under the terms of either the GPL or the LGPL, and not to allow others to
# use your version of this file under the terms of the MPL, indicate your
# decision by deleting the provisions above and replace them with the notice
# and other provisions required by the GPL or the LGPL. If you do not delete
# the provisions above, a recipient may use your version of this file under
# the terms of any one of the MPL, the GPL or the LGPL.
#
# ***** END LICENSE BLOCK *****
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
