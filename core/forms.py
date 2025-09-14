# luxottica_org/core/forms.py

from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.core.validators import RegexValidator
from django.forms import PasswordInput
# Importa todos os modelos necessários, incluindo UserProfile
from .models import CustomUser, Bank, Deposit, UserBankAccount, Product, Withdrawal, UserProfile
import re # Usado para normalizar o número de telefone

# Formulário de criação de usuário personalizado (para registro)
class CustomUserCreationForm(forms.ModelForm):
    # Campo 'username' que será o número de telefone
    username = forms.CharField(
        label="Número de Telefone",
        max_length=15,
        validators=[
            RegexValidator(
                regex=r'^(?:\+244|0)?(9\d{8})$',
                message="O número de telefone deve ser um número angolano válido (ex: 9XXXXXXXX ou +2449XXXXXXXX)."
            )
        ],
        help_text="Ex: 9XXXXXXXX",
        widget=forms.TextInput(attrs={'placeholder': 'Ex: 9XXXXXXXX'})
    )
    password = forms.CharField(
        label="Senha",
        widget=PasswordInput(attrs={'placeholder': 'Sua senha'})
    )
    # Campo para o código de convite opcional
    invited_by_code = forms.CharField(
        label="Código de Convite (Opcional)",
        max_length=20,
        required=False,
        help_text="Se você foi convidado, insira o código",
        widget=forms.TextInput(attrs={'placeholder': 'Se você foi convidado, insira o código'})
    )

    class Meta:
        model = CustomUser
        fields = ('username', 'password', 'invited_by_code',)

    # Normaliza e valida o número de telefone
    def clean_username(self):
        username = self.cleaned_data['username']
        # Remove o prefixo (+244 ou 0) e pega apenas os 9 dígitos
        match = re.match(r'^(?:\+244|0)?(9\d{8})$', username)
        if not match:
            raise forms.ValidationError("Formato de número de telefone inválido.")
        
        normalized_username = match.group(1)
        
        # Verifica se o número de telefone já existe no banco de dados
        if CustomUser.objects.filter(phone_number=normalized_username).exists():
            raise forms.ValidationError("Este número de telefone já está registrado.")
        
        return normalized_username

    # Sobrescreve o método save para definir a senha e o número de telefone
    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        user.phone_number = self.cleaned_data["username"] 
        
        invited_by_code = self.cleaned_data.get('invited_by_code')
        if invited_by_code:
            try:
                # Verifica se o código de convite existe
                if not CustomUser.objects.filter(my_invitation_code=invited_by_code).exists():
                    raise forms.ValidationError("Código de convite inválido ou inexistente.")
                user.invited_by_code = invited_by_code
            except forms.ValidationError as e:
                self.add_error('invited_by_code', e)
                if commit:
                    raise
        
        if commit:
            user.save()
        return user


# Formulário de autenticação personalizado (para login)
class CustomAuthenticationForm(AuthenticationForm):
    username = forms.CharField(
        label="Número de Telefone",
        max_length=15,
        widget=forms.TextInput(attrs={'autofocus': True, 'placeholder': 'Seu número de telefone'})
    )
    password = forms.CharField(
        label="Senha",
        strip=False,
        widget=PasswordInput(attrs={'placeholder': 'Sua senha'})
    )

    # Normaliza o número de telefone antes de tentar o login
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if username:
            match = re.match(r'^(?:\+244|0)?(9\d{8})$', username)
            if match:
                return match.group(1)
        return username

# Formulário para atualização do perfil do usuário (nome e dados bancários principais)
class UserProfileUpdateForm(forms.ModelForm):
    """
    Formulário para o usuário editar seu perfil, incluindo nome completo e dados bancários principais.
    Este formulário interage com o modelo UserProfile.
    """
    class Meta:
        model = UserProfile
        fields = ['full_name', 'bank_name', 'iban']
        labels = {
            'full_name': 'Nome Completo',
            'bank_name': 'Nome do Banco Principal',
            'iban': 'IBAN Principal',
        }
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Seu nome completo'}),
            'bank_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome do banco'}),
            'iban': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'IBAN'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'


# Formulário para alteração de senha
class UserPasswordChangeForm(PasswordChangeForm):
    """
    Formulário para o usuário alterar sua senha.
    Herdado do PasswordChangeForm padrão do Django.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})
        
        self.fields['old_password'].label = 'Senha Antiga'
        self.fields['new_password1'].label = 'Nova Senha'
        self.fields['new_password2'].label = 'Confirme a Nova Senha'


# Formulário para Depósito
class DepositForm(forms.ModelForm):
    bank = forms.ModelChoiceField(
        queryset=Bank.objects.filter(is_active=True),
        empty_label="Selecione um banco",
        label="Banco de Destino",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    class Meta:
        model = Deposit
        fields = ('bank', 'amount', 'proof_image',)
        widgets = {
            'amount': forms.NumberInput(attrs={'placeholder': 'Valor do depósito'}),
        }
        labels = {
            'amount': 'Valor do Depósito (Kz)',
            'proof_image': 'Comprovativo de Depósito (Opcional)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['amount'].widget.attrs.update({'class': 'form-control'})
        self.fields['proof_image'].widget.attrs.update({'class': 'form-control-file'})


# Formulário para Adicionar Conta Bancária do Usuário (contas adicionais para retirada)
class UserBankAccountForm(forms.ModelForm):
    class Meta:
        model = UserBankAccount
        fields = ('bank_name', 'account_name', 'iban',)
        widgets = {
            'bank_name': forms.TextInput(attrs={'placeholder': 'Nome do Banco'}),
            'account_name': forms.TextInput(attrs={'placeholder': 'Nome do Titular da Conta'}),
            'iban': forms.TextInput(attrs={'placeholder': 'Número de IBAN'}),
        }
        labels = {
            'bank_name': 'Nome do Banco',
            'account_name': 'Nome do Titular da Conta',
            'iban': 'IBAN',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'

# Formulário para Retirada
class WithdrawalForm(forms.ModelForm):
    user_bank_account = forms.ModelChoiceField(
        queryset=UserBankAccount.objects.none(),
        empty_label="Selecione sua conta bancária",
        label="Conta Bancária de Destino",
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    class Meta:
        model = Withdrawal
        fields = ('amount', 'user_bank_account',)
        widgets = {
            'amount': forms.NumberInput(attrs={'placeholder': 'Valor a Retirar'}),
        }
        labels = {
            'amount': 'Valor da Retirada (Kz)',
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if self.user:
            self.fields['user_bank_account'].queryset = self.user.bank_accounts.filter(is_active=True)
        
        self.fields['amount'].widget.attrs.update({'class': 'form-control'})
    
    # Validação para verificar se o saldo é suficiente
    def clean_amount(self):
        amount = self.cleaned_data['amount']
        if self.user.balance < amount:
            raise forms.ValidationError("Saldo insuficiente para esta retirada.")
        return amount

# Formulário para Selecionar Nível de Investimento
class SelectProductForm(forms.Form):
    product = forms.ModelChoiceField(
        queryset=Product.objects.filter(is_active=True).order_by('order'),
        empty_label="Selecione um nível de investimento",
        label="Escolha seu Nível de Investimento (VIP)",
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product'].widget.attrs.update({'class': 'form-control'})
