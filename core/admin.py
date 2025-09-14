from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.db import transaction
from django.utils import timezone
from .models import (
    CustomUser, Product, Bank, Deposit, UserBankAccount, UserProfile,
    Withdrawal, Task, SupportInfo, LuckyWheelPrize, LuckyWheelSpin
)

# Adiciona o modelo UserProfile como um "Inline" na página de edição do CustomUser
class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Perfil do Usuário'
    fk_name = 'user'
    # Campos que realmente existem no modelo UserProfile.
    fields = ('full_name', 'bank_name', 'iban')

# Admin para CustomUser
@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    # Usa o inline para exibir os campos do UserProfile na página de edição do usuário
    inlines = (UserProfileInline,)
    
    # Campos a serem exibidos na lista de usuários no admin
    list_display = (
        'username', 'phone_number', 'email', 'balance', 'is_staff',
        'current_product', 'level_activation_date',
        'my_invitation_code', 'invited_by_code',
        'can_spin_lucky_wheel', 'daily_spins_remaining', 'last_spin_date'
    )
    # Campos que podem ser usados para buscar usuários.
    # 'profile__full_name' e 'profile__iban' acessam os campos do UserProfile.
    # Os outros campos são diretamente do CustomUser.
    search_fields = ('username', 'phone_number', 'email', 'my_invitation_code', 'invited_by_code', 'profile__full_name', 'profile__iban')
    # Campos que podem ser filtrados
    list_filter = ('is_staff', 'is_active', 'is_superuser', 'current_product', 'can_spin_lucky_wheel')

    # Configuração dos campos no formulário de edição de usuário no admin
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Informações Pessoais', {'fields': ('phone_number', 'email', 'balance', 'bonus_balance')}),
        ('Produto de Investimento', {'fields': ('current_product', 'level_activation_date')}),
        ('Convites e Roleta', {'fields': ('my_invitation_code', 'referral_income', 'invited_by_code', 'can_spin_lucky_wheel', 'daily_spins_remaining', 'last_spin_date')}),
        ('Permissões', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Datas Importantes', {'fields': ('last_login', 'date_joined')}),
    )
    
    # Garante que 'password' e 'last_login' não sejam editáveis diretamente como texto
    readonly_fields = ('last_login', 'date_joined', 'my_invitation_code')


# Admin para Produto de Investimento
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('level_name', 'min_deposit_amount', 'daily_income', 'duration_days', 'order', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('level_name',)
    ordering = ('order',)


# Admin para Banco
@admin.register(Bank)
class BankAdmin(admin.ModelAdmin):
    list_display = ('name', 'account_name', 'iban', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'account_name', 'iban')


# Admin para Depósito
@admin.register(Deposit)
class DepositAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount', 'bank', 'status', 'timestamp')
    list_filter = ('status', 'bank', 'timestamp')
    search_fields = ('user__username', 'user__phone_number', 'bank__name')
    readonly_fields = ('timestamp',)

    # Ações personalizadas
    actions = ['approve_deposits', 'reject_deposits']

    def handle_deposit_approval_logic(self, deposit):
        """Função para gerenciar o pagamento da comissão de convite."""
        if deposit.user.invited_by_code:
            try:
                # Encontra o usuário que convidou
                referrer_user = CustomUser.objects.get(my_invitation_code=deposit.user.invited_by_code)
                
                # O bônus é de 15% sobre o valor do depósito
                referral_bonus = deposit.amount * 0.15
                
                # Adiciona o bônus ao saldo do usuário que convidou
                referrer_user.referral_income += referral_bonus
                referrer_user.balance += referral_bonus
                referrer_user.save()
            except CustomUser.DoesNotExist:
                # Se o usuário que convidou não for encontrado, apenas continua sem dar o bônus
                pass

    @admin.action(description='Marcar depósitos selecionados como Aprovado')
    def approve_deposits(self, request, queryset):
        with transaction.atomic():
            for deposit in queryset:
                if deposit.status == 'Pending':
                    deposit.status = 'Approved'
                    deposit.user.balance += deposit.amount
                    deposit.user.save()
                    deposit.save()
                    
                    # Chama a nova função para processar a comissão de convite
                    self.handle_deposit_approval_logic(deposit)
                    
        self.message_user(request, "Depósitos aprovados e saldo atualizado com sucesso.")

    @admin.action(description='Marcar depósitos selecionados como Rejeitado')
    def reject_deposits(self, request, queryset):
        with transaction.atomic():
            queryset.update(status='Rejected')
        self.message_user(request, "Depósitos rejeitados com sucesso.")


# Admin para Conta Bancária do Usuário
@admin.register(UserBankAccount)
class UserBankAccountAdmin(admin.ModelAdmin):
    list_display = ('user', 'bank_name', 'account_name', 'iban', 'is_active', 'created_at')
    list_filter = ('is_active', 'bank_name')
    search_fields = ('user__username', 'user__phone_number', 'bank_name', 'iban')
    readonly_fields = ('created_at',)


# Admin para Retirada
@admin.register(Withdrawal)
class WithdrawalAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount', 'amount_received', 'status', 'user_bank_account', 'timestamp')
    list_filter = ('status', 'timestamp')
    search_fields = ('user__username', 'user__phone_number', 'user_bank_account__iban')
    readonly_fields = ('timestamp', 'approved_at')

    # Ações personalizadas
    actions = ['approve_withdrawals', 'reject_withdrawals']

    @admin.action(description='Marcar retiradas selecionadas como Aprovado')
    def approve_withdrawals(self, request, queryset):
        with transaction.atomic():
            for withdrawal in queryset:
                if withdrawal.status == 'Pending':
                    withdrawal.status = 'Approved'
                    withdrawal.approved_at = timezone.now()
                    withdrawal.save()
        self.message_user(request, "Retiradas aprovadas com sucesso.")

    @admin.action(description='Marcar retiradas selecionadas como Rejeitado')
    def reject_withdrawals(self, request, queryset):
        with transaction.atomic():
            for withdrawal in queryset:
                if withdrawal.status == 'Pending':
                    withdrawal.status = 'Rejected'
                    withdrawal.user.balance += withdrawal.amount
                    withdrawal.user.save()
                    withdrawal.save()
        self.message_user(request, "Retiradas rejeitadas e saldos reembolsados com sucesso.")


# Admin para Tarefa
@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'is_completed', 'creation_date', 'completion_date', 'last_income_calculation_date')
    list_filter = ('is_completed', 'product')
    search_fields = ('user__username', 'user__phone_number', 'product__level_name')
    readonly_fields = ('creation_date', 'completion_date', 'last_income_calculation_date')
    actions = ['mark_as_completed']

    @admin.action(description='Marcar tarefas selecionadas como Concluídas')
    def mark_as_completed(self, request, queryset):
        with transaction.atomic():
            for task in queryset:
                if not task.is_completed:
                    task.is_completed = True
                    task.completion_date = timezone.now()
                    task.save()
        self.message_user(request, "Tarefas marcadas como concluídas.")


# Admin para Informações de Suporte
@admin.register(SupportInfo)
class SupportInfoAdmin(admin.ModelAdmin):
    list_display = ('whatsapp_number', 'telegram_username')
    def has_add_permission(self, request):
        return not SupportInfo.objects.exists()


# --- Admin para Roda da Sorte ---

@admin.register(LuckyWheelPrize)
class LuckyWheelPrizeAdmin(admin.ModelAdmin):
    list_display = ('value', 'weight', 'name', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('value', 'name')
    ordering = ('-value',)


@admin.register(LuckyWheelSpin)
class LuckyWheelSpinAdmin(admin.ModelAdmin):
    list_display = ('user', 'prize_won', 'spin_time', 'is_paid_spin')
    list_filter = ('is_paid_spin', 'spin_time')
    search_fields = ('user__username', 'user__phone_number', 'prize_won__value', 'prize_won__name')
    readonly_fields = ('spin_time',)
    