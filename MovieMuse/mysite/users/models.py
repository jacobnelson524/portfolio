from django.db import models
from django.contrib.auth.models import User
from django_resized import ResizedImageField

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    avatar = ResizedImageField(size=[250, 250], default='default.png', upload_to='profile_images')

    def __str__(self):
        return self.user.username


class Movie(models.Model):
    imdb_id = models.CharField(max_length=20, unique=True)
    tmdb_id = models.CharField(max_length=20, blank=True, null=True)
    title = models.CharField(max_length=255)
    year = models.CharField(max_length=10)
    poster = models.URLField(max_length=500, blank=True, null=True)
    genre = models.CharField(max_length=255, blank=True, null=True)
    rated = models.CharField(max_length=20, blank=True, null=True)
    director = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"{self.title} ({self.year})"


class MovieReaction(models.Model):
    REACTION_CHOICES = [
        ('like', 'Like'),
        ('dislike', 'Dislike'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='movie_reactions')
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name='reactions')
    reaction_type = models.CharField(max_length=10, choices=REACTION_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        # Ensure a user can only have one reaction per movie
        unique_together = ['user', 'movie']
        
    def __str__(self):
        return f"{self.user.username} {self.reaction_type}d {self.movie.title}"


class Friendship(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
    ]
    
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_friendships')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_friendships')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['sender', 'receiver']
        
    def __str__(self):
        return f"{self.sender.username} -> {self.receiver.username} ({self.status})"

class WatchParty(models.Model):
    name = models.CharField(max_length=100)
    host = models.ForeignKey(User, on_delete=models.CASCADE, related_name='hosted_parties')
    members = models.ManyToManyField(User, related_name='watch_parties')
    created_at = models.DateTimeField(auto_now_add=True)
    search_initiated = models.BooleanField(default=False)

    def __str__(self):
        return self.name

class WatchPartyMovie(models.Model):
    party = models.ForeignKey(WatchParty, on_delete=models.CASCADE, related_name='movies')
    genre = models.CharField(max_length=100)
    director = models.CharField(max_length=100, blank=True, null=True)
    age_rating = models.CharField(max_length=10, blank=True, null=True)
    year_range = models.CharField(max_length=20, blank=True, null=True)

    def __str__(self):
        return f"{self.party.name} - {self.genre}"
