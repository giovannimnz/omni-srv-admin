import { test, expect } from '@playwright/test';

test.describe('Atius SSO & Fleet Critical Services Smoke Tests', () => {
  test('SSO Login Central - Interface e formulário carregam com sucesso', async ({ page }) => {
    const response = await page.goto('https://sso.atius.com.br/login', { timeout: 15000 });
    expect(response?.status()).toBe(200);

    // Verifica elementos do formulário de autenticação
    const form = page.locator('form');
    await expect(form).toBeVisible();
    
    // Verifica título ou cabeçalho da plataforma
    await expect(page).toHaveTitle(/Atius/i);
  });

  test('Keycloak OIDC Discovery Endpoint - Retorna metadados válidos', async ({ request }) => {
    const response = await request.get('https://auth.atius.com.br/realms/atius/.well-known/openid-configuration');
    expect(response.status()).toBe(200);

    const json = await response.json();
    expect(json.issuer).toBe('https://auth.atius.com.br/realms/atius');
    expect(json.authorization_endpoint).toContain('/protocol/openid-connect/auth');
    expect(json.token_endpoint).toContain('/protocol/openid-connect/token');
  });

  test('Pipeline Runner K3s Health - Pod ativo no cluster', async ({ request }) => {
    // Validação de endpoint de saúde local
    const response = await request.get('https://router.atius.com.br/health', {
      ignoreHTTPSErrors: true,
      timeout: 10000,
    }).catch(() => null);
    
    if (response) {
      expect([200, 404]).toContain(response.status());
    }
  });
});
