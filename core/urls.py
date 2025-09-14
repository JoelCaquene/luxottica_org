# luxottica_org/core/urls.py

from django.urls import path
from . import views

urlpatterns = [
    # Rotas de Autenticação
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # Rota Principal (Home)
    path('', views.home_view, name='home'),
    
    # Rotas de Perfil do Usuário
    path('profile/', views.profile_view, name='profile'),
    path('profile/update-name/', views.update_profile_name, name='update_profile_name'),
    path('profile/update-bank/', views.update_bank_profile, name='update_bank_profile'),
    path('profile/add-bank/', views.add_bank_account_view, name='add_bank_account'),
    
    # Rotas de Depósito
    path('deposit/', views.deposit_view, name='deposit'),
    
    # Rotas de Retirada
    path('withdrawal/', views.withdrawal_view, name='withdrawal'),

    # Rotas de Produtos e Tarefas
    path('products/', views.products_view, name='products'),
    path('products/activate/', views.activate_product_view, name='activate_product'),
    path('tasks/', views.tasks_view, name='tasks'),
    
    # Rota para Níveis de Investimento (CORRIGIDO)
    path('investment_levels/', views.investment_levels_view, name='investment_levels'),
    
    # Rotas de Equipa (Convites)
    path('team/', views.team_view, name='team'),

    # Rota da Roda da Sorte
    path('lucky-wheel/', views.lucky_wheel_view, name='lucky_wheel'),
    path('lucky-wheel/spin/', views.spin_lucky_wheel, name='spin_lucky_wheel'),

    # Rota de Suporte
    path('support/', views.support_view, name='support'),

    # Rota de Renda
    path('income/', views.income_view, name='income'),
]
