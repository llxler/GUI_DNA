// Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
// 
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
// 
//     http://www.apache.org/licenses/LICENSE-2.0
// 
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

const path = require('path')
const { test, expect } = require('@playwright/test')
const { isExisted } = require('@web-bench/test-util')

test.beforeEach(async ({ page }) => {
  await page.goto('/index.html')

  const addFile = page.locator('.tools button:text("file")')
  await addFile.click()
})

test('> 1 file existed', async ({ page }) => {
  const count = await page.locator('.entries > .file').count()
  await expect(count).toBeGreaterThan(0)
})

test('file entry', async ({ page }) => {
  await expect(page.locator('.entries > .entry.file:nth-child(1)')).toBeVisible()
})

test('add files', async ({ page }) => {
  const addFile = page.locator('.tools button:text("file")')
  const count1 = await page.locator('.entries .file').count()
  await addFile.click()
  const count2 = await page.locator('.entries .file').count()
  await expect(count2).toBe(count1 + 1)

  await expect(await page.locator('.entries > .file:nth-child(1)').getAttribute('id')).not.toBe(
    await page.locator('.entries > .file:nth-child(2)').getAttribute('id')
  )
})

test('click file', async ({ page }) => {
  const addFile = page.locator('.tools button:text("file")')
  await addFile.click()
  await addFile.click()
  await addFile.click()

  const locators = await page.locator('.tools .file').all()
  for (const locator of locators) {
    await locator.click()
    const content = (await locator.getAttribute('data-content')) ?? ''
    await expect(page.locator('.editor')).toHaveText(content)
  }
})
