# -*- coding: utf-8 -*-
# microsof_2025_platform/core/models.py

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone
from decimal import Decimal
import random
import re

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction

# CustomUser Manager para adicionar métodos personalizados e sobrescrever create_user
class CustomUserManager(BaseUserManager):
    """
    Gerenciador de modelos personalizado para o CustomUser.
    Permite a criação de usuários e superusuários de forma consistente,
    incluindo a normalização do número de telefone e a geração de códigos de convite.
    """
    def create_user(self, username, password=None, **extra_fields):
        if not username:
            raise ValueError('O número de telefone é obrigatório.')
        
        phone_number_cleaned_match = re.match(r'^(?:\+244|0)?(9\d{8})$', username)
        if not phone_number_cleaned_match:
            raise ValueError("Formato de número de telefone inválido para criação de usuário.")
            
        normalized_phone_number_for_db = phone_number_cleaned_match.group(1)
        
        user = self.model(username=normalized_phone_number_for_db, phone_number=normalized_phone_number_for_db, **extra_fields)
        user.set_password(password)
        
        if not user.my_invitation_code:
            user.my_invitation_code = self.generate_unique_invitation_code()

        user.save(using=self._db)
        return user

    def create_superuser(self, username, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
            
        return self.create_user(username, password, **extra_fields)

    def generate_unique_invitation_code(self):
        length = 10
        characters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        while True:
            code = ''.join(random.choice(characters) for i in range(length))
            if not self.filter(my_invitation_code=code).exists():
                return code

# Modelo de Usuário Personalizado
class CustomUser(AbstractUser):
    """
    Modelo de usuário personalizado que herda de AbstractUser.
    Adiciona campos específicos da plataforma como saldo, nível, código de convite, etc.
    """
    phone_number = models.CharField(max_length=15, unique=True, verbose_name="Número de Telefone")
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name="Saldo")
    bonus_balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name="Saldo Bônus")
    
    current_product = models.ForeignKey(
        'Product',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Produto de Investimento Atual"
    )
    
    level_activation_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Data de Ativação do Nível"
    )
    my_invitation_code = models.CharField(max_length=20, unique=True, blank=True, null=True, verbose_name="Meu Código de Convite")
    invited_by_code = models.CharField(max_length=20, blank=True, null=True, verbose_name="Convidado Pelo Código")
    referral_income = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name="Ganhos de Convite")
    can_spin_lucky_wheel = models.BooleanField(default=False, verbose_name="Pode Rodar Roleta da Sorte")
    daily_spins_remaining = models.IntegerField(default=0, verbose_name="Giros Diários Restantes")
    last_spin_date = models.DateField(null=True, blank=True, verbose_name="Última Data de Giro")

    objects = CustomUserManager()

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = [] 

    def __str__(self):
        return self.username 

    class Meta:
        verbose_name = "Usuário"
        verbose_name_plural = "Usuários"
        
    def save(self, *args, **kwargs):
        is_new_user = self._state.adding
        
        if is_new_user and not self.my_invitation_code:
            self.my_invitation_code = CustomUser.objects.generate_unique_invitation_code()

        # A lógica de subsídio de convite foi removida daqui
        # e movida para um signal do modelo de Depósito para ser mais seguro.

        super().save(*args, **kwargs)

# NOVO MODELO: UserProfile para dados do perfil e banco principal
class UserProfile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='profile', verbose_name="Usuário")
    full_name = models.CharField(max_length=255, blank=True, null=True, verbose_name="Nome Completo")
    bank_name = models.CharField(max_length=100, blank=True, null=True, verbose_name="Nome do Banco Principal")
    iban = models.CharField(max_length=34, blank=True, null=True, verbose_name="IBAN Principal")

    def __str__(self):
        return f"Perfil de {self.user.username}"

    class Meta:
        verbose_name = "Perfil do Usuário"
        verbose_name_plural = "Perfis dos Usuários"

@receiver(post_save, sender=CustomUser)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=CustomUser)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()

# Produto de Investimento
class Product(models.Model):
    level_name = models.CharField(max_length=50, unique=True, verbose_name="Nome do Nível (Ex: VIP 1)")
    min_deposit_amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Valor Mínimo de Depósito")
    daily_income = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Renda Diária")
    duration_days = models.IntegerField(default=30, verbose_name="Duração em Dias")
    order = models.IntegerField(default=0, verbose_name="Ordem de Exibição")
    is_active = models.BooleanField(default=True, verbose_name="Ativo")

    def __str__(self):
        return self.level_name

    class Meta:
        verbose_name = "Produto de Investimento"
        verbose_name_plural = "Produtos de Investimento"
        ordering = ['order']

# Modelo para Bancos Disponíveis para Depósito
class Bank(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="Nome do Banco")
    account_name = models.CharField(max_length=150, verbose_name="Nome do Titular da Conta")
    iban = models.CharField(max_length=34, verbose_name="IBAN da Conta")
    is_active = models.BooleanField(default=True, verbose_name="Ativo para Depósito")
    
    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Banco para Depósito"
        verbose_name_plural = "Bancos para Depósito"

# Modelo para registrar Depósitos
class Deposit(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pendente'),
        ('Approved', 'Aprovado'),
        ('Rejected', 'Rejeitado'),
    ]
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, verbose_name="Usuário")
    bank = models.ForeignKey(Bank, on_delete=models.SET_NULL, null=True, verbose_name="Banco Selecionado")
    amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Valor do Depósito")
    proof_image = models.ImageField(upload_to='deposit_proofs/', blank=True, null=True, verbose_name="Comprovativo")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Pending', verbose_name="Status")
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="Data/Hora")

    def __str__(self):
        return f"Depósito de {self.user.username} - Kz {self.amount} ({self.status})"

    class Meta:
        verbose_name = "Depósito"
        verbose_name_plural = "Depósitos"
        ordering = ['-timestamp']

# --- NOVO SIGNAL PARA PROCESSAR A LÓGICA DE RECOMPENSA APÓS APROVAÇÃO DO DEPÓSITO ---
@receiver(post_save, sender=Deposit)
def update_user_balance_on_deposit_approval(sender, instance, created, **kwargs):
    # Verifica se o depósito foi aprovado e não é um novo objeto
    if instance.status == 'Approved' and not created:
        # Busca o estado anterior do objeto no banco de dados para evitar reprocessamento
        try:
            old_instance = sender.objects.get(pk=instance.pk)
            # Apenas processa se o status mudou de 'Pending' para 'Approved'
            if old_instance.status == 'Pending' and instance.status == 'Approved':
                # Adiciona o valor do depósito ao saldo principal do usuário
                user = instance.user
                user.balance += instance.amount
                user.save(update_fields=['balance'])
                
                # Lógica de recompensa por indicação (15% sobre o valor do depósito)
                if user.invited_by_code:
                    try:
                        referrer = CustomUser.objects.get(my_invitation_code=user.invited_by_code)
                        referral_bonus = instance.amount * Decimal('0.15') # 15% do valor depositado
                        
                        # Usa uma transação atômica para garantir que a atualização de saldo seja segura
                        with transaction.atomic():
                            referrer.balance += referral_bonus
                            referrer.referral_income += referral_bonus
                            referrer.save(update_fields=['balance', 'referral_income'])
                            print(f"Bônus de {referral_bonus} Kz adicionado a {referrer.username} pela indicação de {user.username}.")
                            
                    except CustomUser.DoesNotExist:
                        print(f"Usuário com código de indicação {user.invited_by_code} não encontrado.")
        except sender.DoesNotExist:
            # Caso o objeto anterior não seja encontrado (pode acontecer), não faz nada.
            pass

# Modelo para as contas bancárias do usuário (para retirada)
class UserBankAccount(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='bank_accounts', verbose_name="Usuário")
    bank_name = models.CharField(max_length=100, verbose_name="Nome do Banco")
    account_name = models.CharField(max_length=150, verbose_name="Nome do Titular da Conta")
    iban = models.CharField(max_length=34, unique=True, verbose_name="IBAN")
    is_active = models.BooleanField(default=True, verbose_name="Ativo")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Data de Criação")

    def __str__(self):
        return f"{self.user.username} - {self.bank_name} ({self.iban})"

    class Meta:
        verbose_name = "Conta Bancária do Usuário"
        verbose_name_plural = "Contas Bancárias do Usuário"

# Modelo para registrar Retiradas
class Withdrawal(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pendente'),
        ('Approved', 'Aprovado'),
        ('Rejected', 'Rejeitado'),
    ]
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, verbose_name="Usuário")
    user_bank_account = models.ForeignKey(UserBankAccount, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Conta Bancária de Destino")
    amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Valor Solicitado")
    tax_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'), verbose_name="Percentagem da Taxa")
    amount_received = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Valor a Receber")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Pending', verbose_name="Status")
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="Data/Hora")
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name="Aprovado Em")

    def __str__(self):
        return f"Retirada de {self.user.username} - Kz {self.amount} ({self.status})"

    class Meta:
        verbose_name = "Retirada"
        verbose_name_plural = "Retiradas"
        ordering = ['-timestamp']

# Modelo para Tarefas, agora referenciando o modelo 'Product'
class Task(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, verbose_name="Usuário")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="Produto de Investimento")
    is_completed = models.BooleanField(default=False, verbose_name="Concluída")
    creation_date = models.DateTimeField(auto_now_add=True, verbose_name="Data de Criação")
    completion_date = models.DateTimeField(null=True, blank=True, verbose_name="Data de Conclusão")
    last_income_calculation_date = models.DateField(null=True, blank=True, verbose_name="Último Cálculo de Renda")

    def __str__(self):
        return f"Tarefa de {self.user.username} - Nível {self.product.level_name} ({'Concluída' if self.is_completed else 'Pendente'})"

    class Meta:
        verbose_name = "Tarefa"
        verbose_name_plural = "Tarefas"
        ordering = ['-creation_date']

# Modelo para Informações de Suporte (Contatos e Regras)
class SupportInfo(models.Model):
    whatsapp_number = models.CharField(max_length=20, blank=True, null=True, verbose_name="Número de WhatsApp")
    telegram_username = models.CharField(max_length=50, blank=True, null=True, verbose_name="Nome de Usuário Telegram")
    platform_info = models.TextField(blank=True, null=True, verbose_name="Informações da Plataforma")
    platform_rules = models.TextField(blank=True, null=True, verbose_name="Regras da Plataforma")

    def __str__(self):
        return "Informações de Suporte da Plataforma"
    
    class Meta:
        verbose_name = "Informação de Suporte"
        verbose_name_plural = "Informações de Suporte"

# --- Novos Modelos para Roda da Sorte ---

class LuckyWheelPrize(models.Model):
    value = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Valor do Prêmio (Kz)")
    weight = models.IntegerField(default=1, verbose_name="Peso/Probabilidade (maior = mais chance)")
    is_active = models.BooleanField(default=True, verbose_name="Ativo")
    name = models.CharField(max_length=100, blank=True, null=True, verbose_name="Nome do Prêmio (Opcional)")
    daily_spins_allowed = models.IntegerField(default=1, verbose_name="Giros Diários Permitidos")

    def __str__(self):
        return f"Kz {self.value} (Peso: {self.weight})"

    class Meta:
        verbose_name = "Prêmio da Roda da Sorte"
        verbose_name_plural = "Prêmios da Roda da Sorte"
        ordering = ['-value']

class LuckyWheelSpin(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, verbose_name="Usuário")
    prize_won = models.ForeignKey(LuckyWheelPrize, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Prêmio Ganho")
    spin_time = models.DateTimeField(auto_now_add=True, verbose_name="Data/Hora do Giro")
    is_paid_spin = models.BooleanField(default=False, verbose_name="Giro Pago (se aplicável)")
    
    def __str__(self):
        prize_str = self.prize_won.name if self.prize_won and self.prize_won.name else f"Kz {self.prize_won.value}" if self.prize_won else "Nenhum Prêmio"
        return f"Giro de {self.user.username} - Ganhou: {prize_str}"

    class Meta:
        verbose_name = "Giro da Roda da Sorte"
        verbose_name_plural = "Giros da Roda da Sorte"
        ordering = ['-spin_time']
        