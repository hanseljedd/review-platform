from django.contrib.auth import authenticate, login, logout, get_user_model
from django.shortcuts import render, redirect
from django.urls import reverse
from django_ratelimit.decorators import ratelimit

User = get_user_model()

@ratelimit(key='ip', rate='10/m', block=True) # Brute force protection
def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username") or ""
        password = request.POST.get("password") or ""
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            next_url = request.GET.get("next") or reverse("review:landing")
            return redirect(next_url)
        return render(request, "review/auth/login.html", {"error": "Invalid credentials"})
    return render(request, "review/auth/login.html")

@ratelimit(key='ip', rate='5/h', block=True) # Registration spam protection
def register_view(request):
    """
    Registration is currently disabled. Accounts are created by Admin only.
    """
    return render(request, "review/error.html", {"message": "Registration is currently invite-only. Please contact the administrator."})

    # if request.method == "POST":
    #     username = request.POST.get("username") or ""
    #     password = request.POST.get("password") or ""
    #     email = request.POST.get("email") or ""
    #     if not username or not password:
    #         return render(request, "review/auth/register.html", {"error": "Username and password are required"})
    #     if User.objects.filter(username=username).exists():
    #         return render(request, "review/auth/register.html", {"error": "Username already taken"})
    #     
    #     # TODO: Add password strength validation here
    #     user = User.objects.create_user(username=username, password=password, email=email)
    #     login(request, user)
    #     return redirect("review:landing")
    # return render(request, "review/auth/register.html")

def logout_view(request):
    logout(request)
    return redirect("review:landing")
