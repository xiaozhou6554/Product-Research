import { expect, test } from "@playwright/test";

test("researcher can submit a fixed-data research run and see progress", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /从一个商品问题开始/ })).toBeVisible();
  await expect(page.getByPlaceholder(/向 Agent描述你想研究的商品/)).toBeEnabled({ timeout: 10_000 });
  await page.getByPlaceholder(/向 Agent描述你想研究的商品/).fill("帮我研究 travel organizer 在美国市场的机会");
  await page.getByRole("button", { name: "发送问题" }).click();
  await expect(page.getByText(/Live run/)).toBeVisible();
  await expect(page.getByText(/Decision brief/)).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText(/Agent智能助理/)).toBeVisible();
  await page.getByPlaceholder(/问问 Agent智能助理/).fill("利润空间怎么样？");
  await page.getByRole("button", { name: "发送问题" }).click();
  await expect(page.getByText("预估毛利率", { exact: true })).toBeVisible();
});

test("invalid API input is represented as an actionable error by the backend contract", async ({ request }) => {
  const login = await request.post("http://localhost:8000/api/v1/auth/login", { data: { email: "researcher@example.com", password: "Research123!" } });
  const token = (await login.json()).access_token;
  const response = await request.post("http://localhost:8000/api/v1/research-runs", { headers: { Authorization: `Bearer ${token}` }, data: { keyword: "", market: "CN" } });
  expect(response.status()).toBe(422);
});
