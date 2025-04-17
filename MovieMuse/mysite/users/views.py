from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.models import User
from django.db.models import Q
from .models import Movie, MovieReaction, Friendship
from .forms import UpdateAvatarForm, WatchPartyForm, WatchPartyMovieForm
from .models import WatchParty, WatchPartyMovie
import random
from .forms import UpdateAvatarForm
from collections import Counter
import requests
from django.conf import settings
from datetime import datetime
from django.views.decorators.http import require_GET
from django.http import HttpResponse
from django.urls import reverse
TMDB_API_KEY = "9069e9679489f7393d82ea5f5af0e201"
def get_tmdb_id_from_imdb(imdb_id):
    try:
        response = requests.get(
            f"https://api.themoviedb.org/3/find/{imdb_id}",
            params={"api_key": TMDB_API_KEY, "external_source": "imdb_id"}
        )
        response.raise_for_status()
        results = response.json().get("movie_results", [])
        return str(results[0]["id"]) if results else None
    except requests.RequestException:
        return None

def login_page(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect('movie')
        else:
            messages.info(request, 'Try again! Username or password is incorrect.')

    context = {}
    return render(request, 'users/login.html', context)

def logout_page(request):
    logout(request)
    return redirect('users:login')

def register_page(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('movie')
    else:
        form = UserCreationForm()
    return render(request,"users/register.html",{"form": form})

@login_required
def profile(request):
    # Get the user's liked and disliked movies
    liked_reactions = MovieReaction.objects.filter(
        user=request.user, 
        reaction_type='like'
    ).select_related('movie')
    
    disliked_reactions = MovieReaction.objects.filter(
        user=request.user, 
        reaction_type='dislike'
    ).select_related('movie')
    
    # Get friend requests
    pending_requests = Friendship.objects.filter(
        receiver=request.user,
        status='pending'
    ).select_related('sender')
    
    # Get accepted friends
    friends = Friendship.objects.filter(
        (Q(sender=request.user) | Q(receiver=request.user)),
        status='accepted'
    )
    
    friend_users = []
    for friendship in friends:
        if friendship.sender == request.user:
            friend_users.append(friendship.receiver)
        else:
            friend_users.append(friendship.sender)
    
    context = {
        'liked_movies': [reaction.movie for reaction in liked_reactions],
        'disliked_movies': [reaction.movie for reaction in disliked_reactions],
        'pending_requests': pending_requests,
        'friends': friend_users
    }
    
    return render(request, 'users/profile.html', context)

@login_required
def view_profile(request, username):
    user = get_object_or_404(User, username=username)
    
    # Check if the viewed user is a friend
    is_friend = Friendship.objects.filter(
        (Q(sender=request.user, receiver=user) | Q(sender=user, receiver=request.user)),
        status='accepted'
    ).exists()
    
    # Get friend status
    friendship_status = None
    friendship_id = None
    
    try:
        friendship = Friendship.objects.get(
            (Q(sender=request.user, receiver=user) | Q(sender=user, receiver=request.user))
        )
        friendship_status = friendship.status
        friendship_id = friendship.id
    except Friendship.DoesNotExist:
        pass
    
    # Get the user's liked and disliked movies (only visible to friends)
    liked_movies = []
    disliked_movies = []
    
    if is_friend or request.user == user:
        liked_reactions = MovieReaction.objects.filter(
            user=user, 
            reaction_type='like'
        ).select_related('movie')
        
        disliked_reactions = MovieReaction.objects.filter(
            user=user, 
            reaction_type='dislike'
        ).select_related('movie')
        
        liked_movies = [reaction.movie for reaction in liked_reactions]
        disliked_movies = [reaction.movie for reaction in disliked_reactions]
    
    context = {
        'profile_user': user,
        'liked_movies': liked_movies,
        'disliked_movies': disliked_movies,
        'is_friend': is_friend,
        'friendship_status': friendship_status,
        'friendship_id': friendship_id,
        'is_self': request.user == user
    }
    
    return render(request, 'users/view_profile.html', context)

@login_required
def change_avatar(request):
    user_profile = request.user.profile

    if request.method == "POST":
        form = UpdateAvatarForm(request.POST, request.FILES, instance=user_profile)
        if form.is_valid():
            form.save()
            return redirect("users:profile")  # Redirect after a successful update
    else:
        form = UpdateAvatarForm(instance=user_profile)

    return render(request, "users/change_avatar.html", {"form": form})  # Ensure GET requests return a response

@require_POST
@login_required
def react_to_movie(request):
    imdb_id = request.POST.get('imdb_id')
    title = request.POST.get('title')
    year = request.POST.get('year')
    poster = request.POST.get('poster')
    genre = request.POST.get('genre')
    rated = request.POST.get('rated')
    director = request.POST.get('director')
    reaction_type = request.POST.get('reaction_type')
    
    # Ensure reaction type is valid
    if reaction_type not in ['like', 'dislike']:
        return JsonResponse({'status': 'error', 'message': 'Invalid reaction type'}, status=400)
    
    # Get or create the movie
    movie, created = Movie.objects.get_or_create(
        imdb_id=imdb_id,
        defaults={
            'title': title,
            'year': year,
            'poster': poster,
            'genre': genre,
            'rated': rated,
            'director': director
        }
    )

    if not movie.tmdb_id:
        tmdb_id = get_tmdb_id_from_imdb(imdb_id)
        if tmdb_id:
            movie.tmdb_id = tmdb_id
            movie.save()
    
    # Check if the user already has a reaction to this movie
    try:
        reaction = MovieReaction.objects.get(user=request.user, movie=movie)
        
        # If the reaction is the same, remove it (toggle off)
        if reaction.reaction_type == reaction_type:
            reaction.delete()
            return JsonResponse({
                'status': 'success',
                'action': 'removed',
                'message': f'Removed {reaction_type} for {movie.title}'
            })
        else:
            # If the reaction is different, update it
            reaction.reaction_type = reaction_type
            reaction.save()
            return JsonResponse({
                'status': 'success',
                'action': 'updated',
                'message': f'Updated to {reaction_type} for {movie.title}'
            })
            
    except MovieReaction.DoesNotExist:
        # Create a new reaction
        MovieReaction.objects.create(
            user=request.user,
            movie=movie,
            reaction_type=reaction_type
        )
        return JsonResponse({
            'status': 'success',
            'action': 'added',
            'message': f'Added {reaction_type} for {movie.title}'
        })

@login_required
def search_users(request):
    query = request.GET.get('q', '')
    
    if query:
        # Search for users by username
        users = User.objects.filter(username__icontains=query).exclude(id=request.user.id)
        
        # Get friendship status for each user
        user_data = []
        for user in users:
            friendship_status = None
            friendship_id = None
            
            try:
                friendship = Friendship.objects.get(
                    (Q(sender=request.user, receiver=user) | Q(sender=user, receiver=request.user))
                )
                friendship_status = friendship.status
                friendship_id = friendship.id
            except Friendship.DoesNotExist:
                pass
                
            user_data.append({
                'user': user,
                'friendship_status': friendship_status,
                'friendship_id': friendship_id
            })
    else:
        user_data = []
    
    return render(request, 'users/search_users.html', {'user_data': user_data, 'query': query})

@login_required
def send_friend_request(request, user_id):
    receiver = get_object_or_404(User, id=user_id)
    
    # Check if friendship already exists
    if Friendship.objects.filter(
        (Q(sender=request.user, receiver=receiver) | Q(sender=receiver, receiver=request.user))
    ).exists():
        messages.info(request, 'A friendship request already exists with this user.')
        return redirect('users:search_users')
    
    # Create friendship request
    Friendship.objects.create(
        sender=request.user,
        receiver=receiver,
        status='pending'
    )
    
    messages.success(request, f'Friend request sent to {receiver.username}!')
    return redirect('users:search_users')

@login_required
def accept_friend_request(request, friendship_id):
    friendship = get_object_or_404(Friendship, id=friendship_id, receiver=request.user)
    friendship.status = 'accepted'
    friendship.save()
    
    messages.success(request, f'You are now friends with {friendship.sender.username}!')
    return redirect('users:profile')

@login_required
def reject_friend_request(request, friendship_id):
    friendship = get_object_or_404(Friendship, id=friendship_id, receiver=request.user)
    friendship.status = 'rejected'
    friendship.save()
    
    messages.info(request, f'Friend request from {friendship.sender.username} declined.')
    return redirect('users:profile')

@login_required
def remove_friend(request, friendship_id):
    # First try to get the friendship
    friendship = get_object_or_404(Friendship, id=friendship_id, status='accepted')
    
    # Check if the user is part of this friendship
    if friendship.sender != request.user and friendship.receiver != request.user:
        messages.error(request, "You don't have permission to remove this friendship.")
        return redirect('users:friend_list')
    
    other_user = friendship.receiver if friendship.sender == request.user else friendship.sender
    friendship.delete()
    
    messages.info(request, f'You are no longer friends with {other_user.username}.')
    return redirect('users:friend_list')

@login_required
def friend_list(request):
    # Get accepted friends
    friendships = Friendship.objects.filter(
        (Q(sender=request.user) | Q(receiver=request.user)),
        status='accepted'
    ).select_related('sender', 'receiver')
    
    friends = []
    for friendship in friendships:
        if friendship.sender == request.user:
            friends.append({
                'user': friendship.receiver,
                'friendship_id': friendship.id
            })
        else:
            friends.append({
                'user': friendship.sender,
                'friendship_id': friendship.id
            })
    
    return render(request, 'users/friend_list.html', {'friends': friends})

@login_required
def create_watch_party(request):
    if request.method == "POST":
        form = WatchPartyForm(request.POST)
        if form.is_valid():
            watch_party = form.save(commit=False)
            watch_party.host = request.user
            watch_party.save()
            watch_party.members.add(request.user)
            return redirect('users:watch_party_submit', party_id=watch_party.id)  # 🔥 FIXED HERE
    else:
        form = WatchPartyForm()
    return render(request, "users/watchparty_create.html", {"form": form})

@login_required
def submit_movie_criteria(request, party_id):
    party = get_object_or_404(WatchParty, id=party_id)
    if request.method == "POST":
        form = WatchPartyMovieForm(request.POST)
        if form.is_valid():
            movie = form.save(commit=False)
            movie.party = party
            movie.save()
            return redirect('users:watch_party_choose', party_id=party.id)  # 🔥 Fixed redirect
    else:
        form = WatchPartyMovieForm()
    return render(request, "users/watchparty_submit.html", {"form": form, "party": party})

@login_required
def choose_movie(request, party_id):
    party = get_object_or_404(WatchParty, id=party_id)
    
    if request.method == "POST" and "initiate_search" in request.POST:
        # Store that search was initiated
        party.search_initiated = True
        party.save()
        return redirect('users:watchparty_result', party_id=party.id)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        movies = list(party.movies.all())
        selected_movie = random.choice(movies) if movies else None
        return JsonResponse({
            "selected_movie": {
                "genre": selected_movie.genre if selected_movie else None,
                "director": selected_movie.director if selected_movie else None,
                "age_rating": selected_movie.age_rating if selected_movie else None,
            }
        })
    
    return redirect('users:watchparty_result', party_id=party.id)

@login_required
def watchparty_result(request, party_id):
    party = get_object_or_404(WatchParty, id=party_id)
    
    # Collect all members' preferences
    all_liked = []
    all_disliked = []
    member_preferences = {}
    
    for member in party.members.all():
        reactions = MovieReaction.objects.filter(user=member).select_related('movie')
        liked = [r.movie for r in reactions if r.reaction_type == 'like']
        disliked = [r.movie for r in reactions if r.reaction_type == 'dislike']
        
        # Analyze individual preferences
        individual_prefs = {
            'genres': Counter(),
            'years': [],
            'ratings': Counter(),
            'disliked_genres': Counter()
        }
        
        # Process liked movies
        for movie in liked:
            if movie.genre:
                genres = [g.strip().lower() for g in movie.genre.split(',')]
                individual_prefs['genres'].update(genres)
            if movie.year:
                try:
                    year = int(movie.year)
                    individual_prefs['years'].append(year)
                except ValueError:
                    pass
            if movie.rated:
                individual_prefs['ratings'][movie.rated] += 1
        
        # Process disliked movies
        for movie in disliked:
            if movie.genre:
                genres = [g.strip().lower() for g in movie.genre.split(',')]
                individual_prefs['disliked_genres'].update(genres)
        
        # Store analyzed preferences
        member_preferences[member] = {
            'top_genres': [g for g, _ in individual_prefs['genres'].most_common(3)],
            'year_range': (
                min(individual_prefs['years']) if individual_prefs['years'] else None,
                max(individual_prefs['years']) if individual_prefs['years'] else None
            ),
            'ratings': [r for r, _ in individual_prefs['ratings'].most_common(2)],
            'disliked_genres': list(individual_prefs['disliked_genres'].keys()),
            'liked_movies': liked,
            'disliked_movies': disliked
        }
        
        all_liked.extend(liked)
        all_disliked.extend(disliked)
    
    # Get combined rated movie IDs
    rated_imdb_ids = {m.imdb_id for m in all_liked + all_disliked}
    rated_tmdb_ids = {m.tmdb_id for m in all_liked + all_disliked if m.tmdb_id}
    rated_movie_ids = rated_imdb_ids | rated_tmdb_ids
    
    # Get group recommendation
    if all_liked:  # Only try if at least one member has liked movies
        recommendation_result = get_guaranteed_recommendation(all_liked, all_disliked, rated_movie_ids)
    else:
        recommendation_result = {
            'movie': get_quality_fallback(),
            'is_fallback': True,
            'reasons': {'fallback': 'No liked movies in the group to base recommendations on'}
        }
    
    # Analyze group preferences
    preferences = analyze_preferences(all_liked, all_disliked)
    
    context = {
        "party": party,
        "member_preferences": member_preferences,
        "recommended_movie": recommendation_result['movie'],
        "is_fallback": recommendation_result['is_fallback'],
        "preferred_genres": [g for g, _ in preferences['genres'].most_common(3) if g not in preferences['disliked_genres']],
        "disliked_genres": list(preferences['disliked_genres'].keys()),
        "year_range": (
            int(sum(preferences['years'])/len(preferences['years']))-5 if preferences['years'] else datetime.now().year-5,
            int(sum(preferences['years'])/len(preferences['years']))+5 if preferences['years'] else datetime.now().year+5
        ),
        "preferred_ratings": [r for r, _ in preferences['ratings'].most_common(2)],
        "match_reasons": recommendation_result.get('reasons', {}),
        "now": datetime.now()
    }
    return render(request, "users/watchparty_result.html", context)

def get_guaranteed_recommendation(liked_movies, disliked_movies, rated_movie_ids):
    """Returns at least one recommendation with reasoning data"""
    # Get all IDs the user has rated (both IMDB and TMDB)
    rated_imdb_ids = {m.imdb_id for m in liked_movies + disliked_movies}
    rated_tmdb_ids = {m.tmdb_id for m in liked_movies + disliked_movies if m.tmdb_id}
    rated_movie_ids = rated_imdb_ids | rated_tmdb_ids  # Merge both ID sets

    if not liked_movies:
        return {
            'movie': get_quality_fallback(),
            'is_fallback': True,
            'reasons': {'fallback': 'No liked movies to base recommendations on'}
        }
    
    preferences = analyze_preferences(liked_movies, disliked_movies)
    current_year = datetime.now().year
    
    # Try 4 levels of increasingly relaxed searches
    for level in range(4):
        recommendation = find_tmdb_recommendation(
            preferences, 
            rated_movie_ids,
            strict=(level == 0),
            relaxation_level=level
        )
        if recommendation:
            # Add year context to reasons
            release_year = int(recommendation['year']) if recommendation['year'].isdigit() else None
            if release_year:
                if 'year' not in recommendation['match_reasons']:
                    if release_year >= current_year - 3:
                        recommendation['match_reasons']['year'] = f"Recent release ({release_year})"
                    else:
                        recommendation['match_reasons']['year'] = f"From {release_year}"
            
            return {
                'movie': recommendation,
                'is_fallback': (level > 0),
                'reasons': recommendation['match_reasons']
            }
    
    # Final fallback with proper year context
    fallback = get_quality_fallback()
    release_year = int(fallback['year']) if fallback['year'].isdigit() else None
    if release_year:
        if release_year >= current_year - 3:
            fallback['match_reasons']['fallback'] = 'Popular recent release'
        else:
            fallback['match_reasons']['fallback'] = f'Popular film from {release_year}'
    
    return {
        'movie': fallback,
        'is_fallback': True,
        'reasons': fallback['match_reasons']
    }

def analyze_preferences(liked_movies, disliked_movies):
    """Analyzes user's liked/disliked movies to determine preferences"""
    preferences = {
        'genres': Counter(),
        'years': [],
        'ratings': Counter(),
        'disliked_genres': Counter(),
        'disliked_directors': Counter()
    }
    
    # Analyze liked movies
    for movie in liked_movies:
        if movie.genre:
            genres = [g.strip().lower() for g in movie.genre.split(',')]
            preferences['genres'].update(genres)
        if movie.year:
            try:
                year = int(movie.year)
                preferences['years'].append(year)
            except ValueError:
                pass
        if movie.rated:
            preferences['ratings'][movie.rated] += 1
    
    # Analyze disliked movies
    for movie in disliked_movies:
        if movie.genre:
            genres = [g.strip().lower() for g in movie.genre.split(',')]
            preferences['disliked_genres'].update(genres)
        if movie.director:
            directors = [d.strip() for d in movie.director.split(',')]
            preferences['disliked_directors'].update(directors)
    
    return preferences

def find_tmdb_recommendation(preferences, rated_movie_ids, strict=True, relaxation_level=0):
    """Finds recommendations using TMDB API with validation and reasoning"""
    params = build_tmdb_params(preferences, strict, relaxation_level)
    current_year = datetime.now().year
    
    try:
        response = requests.get(
            "https://api.themoviedb.org/3/discover/movie",
            params=params,
            timeout=5
        )
        response.raise_for_status()
        results = response.json().get('results', [])
        
        for movie in results:
            # Skip if TMDB ID or IMDB ID is already rated
            if (str(movie.get('id')) in rated_movie_ids or 
                str(movie.get('imdb_id')) in rated_movie_ids):
                continue
                
            details = get_tmdb_movie_details(movie['id'])
            if not details or not is_valid_movie(movie, details):
                continue
                
            # Initialize match reasons
            match_reasons = {}
            movie_genres = {g['name'].lower(): g['id'] for g in details.get('genres', [])}
            directors = [d['name'] for d in details.get('credits', {}).get('crew', []) 
                        if d['job'] == 'Director']
            release_year = int(movie.get('release_date', '')[:4]) if movie.get('release_date') else None
            
            # Check genre matches
            matched_genres = [g for g in preferences['genres'] if g in movie_genres]
            if matched_genres:
                match_reasons['genres'] = [g.title() for g in matched_genres[:3]]
            
            # Check year match with context
            if release_year:
                if preferences['years']:
                    avg_year = sum(preferences['years']) / len(preferences['years'])
                    year_diff = abs(release_year - avg_year)
                    if year_diff <= 5 + (relaxation_level * 3):
                        if release_year >= current_year - 3:
                            match_reasons['year'] = f"Recent release ({release_year})"
                        else:
                            match_reasons['year'] = f"From {release_year} (matches your preferred era)"
                else:
                    if release_year >= current_year - 3:
                        match_reasons['year'] = f"Recent release ({release_year})"
                    else:
                        match_reasons['year'] = f"From {release_year}"
            
            # Check rating match
            content_rating = get_content_rating(details)
            if content_rating in preferences['ratings']:
                match_reasons['rating'] = content_rating
            
            # Check director match
            for director in directors:
                if director in preferences['genres']:
                    match_reasons['director'] = director
                    break
            
            # Skip if contains blacklisted elements (unless in fallback mode)
            if strict or relaxation_level < 3:
                if any(dg in movie_genres for dg in preferences['disliked_genres']):
                    continue
                if any(dd in directors for dd in preferences['disliked_directors']):
                    continue
            
            movie_result = format_movie_result(movie, details)
            movie_result['match_reasons'] = match_reasons
            return movie_result
            
    except requests.RequestException:
        pass
    
    return None

def build_tmdb_params(preferences, strict, relaxation_level):
    """Builds TMDB API parameters with relaxation levels"""
    params = {
        "api_key": TMDB_API_KEY,
        "language": "en-US",
        "sort_by": "popularity.desc",
        "include_adult": False,
        "page": 1
    }
    
    # Year range with relaxation
    if preferences['years']:
        avg_year = sum(preferences['years']) / len(preferences['years'])
        year_range = 5 + (relaxation_level * 3)
        params["primary_release_date.gte"] = f"{int(avg_year - year_range)}-01-01"
        params["primary_release_date.lte"] = f"{int(avg_year + year_range)}-12-31"
    else:
        params["primary_release_date.gte"] = f"{datetime.now().year - (5 + relaxation_level * 2)}-01-01"
    
    # Genres with relaxation
    if strict or relaxation_level < 2:
        top_genres = [
            g for g, _ in preferences['genres'].most_common() 
            if g not in preferences['disliked_genres']
        ]
        if top_genres:
            genre_map = get_genre_map()
            genre_ids = [str(genre_map[g]) for g in top_genres[:3 - relaxation_level] if g in genre_map]
            if genre_ids:
                params["with_genres"] = ",".join(genre_ids)
    
    # Age rating (strict mode only)
    if strict and preferences['ratings']:
        cert_map = {'G': 'G', 'PG': 'PG', 'PG-13': 'PG-13', 'R': 'R', 'NC-17': 'NC-17'}
        top_rating = preferences['ratings'].most_common(1)[0][0]
        if top_rating in cert_map:
            params["certification_country"] = 'US'
            params["certification"] = cert_map[top_rating]
    
    return params

def is_valid_movie(movie_data, details):
    """Validates movie meets all quality criteria"""
    # Basic TMDB checks
    if not movie_data.get('title') or not movie_data.get('release_date'):
        return False
    if movie_data.get('vote_count', 0) < 50:
        return False
    if movie_data.get('adult', False):
        return False
    
    # Convert to OMDb-like structure for validation
    fake_omdb = {
        'Genre': ', '.join([g['name'] for g in details.get('genres', [])]),
        'Rated': get_content_rating(details),
        'Director': ', '.join([d['name'] for d in details.get('credits', {}).get('crew', []) 
                   if d['job'] == 'Director'][:3]) or 'N/A'
    }
    
    # Replicate movie.html validation
    if ('short' in fake_omdb['Genre'].lower() or 
        fake_omdb['Rated'] == 'N/A' or 
        fake_omdb['Director'] == 'N/A'):
        return False
        
    # Additional quality checks
    if not details.get('overview') or len(details.get('overview', '').split()) < 10:
        return False
        
    return True

def get_content_rating(details):
    """Extracts US content rating from TMDB data"""
    try:
        us_releases = [r for r in details.get('release_dates', {}).get('results', []) 
                      if r.get('iso_3166_1') == 'US']
        if us_releases and us_releases[0].get('release_dates'):
            return us_releases[0]['release_dates'][0].get('certification', 'N/A')
    except Exception:
        pass
    return 'N/A'

def get_tmdb_movie_details(movie_id):
    """Gets detailed movie info from TMDB"""
    try:
        response = requests.get(
            f"https://api.themoviedb.org/3/movie/{movie_id}",
            params={
                "api_key": TMDB_API_KEY,
                "append_to_response": "credits,genres,release_dates"
            },
            timeout=3
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        return None

def format_movie_result(movie, details):
    """Formats movie data for template with all needed fields"""
    directors = [d['name'] for d in details.get('credits', {}).get('crew', []) 
                if d['job'] == 'Director']
    release_year = movie.get('release_date', '')[:4] if movie.get('release_date') else 'N/A'
    
    return {
        'tmdb_id': movie['id'],
        'title': movie.get('title', 'Unknown Title'),
        'year': release_year,
        'poster': f"https://image.tmdb.org/t/p/w500{movie['poster_path']}" if movie.get('poster_path') else None,
        'genre': ', '.join([g['name'] for g in details.get('genres', [])][:3]),
        'rating': movie.get('vote_average', 0),
        'overview': movie.get('overview', 'No description available'),
        'director': ', '.join(directors[:2]) if directors else 'Unknown Director',
        'content_rating': get_content_rating(details),
        'match_reasons': {}  # To be filled by find_tmdb_recommendation
    }

def get_quality_fallback():
    """Returns a high-quality fallback meeting all validation"""
    params = {
        "api_key": TMDB_API_KEY,
        "sort_by": "popularity.desc",
        "vote_count.gte": 1000,
        "vote_average.gte": 6.0,
        "page": 1
    }
    
    try:
        response = requests.get(
            "https://api.themoviedb.org/3/discover/movie",
            params=params,
            timeout=3
        )
        if response.status_code == 200:
            results = response.json().get('results', [])
            for movie in results:
                details = get_tmdb_movie_details(movie['id'])
                if details and is_valid_movie(movie, details):
                    return format_movie_result(movie, details)
    except requests.RequestException:
        pass
    
    # Ultimate fallback if all else fails
    return {
        'title': "Critically Acclaimed Film",
        'year': datetime.now().year,
        'poster': None,
        'genre': "Drama",
        'rating': 7.5,
        'overview': "A highly-rated popular movie we think you'll enjoy",
        'director': "Award-Winning Director",
        'content_rating': "PG-13",
        'match_reasons': {'fallback': 'Highly-rated film'}
    }

def get_genre_map():
    """Returns mapping of genre names to TMDB IDs"""
    return {
        'action': 28, 'adventure': 12, 'animation': 16, 'comedy': 35,
        'crime': 80, 'documentary': 99, 'drama': 18, 'family': 10751,
        'fantasy': 14, 'history': 36, 'horror': 27, 'music': 10402,
        'mystery': 9648, 'romance': 10749, 'science fiction': 878,
        'thriller': 53, 'war': 10752, 'western': 37
    }

@login_required
def join_party(request, party_id):
    party = get_object_or_404(WatchParty, id=party_id)
    if request.user not in party.members.all():
        party.members.add(request.user)
        messages.success(request, f"You've joined {party.name}!")
    return redirect('users:watch_party_submit', party_id=party.id)

@require_GET
@login_required
def party_members(request, party_id):
    """HTMX endpoint for live member updates"""
    party = get_object_or_404(WatchParty, id=party_id)
    return render(request, 'users/_member_list.html', {'party': party})

@login_required
@require_GET
def check_search_status(request, party_id):
    party = get_object_or_404(WatchParty, id=party_id)
    if party.search_initiated:
        return HttpResponse(
            status=204, 
            headers={'HX-Redirect': reverse('users:watchparty_result', args=[party.id])}
        )
    return HttpResponse(status=200)

def analyze_individual_preferences(member):
    """Analyzes a single member's movie preferences"""
    reactions = MovieReaction.objects.filter(user=member).select_related('movie')
    liked_movies = [r.movie for r in reactions if r.reaction_type == 'like']
    disliked_movies = [r.movie for r in reactions if r.reaction_type == 'dislike']
    
    # Initialize preferences dictionary
    preferences = {
        'genres': Counter(),
        'years': [],
        'ratings': Counter(),
        'disliked_genres': Counter(),
        'liked_movies': liked_movies,
        'disliked_movies': disliked_movies
    }
    
    # Analyze liked movies
    for movie in liked_movies:
        if movie.genre:
            genres = [g.strip().lower() for g in movie.genre.split(',')]
            preferences['genres'].update(genres)
        if movie.year:
            try:
                year = int(movie.year)
                preferences['years'].append(year)
            except ValueError:
                pass
        if movie.rated:
            preferences['ratings'][movie.rated] += 1
    
    # Analyze disliked movies
    for movie in disliked_movies:
        if movie.genre:
            genres = [g.strip().lower() for g in movie.genre.split(',')]
            preferences['disliked_genres'].update(genres)
    
    return preferences
