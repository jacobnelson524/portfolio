from django import forms
from django.contrib.auth.models import User
from .models import Profile, WatchParty, WatchPartyMovie

class UpdateAvatarForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['avatar']

class WatchPartyForm(forms.ModelForm):
    class Meta:
        model = WatchParty
        fields = ['name']

class WatchPartyMovieForm(forms.ModelForm):
    class Meta:
        model = WatchPartyMovie
        fields = ['genre', 'director', 'age_rating', 'year_range']
