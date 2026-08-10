"""Testes do bootstrap de Site/SocialApp (social_bootstrap + commando admin)."""

import os
from unittest import mock

from allauth.socialaccount.models import SocialApp
from django.contrib.sites.models import Site
from django.core.management import call_command
from django.test import TestCase

from apps.core.social_bootstrap import bootstrap_site, bootstrap_social_apps


class TestBootstrapSite(TestCase):
    def test_default_domain_and_name(self):
        bootstrap_site()
        site = Site.objects.get(id=1)
        assert site.domain == "localhost:8000"
        assert site.name == "PlataformaVendas"

    def test_env_overrides_defaults(self):
        env = {
            "DJANGO_SITE_DOMAIN": "eletrica.test",
            "DJANGO_SITE_NAME": "MasterLight",
        }
        with mock.patch.dict(os.environ, env, clear=False):
            bootstrap_site()
        site = Site.objects.get(id=1)
        assert site.domain == "eletrica.test"
        assert site.name == "MasterLight"

    def test_updates_existing_site(self):
        Site.objects.create(domain="antigo.test", name="Antigo")
        bootstrap_site()
        assert Site.objects.filter(id=1, domain="localhost:8000").exists()


class TestBootstrapSocialApps(TestCase):
    def test_no_apps_without_env(self):
        bootstrap_social_apps()
        assert not SocialApp.objects.exists()

    def test_creates_google_app_from_env(self):
        env = {
            "GOOGLE_CLIENT_ID": "id-google",
            "GOOGLE_CLIENT_SECRET": "segredo-google",
        }
        with mock.patch.dict(os.environ, env, clear=False):
            bootstrap_social_apps()
        app = SocialApp.objects.get(provider="google")
        assert app.client_id == "id-google"
        assert app.secret == "segredo-google"
        assert app.name == "Google"
        assert list(app.sites.all()) == [Site.objects.get(id=1)]

    def test_creates_facebook_app_from_env(self):
        env = {
            "FACEBOOK_CLIENT_ID": "id-fb",
            "FACEBOOK_CLIENT_SECRET": "segredo-fb",
        }
        with mock.patch.dict(os.environ, env, clear=False):
            bootstrap_social_apps()
        assert SocialApp.objects.filter(provider="facebook").exists()

    def test_updates_existing_app_idempotently(self):
        app = SocialApp.objects.create(provider="google")
        app.sites.add(Site.objects.get(id=1))
        env = {
            "GOOGLE_CLIENT_ID": "novo-id",
            "GOOGLE_CLIENT_SECRET": "novo-segredo",
        }
        with mock.patch.dict(os.environ, env, clear=False):
            bootstrap_social_apps()
        app.refresh_from_db()
        assert app.client_id == "novo-id"
        assert app.secret == "novo-segredo"
        assert SocialApp.objects.filter(provider="google").count() == 1

    def test_partial_env_ignored(self):
        env = {"GOOGLE_CLIENT_ID": "so-id"}
        with mock.patch.dict(os.environ, env, clear=False):
            bootstrap_social_apps()
        assert not SocialApp.objects.exists()

    def test_no_site_returns_quietly(self):
        Site.objects.all().delete()
        env = {
            "GOOGLE_CLIENT_ID": "id",
            "GOOGLE_CLIENT_SECRET": "sec",
        }
        with mock.patch.dict(os.environ, env, clear=False):
            bootstrap_social_apps()
        assert not SocialApp.objects.exists()


class TestBootstrapSocialCommand(TestCase):
    def test_command_creates_site_and_apps(self):
        env = {
            "DJANGO_SITE_DOMAIN": "teste.test",
            "GOOGLE_CLIENT_ID": "id-cmd",
            "GOOGLE_CLIENT_SECRET": "sec-cmd",
        }
        with mock.patch.dict(os.environ, env, clear=False):
            call_command("bootstrap_social")
        site = Site.objects.get(id=1)
        assert site.domain == "teste.test"
        assert SocialApp.objects.filter(provider="google").exists()
