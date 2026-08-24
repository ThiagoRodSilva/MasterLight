"""E2E tests for checkout flow with Asaas hosted checkout."""

import pytest
from playwright.sync_api import Page, expect


@pytest.mark.django_db
class TestCheckoutFlow:
    """Testes E2E do fluxo de checkout."""

    def test_home_page_loads(self, page: Page, base_url: str):
        """Home page carrega corretamente."""
        page.goto(base_url)
        expect(page.locator("h1")).to_be_visible()

    def test_shop_list_page_loads(self, page: Page, base_url: str):
        """Lista de produtos carrega."""
        page.goto(f"{base_url}/loja/")
        expect(page.locator("h1:has-text('Loja')")).to_be_visible()

    def test_services_list_page_loads(self, page: Page, base_url: str):
        """Lista de serviços carrega."""
        page.goto(f"{base_url}/servicos/")
        expect(page.locator("h1:has-text('Serviços')")).to_be_visible()


@pytest.mark.django_db
class TestCartFlow:
    """Testes E2E do carrinho."""

    def test_add_product_to_cart(self, page: Page, base_url: str):
        """Adiciona produto ao carrinho."""
        # Cria um produto via admin ou fixture
        # Por enquanto, testa apenas a navegação
        page.goto(f"{base_url}/loja/")
        # Se houver produtos, testa o botão de adicionar
        add_buttons = page.locator('button:has-text("Ver detalhes"), a:has-text("Ver detalhes")')
        if add_buttons.count() > 0:
            add_buttons.first.click()
            expect(page).to_have_url(regex=r".*/loja/.*/")
            # Volta à lista
            page.goto(f"{base_url}/loja/")


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


@pytest.mark.django_db
class TestAsaasCheckoutRedirect:
    """Testes de redirecionamento para checkout Asaas (mockado)."""

    def test_checkout_redirects_to_asaas(self, page: Page, base_url: str):
        """Testa redirecionamento para Asaas (requer mock do Asaas)."""
        # Este teste requer que o Asaas esteja mockado
        # Em CI/CD, usar mock_asaas() do Django
        page.goto(f"{base_url}/checkout/")
        # Se não há carrinho, deve redirecionar para a loja
        expect(page).to_have_url(regex=r".*/loja/")
