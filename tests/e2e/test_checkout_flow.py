"""E2E tests for services and authentication flows."""

import pytest
from playwright.sync_api import Page, expect


@pytest.mark.django_db
class TestCheckoutFlow:
    """Testes E2E do fluxo de serviços."""

    def test_home_page_loads(self, page: Page, base_url: str):
        """Home page carrega corretamente."""
        page.goto(base_url)
        expect(page.locator("h1")).to_be_visible()

    def test_services_list_page_loads(self, page: Page, base_url: str):
        """Lista de serviços carrega."""
        page.goto(f"{base_url}/servicos/")
        expect(page.locator("h1:has-text('Serviços')")).to_be_visible()


@pytest.mark.django_db
class TestAuthenticationFlow:
    """Testes E2E de autenticação."""

    def test_login_page_loads(self, page: Page, base_url: str):
        """Página de login carrega."""
        page.goto(f"{base_url}/social/login/")
        expect(page.locator("form")).to_be_visible()

    def test_signup_page_loads(self, page: Page, base_url: str):
        """Página de cadastro carrega."""
        page.goto(f"{base_url}/social/signup/")
        expect(page.locator("form")).to_be_visible()
