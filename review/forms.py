# review/forms.py
from django import forms
from django.core.validators import FileExtensionValidator
from .models import PaymentTransaction

class PaymentUploadForm(forms.ModelForm):
    full_name = forms.CharField(max_length=255, required=True, widget=forms.TextInput(attrs={'placeholder': 'e.g. Juan Dela Cruz'}))
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'placeholder': 'name@example.com'}))
    desired_username = forms.CharField(max_length=150, required=False, help_text="Optional: If you don't have an account yet.")
    
    class Meta:
        model = PaymentTransaction
        fields = ['amount', 'uploaded_file']
        widgets = {
            'amount': forms.Select(choices=[
                (100, '₱100.00 - 1 Month Premium'),
                (600, '₱600.00 - 1 Year Premium (Save 50%)')
            ], attrs={'class': 'form-select'}),
        }
        
    def clean_uploaded_file(self):
        file = self.cleaned_data.get('uploaded_file')
        if file:
            if file.size > 5 * 1024 * 1024:  # 5MB limit
                raise forms.ValidationError("File size must be under 5MB.")
        return file
