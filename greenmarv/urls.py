from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('home2/', views.home2, name='home2'),
    path('index/', views.index, name='index'),   
    path('login/', views.login_user, name='login'),
    path('logout/', views.logout_user, name='logout'),
    path('register/', views.register_user, name='register'),
    path('update_user/', views.update_user, name='update_user'),
    path('update_info/', views.update_info, name='update_info'),
    path('update_password/', views.update_password, name='update_password'),
    path('product/<int:pk>', views.product, name='product'),
    path('shop/', views.shop_all, name='shop'),
    path('search/', views.search, name='search'),
]
