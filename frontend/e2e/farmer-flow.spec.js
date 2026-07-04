import { expect, test } from '@playwright/test'

const json = (body) => ({
  status: 200,
  contentType: 'application/json',
  body: JSON.stringify(body),
})

test.beforeEach(async ({ context, page }) => {
  await context.grantPermissions(['geolocation'])
  await context.setGeolocation({ latitude: 14.75, longitude: 78.55 })
  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url())
    if (url.pathname.endsWith('/auth/me')) {
      return route.fulfill(json({ ok: true, user: { id: 1, full_name: 'Field Tester', email: 'field@example.com', role: 'farmer' } }))
    }
    if (url.pathname.endsWith('/dashboard')) {
      return route.fulfill(json({ ok: true, counts: { analysis_count: 0, weather_count: 0, chat_count: 0 }, recent: [] }))
    }
    if (url.pathname.startsWith('/api/history')) {
      return route.fulfill(json({ ok: true, history: [] }))
    }
    if (url.pathname.endsWith('/predict')) {
      return route.fulfill(json({
        ok: true,
        analysis_id: 42,
        disease: { disease: 'Brown Spot', confidence: 0.82, method: 'custom_model', needs_retake: false },
        severity: { level: 'Moderate', advice: 'Confirm field spread.' },
        fertilizer: { fertiliser: ['Use a soil test before correcting nutrients.'], immediate_action: 'Confirm symptoms.' },
        weather: { location: 'Proddatur', temperature: 29, humidity: 81, wind_speed: 2.1, description: 'Cloudy', source: 'live' },
        location_advisories: ['High local humidity may favor fungal disease pressure.'],
        symptoms_confirmed: true,
        requires_agronomist_review: false,
        review_reasons: [],
      }))
    }
    return route.fulfill(json({ ok: true }))
  })
})

test('farmer can complete a GPS-aware guided diagnosis', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Upload' }).click()
  await page.locator('input[type=file]').setInputFiles({
    name: 'leaf.png',
    mimeType: 'image/png',
    buffer: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=', 'base64'),
  })
  await page.getByRole('combobox').filter({ has: page.locator('option[value="Tillering"]') }).selectOption('Tillering')
  await page.getByPlaceholder(/Describe lesion shape/i).fill('Oval brown lesions on lower leaves')
  await page.getByRole('checkbox').check()
  await page.getByRole('button', { name: 'Analyze crop' }).click()

  await expect(page.getByText('Brown Spot', { exact: true }).first()).toBeVisible()
  await expect(page.getByText('Location-aware guidance')).toBeVisible()
  await expect(page.getByText(/Proddatur/)).toBeVisible()
})

test('navigation remains usable on mobile', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('button', { name: 'Dashboard' })).toBeVisible()
  await page.getByRole('button', { name: 'Weather' }).click()
  await expect(page.getByRole('button', { name: 'Use my location' })).toBeVisible()
})
