from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [
    path('register/', views.register_page, name="register"),
    path('login/', views.login_page, name="login"),
    path('logout/', views.logout_page, name="logout"),
    path('profile/', views.profile, name="profile"),
    path('profile/<str:username>/', views.view_profile, name="view_profile"),
    path('change_avatar/', views.change_avatar, name="change_avatar"),
    path('react_to_movie/', views.react_to_movie, name="react_to_movie"),
    path('search_users/', views.search_users, name="search_users"),
    path('watchparty/create/', views.create_watch_party, name="watch_party_create"),
    path('watchparty/<int:party_id>/submit/', views.submit_movie_criteria, name="watch_party_submit"),
    path('watchparty/<int:party_id>/choose/', views.choose_movie, name="watch_party_choose"),
    path('watchparty/<int:party_id>/result/', views.watchparty_result, name="watchparty_result"),
    path('send_friend_request/<int:user_id>/', views.send_friend_request, name="send_friend_request"),
    path('accept_friend_request/<int:friendship_id>/', views.accept_friend_request, name="accept_friend_request"),
    path('reject_friend_request/<int:friendship_id>/', views.reject_friend_request, name="reject_friend_request"),
    path('remove_friend/<int:friendship_id>/', views.remove_friend, name="remove_friend"),
    path('friends/', views.friend_list, name="friend_list"),
    path('party/<int:party_id>/members/', views.party_members, name='party_members'),
    path('party/join/<int:party_id>/', views.join_party, name='join_party'),
    path('watchparty/<int:party_id>/check_status/', views.check_search_status, name='check_search_status'),
]
