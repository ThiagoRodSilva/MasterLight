"""Testes do ReconcilePaymentsView (cron Vercel)."""

import json
from unittest import mock

from django.test import Client, TestCase, override_settings
from django.urls import reverse


@override_settings(CRON_SECRET="test-secret")
class TestReconcilePaymentsView(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse("payments-reconcile")

    def test_post_without_token_returns_403(self):
        response = self.client.post(self.url, data=json.dumps({}), content_type="application/json")
        assert response.status_code == 403

    def test_post_with_wrong_token_returns_403(self):
        response = self.client.post(
            self.url,
            data=json.dumps({}),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer wrong-secret",
        )
        assert response.status_code == 403

    def test_post_with_correct_token_returns_200(self):
        with mock.patch("apps.payments.views.call_command") as mock_call:
            response = self.client.post(
                self.url,
                data=json.dumps({}),
                content_type="application/json",
                HTTP_AUTHORIZATION="Bearer test-secret",
            )
        assert response.status_code == 200
        mock_call.assert_called_once_with("sync_payments")

    def test_post_with_empty_cron_secret_returns_403(self):
        with self.settings(CRON_SECRET=""):
            response = self.client.post(
                self.url,
                data=json.dumps({}),
                content_type="application/json",
                HTTP_AUTHORIZATION="Bearer test-secret",
            )
        assert response.status_code == 403

    def test_post_without_cron_secret_setting_returns_403(self):
        with self.settings(CRON_SECRET=None):
            response = self.client.post(
                self.url,
                data=json.dumps({}),
                content_type="application/json",
                HTTP_AUTHORIZATION="Bearer anything",
            )
        assert response.status_code == 403

    def test_post_command_exception_returns_500(self):
        with mock.patch("apps.payments.views.call_command", side_effect=Exception("fail")):
            response = self.client.post(
                self.url,
                data=json.dumps({}),
                content_type="application/json",
                HTTP_AUTHORIZATION="Bearer test-secret",
            )
        assert response.status_code == 500
