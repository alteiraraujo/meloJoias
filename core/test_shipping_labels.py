from django.test import TestCase, Client as Browser
from django.urls import reverse
from django.utils import timezone

from .forms import ClientForm, SenderForm
from .models import Client, Consignment, SenderProfile, StockMovement


ADDRESS = {'postal_code': '01001-000', 'street': 'Praça da Sé', 'number': '100',
           'complement': 'Sala 2', 'neighborhood': 'Sé', 'city': 'São Paulo', 'state': 'SP'}


class ShippingLabelTests(TestCase):
    def setUp(self):
        self.reseller = Client.objects.create(name='Maria da Silva', address='Endereço antigo preservado',
                                               document='DOCUMENTO-PRIVADO', phone='11999990000')
        self.consignment = Consignment.objects.create(client=self.reseller, due_date=timezone.localdate())
        self.url = reverse('shipping_label', args=[self.consignment.pk])
        self.print_url = reverse('shipping_label_print', args=[self.consignment.pk])

    def test_missing_addresses_block_print_and_preserve_legacy_address(self):
        self.assertRedirects(self.client.get(self.print_url), self.url)
        response = self.client.get(self.url)
        self.assertContains(response, 'Endereço antigo preservado')
        self.assertContains(response, 'Complete no cadastro da revendedora')
        self.assertFalse(response.context['label_ready'])
        self.assertFalse(SenderProfile.objects.exists())
        self.assertContains(self.client.get(reverse('consignment_print', args=[self.consignment.pk])), 'Endereço antigo preservado')

    def test_edit_address_returns_to_label_and_updates_packing_slip(self):
        edit = reverse('entity_edit', args=['clients', self.reseller.pk]) + f'?return_to_consignment={self.consignment.pk}'
        data = {'name': self.reseller.name, 'address': self.reseller.address, 'active': 'on', **ADDRESS}
        self.assertRedirects(self.client.post(edit, data), self.url)
        self.reseller.refresh_from_db()
        self.assertEqual(self.reseller.address, 'Endereço antigo preservado')
        self.assertIn('São Paulo - SP', self.reseller.mailing_address)
        self.assertContains(self.client.get(reverse('consignment_print', args=[self.consignment.pk])), '01001-000')
        self.assertFalse(self.client.get(self.url).context['label_ready'])

    def test_sender_reused_and_print_contains_only_shipping_information(self):
        for field, value in ADDRESS.items():
            setattr(self.reseller, field, value)
        self.reseller.save()
        self.assertRedirects(self.client.post(self.url, {'name': 'Melo Joias', **ADDRESS}), self.url)
        self.assertTrue(self.client.get(self.url).context['label_ready'])
        response = self.client.get(self.print_url)
        for value in ['Maria da Silva', 'Melo Joias', 'São Paulo', '01001-000', 'USO EXCLUSIVO DOS CORREIOS', 'DESTINATÁRIO', 'REMETENTE']:
            self.assertContains(response, value)
        self.assertNotContains(response, 'DOCUMENTO-PRIVADO')
        self.assertNotContains(response, 'Endereço antigo preservado')
        self.assertNotContains(response, 'R$')
        other = Consignment.objects.create(client=self.reseller, due_date=timezone.localdate())
        self.assertTrue(self.client.get(reverse('shipping_label', args=[other.pk])).context['label_ready'])
        self.client.post(self.url, {'name': 'Melo Joias origem', **ADDRESS})
        self.assertEqual(SenderProfile.objects.count(), 1)
        self.assertFalse(StockMovement.objects.exists())

    def test_validation_csrf_and_html_escaping(self):
        for cep in ['123', '123456789', 'abcdefgh', '１２３４５６７８']:
            self.assertFalse(SenderForm(data={'name': 'Origem', **ADDRESS, 'postal_code': cep}).is_valid())
        self.assertFalse(SenderForm(data={'name': 'Origem', **ADDRESS, 'state': 'ZZ'}).is_valid())
        self.assertFalse(SenderForm(data={'name': 'Origem', **ADDRESS, 'number': ''}).is_valid())
        self.assertTrue(SenderForm(data={'name': 'Origem', **ADDRESS, 'number': 'S/N', 'postal_code': '01001000'}).is_valid())
        self.assertEqual(Browser(enforce_csrf_checks=True).post(self.url, {'name': 'Origem', **ADDRESS}).status_code, 403)
        form = ClientForm(data={'name': '<script>test</script>', **ADDRESS}, instance=self.reseller)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.client.post(self.url, {'name': 'Origem', **ADDRESS})
        response = self.client.get(self.print_url)
        self.assertContains(response, '&lt;script&gt;test&lt;/script&gt;')
        self.assertNotContains(response, '<script>test</script>')

    def test_invalid_sender_update_preserves_saved_profile(self):
        self.client.post(self.url, {'name': 'Origem', **ADDRESS})
        response = self.client.post(self.url, {'name': 'Origem alterada', **ADDRESS, 'postal_code': '12'})
        self.assertFalse(response.context['label_ready'])
        self.assertEqual(SenderProfile.objects.get(pk=1).name, 'Origem')
