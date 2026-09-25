from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from .models import User


class SchoolUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('email',)


class SchoolUserChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User
        fields = '__all__'
