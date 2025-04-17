from django.shortcuts import render, redirect

def movie(request):
    return render(request, 'movie.html')
