# -*- coding: utf-8 -*-
# microsof_2025_platform/core/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.utils import timezone
import datetime
from decimal import Decimal
import random
from django.db.models import Sum

# Importação dos formulários
from .forms import (
    CustomUserCreationForm,
    CustomAuthenticationForm,
    DepositForm,
    UserBankAccountForm,
    WithdrawalForm,
    SelectProductForm,
    UserProfileUpdateForm,
    UserPasswordChangeForm,
)
# Importação dos modelos
from .models import (
    CustomUser,
    Bank,
    Deposit,
    UserBankAccount,
    Product,
    Task,
    SupportInfo,
    LuckyWheelPrize,
    LuckyWheelSpin,
    Withdrawal,
    UserProfile,
)

# --- Views de Autenticação ---

def register_view(request):
    """
    View para o registro de novos usuários.
    Cria um novo usuário, gera um código de convite e atribui um bónus ao
    referenciador, se um código válido for fornecido.
    """
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                user = form.save()
                
                invited_by_code = form.cleaned_data.get('invited_by_code')
                if invited_by_code:
                    try:
                        # Procura pelo utilizador que convidou
                        referrer = CustomUser.objects.get(my_invitation_code=invited_by_code)
                        bonus_amount = Decimal('100.00')
                        referrer.bonus_balance += bonus_amount
                        # CORREÇÃO APLICADA AQUI: Adicionar o bônus também ao referral_income para rastreamento total
                        referrer.referral_income += bonus_amount 
                        referrer.save()
                        messages.success(request, f"Parabéns! Você recebeu um bónus de Kz {bonus_amount} por convidar {user.username}.")
                    except CustomUser.DoesNotExist:
                        messages.error(request, "Código de convite inválido fornecido (problema interno).")
                
            messages.success(request, 'Registo realizado com sucesso! Faça login para continuar.')
            return redirect('login')
        else:
            # Exibe erros de validação do formulário
            for field, errors in form.errors.items():
                for error in errors:
                    if field == '__all__':
                        messages.error(request, f"Erro: {error}")
                    else:
                        messages.error(request, f"Erro no campo '{form.fields[field].label}': {error}")
    else:
        form = CustomUserCreationForm()
    return render(request, 'core/register.html', {'form': form})

def login_view(request):
    """
    View para o login de usuários.
    Autentica o utilizador e redireciona para a página inicial em caso de sucesso.
    """
    if request.method == 'POST':
        form = CustomAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f'Bem-vindo(a), {user.username}!')
                return redirect('home')
            else:
                messages.error(request, 'Número de telefone ou senha inválidos.')
        else:
            # Exibe erros de validação do formulário
            for field, errors in form.errors.items():
                for error in errors:
                    if field == '__all__':
                        messages.error(request, f"Erro: {error}")
                    else:
                        messages.error(request, f"Erro no campo '{form.fields[field].label}': {error}")
    else:
        form = CustomAuthenticationForm()
    return render(request, 'core/login.html', {'form': form})

@login_required
def logout_view(request):
    """
    View para o logout de usuários.
    """
    logout(request)
    messages.info(request, 'Você foi desconectado(a).')
    return redirect('login')

# --- Views Principais ---

@login_required
def home_view(request):
    """
    View da página inicial do usuário.
    Exibe informações do utilizador, como o produto ativo e o número de referidos.
    """
    user = CustomUser.objects.get(pk=request.user.pk)
    
    # Conta os referidos que têm o código de convite do utilizador atual
    referral_count = CustomUser.objects.filter(invited_by_code=user.my_invitation_code).count() if user.my_invitation_code else 0

    context = {
        'user': user,
        'referral_count': referral_count,
    }
    return render(request, 'core/home.html', context)

@login_required
def deposit_view(request):
    """
    View para o depósito de fundos.
    Permite ao utilizador submeter uma solicitação de depósito.
    """
    banks = Bank.objects.filter(is_active=True)
    if not banks.exists():
        messages.warning(request, "Nenhum banco disponível para depósito no momento. Tente mais tarde.")
        return redirect('home')

    if request.method == 'POST':
        form = DepositForm(request.POST, request.FILES)
        if form.is_valid():
            with transaction.atomic():
                deposit = form.save(commit=False)
                deposit.user = request.user
                deposit.status = 'Pending'
                deposit.save()
            messages.success(request, "Sua solicitação de depósito foi enviada e está pendente de aprovação.")
            return redirect('deposit')
        else:
            # Exibe erros de validação do formulário
            for field, errors in form.errors.items():
                for error in errors:
                    if field == '__all__':
                        messages.error(request, f"Erro: {error}")
                    else:
                        messages.error(request, f"Erro no campo '{form.fields[field].label}': {error}")
    else:
        form = DepositForm()
    
    support_info = SupportInfo.objects.first()
    
    context = {
        'form': form,
        'banks': banks,
        'support_info': support_info,
    }
    return render(request, 'core/deposit.html', context)


@login_required
def withdrawal_view(request):
    """
    View para a retirada de fundos.
    Verifica o saldo e o valor mínimo antes de processar a retirada.
    """
    user = request.user
    withdrawal_tax_percentage = Decimal('5.0')  # Taxa de 5%
    withdrawal_min_amount = Decimal('1500.00')  # Saque mínimo

    # Contas bancárias ativas do usuário
    user_bank_accounts = UserBankAccount.objects.filter(user=user, is_active=True)

    if not user_bank_accounts.exists():
        messages.warning(request, "Você precisa adicionar uma conta bancária ativa antes de fazer uma retirada.")
        return redirect('add_bank_account')

    if request.method == 'POST':
        form = WithdrawalForm(request.POST, user=user)
        if form.is_valid():
            amount = form.cleaned_data['amount']
            selected_account = form.cleaned_data['user_bank_account']
            
            # Validação de regras de negócio
            if amount < withdrawal_min_amount:
                messages.error(request, f"O saque mínimo permitido é de Kz {withdrawal_min_amount:.2f}.")
            elif amount > user.balance:
                messages.error(request, "Saldo insuficiente para esta retirada.")
            else:
                with transaction.atomic():
                    # Lógica de cálculo
                    tax_percentage_decimal = withdrawal_tax_percentage / 100
                    tax_amount = amount * tax_percentage_decimal
                    amount_received = amount - tax_amount

                    # Atualiza o saldo do usuário
                    user.balance -= amount
                    user.save()

                    # Cria o objeto de retirada no banco de dados
                    Withdrawal.objects.create(
                        user=user,
                        user_bank_account=selected_account,
                        amount=amount,
                        tax_percentage=withdrawal_tax_percentage,  # Armazena a porcentagem, não o decimal
                        amount_received=amount_received,
                        status='Pending'
                    )
                    messages.success(request, f"Sua solicitação de retirada de Kz {amount:.2f} foi enviada. Você receberá Kz {amount_received:.2f}.")
                    return redirect('withdrawal')
        else:
            # Se o formulário for inválido, as mensagens de erro já estarão no objeto 'form'
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"Erro no campo '{form.fields[field].label}': {error}")
    else:
        form = WithdrawalForm(user=user)

    context = {
        'form': form,
        'user_bank_accounts': user_bank_accounts,
        'current_balance': user.balance,
        'withdrawal_tax_percentage': withdrawal_tax_percentage,
        'has_bank_account': user_bank_accounts.exists(),
    }
    return render(request, 'core/withdrawal.html', context)


@login_required
def add_bank_account_view(request):
    """
    View para adicionar uma conta bancária ao perfil do usuário.
    """
    if request.method == 'POST':
        form = UserBankAccountForm(request.POST)
        if form.is_valid():
            bank_account = form.save(commit=False)
            bank_account.user = request.user
            bank_account.is_active = True  # Garantir que a conta seja ativa
            bank_account.save()
            messages.success(request, "Conta bancária adicionada com sucesso!")
            return redirect('profile')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    if field == '__all__':
                        messages.error(request, f"Erro: {error}")
                    else:
                        messages.error(request, f"Erro no campo '{form.fields[field].label}': {error}")
    else:
        form = UserBankAccountForm()
    
    user_bank_accounts = UserBankAccount.objects.filter(user=request.user)
    context = {
        'form': form,
        'user_bank_accounts': user_bank_accounts,
    }
    return render(request, 'core/add_bank_account.html', context)


@login_required
def support_view(request):
    """
    View para a página de suporte.
    """
    support_info = SupportInfo.objects.first()
    context = {
        'support_info': support_info
    }
    return render(request, 'core/support.html', context)


@login_required
def income_view(request):
    """
    View para a página de renda do usuário.
    Verifica se a renda diária deve ser calculada e atualiza o saldo do utilizador.
    Também busca e exibe o histórico de depósitos, retiradas e tarefas concluídas.
    """
    user = request.user
    
    # Recarrega o usuário para ter o saldo mais recente
    user.refresh_from_db() 

    tasks = Task.objects.filter(user=user, is_completed=False)
    today = timezone.localdate()
    is_weekend = today.weekday() >= 5 # 5 é sábado, 6 é domingo

    for task in tasks:
        if not task.last_income_calculation_date or (task.last_income_calculation_date < today and not is_weekend):
            if user.level_activation_date:
                activation_date = user.level_activation_date.date()
                end_date = activation_date + datetime.timedelta(days=task.product.duration_days)
                
                if today >= end_date:
                    with transaction.atomic():
                        task.is_completed = True
                        task.completion_date = timezone.now()
                        task.save()
                    
                        if user.current_product == task.product:
                            user.current_product = None
                            user.level_activation_date = None
                            user.save()
                        messages.info(request, f"Seu investimento '{task.product.level_name}' foi concluído.")
                    continue

                daily_income_amount = task.product.daily_income
                with transaction.atomic():
                    user.balance += daily_income_amount
                    user.save()
                    task.last_income_calculation_date = today
                    task.save()
                    messages.success(request, f"Renda diária de Kz {daily_income_amount:.2f} do produto '{task.product.level_name}' adicionada ao seu saldo!")
    
    # --- Dados para o Resumo de Ganhos ---
    # É importante recalcular o usuário após qualquer save() dentro do loop acima
    user.refresh_from_db() 
    current_balance = user.balance
    total_referral_earnings = user.referral_income # Assumindo que referral_income no CustomUser armazena o total
    
    # Calcular Total de Ganhos por Tarefas (Soma da renda diária de todas as tarefas *dias concluídos*)
    # Isso pode ser complexo se precisar somar a renda de tarefas que foram ativadas em dias diferentes.
    # Por simplicidade, vamos somar a renda diária total de produtos ativos multiplicado pela duração
    # Se uma tarefa for concluída, ela contribui para os ganhos totais.
    
    # Soma de ganhos de tarefas concluídas (renda total do produto)
    completed_tasks_total_earnings = Decimal('0.00')
    all_completed_tasks = Task.objects.filter(user=user, is_completed=True)
    for task_completed in all_completed_tasks:
        if task_completed.product:
            # Multiplica a renda diária pela duração total para o ganho total daquela tarefa
            completed_tasks_total_earnings += task_completed.product.daily_income * task_completed.product.duration_days

    # Soma da renda diária de tarefas ATIVAS (para o dia atual)
    active_tasks_daily_income = Task.objects.filter(user=user, is_completed=False).aggregate(Sum('product__daily_income'))['product__daily_income__sum'] or Decimal('0.00')
    
    # Para o "Total de Ganhos por Tarefas", o mais preciso seria somar todas as rendas que já foram ADICIONADAS ao saldo
    # Isso exigiria um modelo de `IncomeTransaction` ou similar.
    # Como não temos um modelo de transações de renda diária, vamos somar as rendas dos produtos das tarefas CONCLUÍDAS
    # e, para as ativas, pode-se considerar o que já foi acumulado ou a renda diária total *até agora*.
    # Por agora, para 'total_task_earnings', usaremos a soma dos ganhos totais dos produtos das tarefas concluídas.
    # Se precisar de um histórico mais granular, um novo modelo de transação de renda seria ideal.
    
    total_task_earnings = completed_tasks_total_earnings # Total de ganhos de tarefas já concluídas


    # --- Histórico de Transações Recentes ---
    recent_deposits = Deposit.objects.filter(user=user, status='Approved').order_by('-timestamp')[:10] # Últimos 10
    recent_withdrawals = Withdrawal.objects.filter(user=user, status='Approved').order_by('-timestamp')[:10] # Últimos 10
    
    # Para tarefas, você pode querer mostrar tarefas recém-concluídas
    completed_tasks_for_history = Task.objects.filter(user=user, is_completed=True).order_by('-completion_date')[:10]


    context = {
        'user': user,
        'current_balance': current_balance,
        'total_task_earnings': total_task_earnings,
        'total_referral_earnings': total_referral_earnings,
        'recent_deposits': recent_deposits,
        'recent_withdrawals': recent_withdrawals,
        'completed_tasks': completed_tasks_for_history, # Renomeado para clareza no template
    }
    return render(request, 'core/income.html', context)


@login_required
def products_view(request):
    """
    View para exibir a lista de produtos (níveis de investimento).
    """
    products = Product.objects.filter(is_active=True).order_by('order')
    form = SelectProductForm()
    
    context = {
        'products': products,
        'form': form,
    }
    return render(request, 'core/products.html', context)


@login_required
def activate_product_view(request):
    """
    View para ativar um produto de investimento.
    Verifica se o utilizador tem saldo e não tem outro produto ativo antes de ativar.
    """
    if request.method == 'POST':
        product_id = request.POST.get('product_id')
        if not product_id:
            messages.error(request, "ID do produto não fornecido.")
            return redirect('investment_levels')

        try:
            selected_product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            messages.error(request, "O produto selecionado não existe.")
            return redirect('investment_levels')

        user = request.user

        if user.current_product and selected_product.order <= user.current_product.order:
            messages.error(request, f"Você já possui um produto ativo. Você só pode fazer upgrade para um nível superior.")
            return redirect('investment_levels')
        
        # A lógica foi corrigida para permitir o upgrade
        # O valor para comprar o nível vem do saldo principal (balance).
        if user.balance < selected_product.min_deposit_amount:
            messages.error(request, f"Saldo insuficiente. Você precisa de Kz {selected_product.min_deposit_amount} para ativar este produto.")
            return redirect('investment_levels')

        with transaction.atomic():
            # Deduz o valor do saldo do utilizador e atribui o produto
            user.balance -= selected_product.min_deposit_amount
            user.current_product = selected_product
            user.level_activation_date = timezone.now()
            user.save()

            # Cria uma tarefa para rastrear o novo investimento
            Task.objects.create(
                user=user,
                product=selected_product,
                is_completed=False,
                last_income_calculation_date=timezone.localdate()
            )
            
            # CORREÇÃO DO ERRO AQUI
            messages.success(request, f"Produto '{selected_product.level_name}' ativado com sucesso! Você agora receberá renda diária.")
            return redirect('income')
    
    return redirect('investment_levels')


@login_required
def team_view(request):
    """
    View para a página da equipa/referidos.
    Mostra o código de convite do utilizador e a lista dos seus referidos,
    distinguindo os que investiram dos que não investiram.
    """
    user = request.user
    
    invited_users = CustomUser.objects.filter(invited_by_code=user.my_invitation_code).order_by('-date_joined') if user.my_invitation_code else CustomUser.objects.none()
    
    total_invited_users = invited_users.count()
    
    invested_users_count = invited_users.filter(current_product__isnull=False).count()
    
    non_invested_users_count = total_invited_users - invested_users_count

    context = {
        'user': user,
        'invited_users': invited_users,
        'total_invited_users': total_invited_users,
        'invested_users_count': invested_users_count,
        'non_invested_users_count': non_invested_users_count,
    }
    return render(request, 'core/team.html', context)


@login_required
def profile_view(request):
    """
    View para a página de perfil.
    Permite visualizar e editar o perfil do usuário, alterar a senha e
    gerenciar suas contas bancárias.
    """
    user = request.user
    user_profile, created = UserProfile.objects.get_or_create(user=user)
    user_bank_accounts = UserBankAccount.objects.filter(user=user)
    
    profile_form = UserProfileUpdateForm(instance=user_profile)
    password_form = UserPasswordChangeForm(user=user)
    add_bank_account_form = UserBankAccountForm()
    
    bank_account_forms = {}
    for account in user_bank_accounts:
        bank_account_forms[account.id] = UserBankAccountForm(instance=account)

    if request.method == 'POST':
        if 'update_profile' in request.POST:
            profile_form = UserProfileUpdateForm(request.POST, instance=user_profile)
            if profile_form.is_valid():
                updated_profile = profile_form.save()
                
                # --- Lógica de sincronização com UserBankAccount ---
                # Procura por uma conta bancária principal ou cria uma nova
                primary_bank_account, created = UserBankAccount.objects.get_or_create(
                    user=user,
                    bank_name=updated_profile.bank_name,
                    account_name=updated_profile.full_name,
                    iban=updated_profile.iban,
                    defaults={'is_active': True}
                )
                if not created:
                    # Se já existia, atualiza os dados e garante que está ativa
                    primary_bank_account.bank_name = updated_profile.bank_name
                    primary_bank_account.account_name = updated_profile.full_name
                    primary_bank_account.iban = updated_profile.iban
                    primary_bank_account.is_active = True
                    primary_bank_account.save()

                messages.success(request, "Perfil e dados bancários principais atualizados com sucesso!")
                return redirect('profile')
            else:
                for field, errors in profile_form.errors.items():
                    for error in errors:
                        if field == '__all__':
                            messages.error(request, f"Erro: {error}")
                        else:
                            messages.error(request, f"Erro no campo '{profile_form.fields[field].label}': {error}")
        
        elif 'update_password' in request.POST:
            password_form = UserPasswordChangeForm(user=user, data=request.POST)
            if password_form.is_valid():
                password_form.save()
                messages.success(request, "Senha alterada com sucesso!")
                login(request, user) # Faz o login novamente para evitar que a sessão expire
                return redirect('profile')
            else:
                for field, errors in password_form.errors.items():
                    for error in errors:
                        if field == '__all__':
                            messages.error(request, f"Erro: {error}")
                        else:
                            messages.error(request, f"Erro no campo '{password_form.fields[field].label}': {error}")

        elif 'add_bank_account' in request.POST:
            add_bank_account_form = UserBankAccountForm(request.POST)
            if add_bank_account_form.is_valid():
                bank_account = add_bank_account_form.save(commit=False)
                bank_account.user = user
                bank_account.is_active = True
                bank_account.save()
                messages.success(request, "Conta bancária adicionada com sucesso!")
                return redirect('profile')
            else:
                for field, errors in add_bank_account_form.errors.items():
                    for error in errors:
                        if field == '__all__':
                            messages.error(request, f"Erro: {error}")
                        else:
                            messages.error(request, f"Erro no campo '{add_bank_account_form.fields[field].label}': {error}")

        elif 'update_bank_account' in request.POST:
            try:
                bank_account_id = request.POST.get('bank_account_id')
                if bank_account_id:
                    # Tenta obter a conta bancária do utilizador logado, ou retorna 404
                    bank_account_instance = get_object_or_404(UserBankAccount, pk=bank_account_id, user=user)
                    bank_account_form_to_update = UserBankAccountForm(request.POST, instance=bank_account_instance)
                    
                    if bank_account_form_to_valid():
                        # Salva o formulário, mas não comita ainda
                        updated_account = bank_account_form_to_update.save(commit=False)
                        # Garante que a conta atualizada está ativa
                        updated_account.is_active = True
                        # Salva o objeto na base de dados
                        updated_account.save()
                        messages.success(request, "Dados bancários atualizados com sucesso!")
                        return redirect('profile')
                    else:
                        messages.error(request, "Erro ao atualizar a conta bancária. Verifique os campos.")
                        bank_account_forms[int(bank_account_id)] = bank_account_form_to_update
                else:
                    messages.error(request, "ID da conta bancária não fornecido.")
            except UserBankAccount.DoesNotExist:
                messages.error(request, "A conta bancária que você tentou atualizar não existe ou não pertence a você.")
            except Exception as e:
                messages.error(request, f"Ocorreu um erro inesperado: {e}")

    context = {
        'user': user,
        'profile_form': profile_form,
        'password_form': password_form,
        'user_bank_accounts': user_bank_accounts,
        'bank_account_forms': bank_account_forms,
        'add_bank_account_form': add_bank_account_form,
    }
    return render(request, 'core/profile.html', context)


@login_required
def update_profile_name(request):
    """
    Redireciona para a página de perfil onde a lógica de atualização do nome é tratada.
    """
    return redirect('profile')

@login_required
def update_bank_profile(request):
    """
    Redireciona para a página de perfil onde a lógica de atualização de dados bancários principais é tratada.
    """
    return redirect('profile')
        
@login_required
def tasks_view(request):
    """
    View para a página de tarefas (investimentos ativos).
    """
    user = request.user
    active_task = Task.objects.filter(user=user, is_completed=False).first()
    
    context = {
        'active_task': active_task,
        'nivel': 'Nenhum',
        'renda_diaria': Decimal('0.00'),
        'invested_value': Decimal('0.00'),
        'percentage': Decimal('0.00'),
        'rental_date': None,
        'remaining_seconds': 0, # Adiciona a nova variável para o tempo restante
    }

    if active_task and active_task.product:
        context['nivel'] = active_task.product.level_name
        context['renda_diaria'] = active_task.product.daily_income
        context['invested_value'] = active_task.product.min_deposit_amount
        
        if active_task.product.min_deposit_amount > 0:
            context['percentage'] = (active_task.product.daily_income / active_task.product.min_deposit_amount) * 100
        else:
            context['percentage'] = Decimal('0.00')
        
        context['rental_date'] = active_task.creation_date
        
        # Calcula o tempo restante
        end_time = active_task.creation_date + datetime.timedelta(days=active_task.product.duration_days)
        time_left = end_time - timezone.now()
        context['remaining_seconds'] = max(0, int(time_left.total_seconds()))

    return render(request, 'core/tasks.html', context)

# --- Views da Roda da Sorte ---

@login_required
def lucky_wheel_view(request):
    """
    View para a Roda da Sorte.
    Reinicia o número de giros diários se for um novo dia.
    """
    user = request.user
    today = timezone.localdate()
    
    active_prizes = LuckyWheelPrize.objects.filter(is_active=True)
    if not active_prizes.exists():
        messages.warning(request, "A Roda da Sorte não está disponível no momento. Contate o suporte.")
        context = {
            'user': user,
            'prizes': [],
        }
        return render(request, 'core/lucky_wheel.html', context)
        
    # Verifica se é um novo dia para resetar os giros
    if user.last_spin_date is None or user.last_spin_date < today:
        first_prize = active_prizes.first()
        daily_spins_allowed = first_prize.daily_spins_allowed if first_prize and first_prize.daily_spins_allowed is not None else 1
        
        user.daily_spins_remaining = daily_spins_allowed
        user.last_spin_date = today
        user.save()
        messages.info(request, f"Seus giros diários da Roda da Sorte foram resetados! Você tem {daily_spins_allowed} giros.")

    context = {
        'user': user,
        'prizes': active_prizes,
    }
    return render(request, 'core/lucky_wheel.html', context)

@login_required
def spin_lucky_wheel(request):
    """
    View para processar um giro na Roda da Sorte.
    Seleciona um prémio com base no peso e atualiza o saldo do utilizador.
    """
    if request.method == 'POST':
        user = request.user
        
        if user.daily_spins_remaining <= 0:
            messages.error(request, "Você atingiu o limite diário de giros. Volte amanhã!")
            return redirect('lucky_wheel')

        active_prizes = LuckyWheelPrize.objects.filter(is_active=True)
        if not active_prizes.exists():
            messages.error(request, "Nenhum prémio configurado para a Roda da Sorte. Contate o suporte.")
            return redirect('lucky_wheel')

        total_weight = sum(prize.weight for prize in active_prizes)
        
        if total_weight == 0:
            messages.error(request, "Pesos dos prémios inválidos. Contate o suporte.")
            return redirect('lucky_wheel')

        rand_num = random.uniform(0, total_weight)
        
        cumulative_weight = 0
        prize_won = None
        for prize in active_prizes:
            cumulative_weight += prize.weight
            if rand_num <= cumulative_weight:
                prize_won = prize
                break
        
        if not prize_won:
            messages.error(request, "Não foi possível sortear um prémio. Tente novamente.")
            return redirect('lucky_wheel')

        with transaction.atomic():
            user.daily_spins_remaining -= 1
            user.last_spin_date = timezone.localdate()
            user.save()

            if prize_won.value > 0:
                user.balance += prize_won.value
                user.save()
                messages.success(request, f"Parabéns! Você ganhou Kz {prize_won.value:.2f} na Roda da Sorte!")
            else:
                messages.info(request, f"Você girou a Roda da Sorte, mas não ganhou um prémio em dinheiro desta vez.")

            LuckyWheelSpin.objects.create(
                user=user,
                prize_won=prize_won,
                is_paid_spin=False
            )
        
        return redirect('lucky_wheel')
    return redirect('home')


@login_required
def investment_levels_view(request):
    """
    View para exibir a lista de produtos (níveis de investimento).
    Acessa a tabela de produtos e envia os dados para o template.
    """
    products = Product.objects.filter(is_active=True).order_by('order')
    
    # O template espera a variável 'investment_levels', então vamos renomear aqui.
    context = {
        'investment_levels': products,
        'user_balance': request.user.balance, # Adicionado para o template
        'current_product_id': request.user.current_product.id if request.user.current_product else None,
    }
    
    return render(request, 'core/investment_levels.html', context)
