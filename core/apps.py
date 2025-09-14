from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    # Removi o método ready() e a importação de signals.
    # Os seus signals já são carregados automaticamente porque estão em models.py,
    # que é importado pelo Django quando a aplicação é iniciada.
    