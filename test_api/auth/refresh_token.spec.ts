import { test, expect } from '@playwright/test';
import path from 'path';
import { readCsv, updateCsvActual } from '../utils/csvReader';
import { generateDefectReports, DefectItem } from '../utils/defectReport';

const csvFilePath = path.join(__dirname, 'refresh_token.csv');
const cases = readCsv<{
  test_id: string;
  refresh_token_type: string;
  expected: string;
  actual?: string;
  note: string;
}>(csvFilePath);

const REFRESH_ENDPOINT = process.env.REFRESH_ENDPOINT || '/api/v1/auth/refresh';
const LOGIN_ENDPOINT = process.env.LOGIN_ENDPOINT || '/api/v1/auth/login';

let validRefreshToken = '';
const actualResults = new Map<string, string>();
const defects: DefectItem[] = [];

test.beforeAll(async ({ request }) => {
  const email = process.env.TEST_EMAIL || 'buithinhu1408@gmail.com';
  const password = process.env.TEST_PASSWORD || 'Abcd1234@';

  const loginRes = await request.post(LOGIN_ENDPOINT, {
    data: { email, password },
  });

  const cookies = loginRes.headers()['set-cookie'] || '';
  const match = cookies.match(/refresh_token=([^;]+)/);
  if (match) {
    validRefreshToken = match[1];
  }
});

for (const tc of cases) {
  test(`${tc.test_id} - ${tc.note}`, async ({ request }) => {
    const headers: Record<string, string> = {};

    if (tc.refresh_token_type === 'VALID_FROM_LOGIN' && validRefreshToken) {
      headers['Cookie'] = `refresh_token=${validRefreshToken}`;
    } else if (tc.refresh_token_type === 'INVALID_VALUE') {
      headers['Cookie'] = `refresh_token=invalid_refresh_token_xyz_12345`;
    } else if (tc.refresh_token_type === 'EXPIRED_OR_REVOKED') {
      headers['Cookie'] = `refresh_token=revoked_token_abcdef`;
    }

    const res = await request.post(REFRESH_ENDPOINT, {
      headers,
    });

    const text = await res.text();
    let body: unknown = text;
    try {
      body = JSON.parse(text);
    } catch {}

    await test.info().attach('response', {
      body: JSON.stringify(
        {
          test_id: tc.test_id,
          note: tc.note,
          headers,
          actual_status: res.status(),
          expected_status: tc.expected,
          response_body: body,
        },
        null,
        2
      ),
      contentType: 'application/json',
    });

    const expectedStatus = Number(tc.expected.match(/\d{3}/)?.[0] || tc.expected);
    const isPassed = res.status() === expectedStatus;

    actualResults.set(
      tc.test_id,
      isPassed
        ? `Status ${res.status()} (PASSED)`
        : `Status ${res.status()} (FAILED: Expected ${expectedStatus})`
    );

    if (!isPassed) {
      defects.push({
        testId: tc.test_id,
        feature: 'Auth - Refresh Token',
        summary: tc.note,
        endpoint: REFRESH_ENDPOINT,
        headers,
        payload: {},
        expectedStatus,
        actualStatus: res.status(),
        responseBody: body,
        explanation: `API Refresh Token phản hồi HTTP ${res.status()} khác với kỳ vọng ${expectedStatus}.`,
      });
    }

    const failureMessage = [
      `\n❌ TESTCASE FAILED: [${tc.test_id}] ${tc.note}`,
      `• Endpoint:        ${REFRESH_ENDPOINT}`,
      `• Headers:         ${JSON.stringify(headers)}`,
      `• Expected Status: ${expectedStatus}`,
      `• Actual Status:   ${res.status()}`,
      `• Response Body:   ${JSON.stringify(body, null, 2)}`,
    ].join('\n');

    expect(res.status(), failureMessage).toBe(expectedStatus);
  });
}

test.afterAll(async () => {
  updateCsvActual(csvFilePath, actualResults);
  if (defects.length > 0) {
    generateDefectReports(defects, 'Defect_Report_AUTH_REFRESH_TOKEN.md');
  }
});
