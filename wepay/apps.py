from django.apps import AppConfig


class WepayConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'wepay'
    
    def ready(self):
        """Import signals when the app is ready to register them."""
        import wepay.signals
