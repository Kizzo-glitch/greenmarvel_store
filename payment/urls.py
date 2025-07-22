from django.urls import path
from . import views

urlpatterns = [
    #path('payment_success', views.payment_success, name='payment_success'),
    path('checkout', views.checkout, name='checkout'),
    path('billing_info', views.billing_info, name="billing_info"),
    path('process_order', views.process_order, name="process_order"),
    
    #For admin
    path('orders/<int:pk>', views.orders, name='orders'),
    path('not_shipped_dash', views.not_shipped_dash, name="not_shipped_dash"),
    path('shipped_dash', views.shipped_dash, name="shipped_dash"),
    path('successful_payments/', views.successful_payments, name='successful_payments'),
    #For customers
    path('payment_success/', views.payment_success, name='payment_success'),
    path('payment_cancel/', views.payment_cancel, name='payment_cancel'),
    path('payment_notify/', views.payment_notify, name='payment_notify'),

    path('order-history/', views.order_history, name='order_history'),
    path('track-order/<int:order_id>/', views.track_order, name='track_order'),
    
    #path('upload_payment/', views.upload_payment, name="upload_payment"),
]