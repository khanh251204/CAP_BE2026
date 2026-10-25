import { APIRequestContext } from '@playwright/test';

let cachedToken: string = '';

/**
 * Đăng nhập và lấy Auth Bearer Token dùng chung cho các test suite
 */
export async function getAuthToken(request: APIRequestContext): Promise<string> {
  if (cachedToken) {
    return cachedToken;
  }

  const email = process.env.TEST_EMAIL || 'buithinhu1408@gmail.com';
  const password = process.env.TEST_PASSWORD || 'Abcd1234@';
  const loginEndpoint = process.env.LOGIN_ENDPOINT || '/api/v1/auth/login';

  const res = await request.post(loginEndpoint, {
    data: { email, password },
  });

  const text = await res.text();
  let body: any = {};
  try {
    body = JSON.parse(text);
  } catch {}

  let token = body?.token || body?.accessToken || body?.data?.token || '';
  if (!token) {
    const setCookie = res.headers()['set-cookie'] || '';
    const match = setCookie.match(/access_token=([^;]+)/);
    if (match) {
      token = match[1];
    }
  }

  if (token) {
    cachedToken = token;
  } else {
    console.warn(`[authHelper] Không thể lấy auth token (Status: ${res.status()}). Response: ${text}`);
  }

  return token;
}
