# luxottica_org/luxottica_org/urls.py

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')), # Inclui todas as URLs do seu app 'core'
]

# Apenas para desenvolvimento: servir arquivos de mídia e estáticos
# Isso NÃO deve ser usado em produção! Servidores web como Nginx/Apache devem fazer isso.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    # Também para arquivos estáticos no modo de desenvolvimento, se necessário
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
