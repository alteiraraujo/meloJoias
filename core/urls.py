from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('cadastros/<slug:entity>/', views.entity_list, name='entity_list'),
    path('cadastros/<slug:entity>/novo/', views.entity_form, name='entity_create'),
    path('cadastros/<slug:entity>/<int:pk>/editar/', views.entity_form, name='entity_edit'),
    path('cadastros/<slug:entity>/<int:pk>/excluir/', views.entity_delete, name='entity_delete'),
    path('clientes/<int:pk>/', views.client_detail, name='client_detail'),
    path('consignacoes/', views.consignment_list, name='consignment_list'),
    path('consignacoes/nova/', views.consignment_create, name='consignment_create'),
    path('consignacoes/<int:pk>/', views.consignment_detail, name='consignment_detail'),
    path('consignacoes/<int:pk>/editar/', views.consignment_edit, name='consignment_edit'),
    path('consignacoes/<int:pk>/acao/', views.consignment_action, name='consignment_action'),
    path('consignacoes/<int:pk>/recebimento/', views.payment_create, name='payment_create'),
    path('consignacoes/<int:pk>/imprimir/', views.consignment_print, name='consignment_print'),
    path('itens/<int:pk>/acerto/', views.item_settle, name='item_settle'),
    path('produtos/<int:pk>/estoque/', views.product_stock, name='product_stock'),
    path('produtos/<int:pk>/etiqueta/', views.product_label, name='product_label'),
    path('produtos/<int:pk>/codigo.svg', views.product_barcode, name='product_barcode'),
    path('backups/', views.backups, name='backups'),
    path('backups/baixar/', views.backup_download, name='backup_download'),
]
