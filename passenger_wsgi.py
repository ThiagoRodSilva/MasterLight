"""Entry point do Passenger (Hostinger, hospedagem compartilhada).

A raiz do projeto fica fora de `public_html` (definida no hPanel ->
seção Python / "Application root"). O Passenger importa este arquivo
e usa o callable `application` no WSGI.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.prod"

application = get_wsgi_application()
