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

const { test, expect } = require('@playwright/test')
const { getViewport, getOffset } = require('@web-bench/test-util')

test.beforeEach(async ({ page }) => {
  await page.goto('/index.html')
})

test('body', async ({ page }) => {
  const style = await page.locator('body').evaluate((el) => window.getComputedStyle(el))
  expect(parseInt(style.padding || '0', 10)).toBe(0)
  expect(parseInt(style.margin || '0', 10)).toBe(0)

  await expect(page.locator('body')).toBeAttached()
  const body = await getOffset(page, 'body')
  const viewport = await getViewport(page)
  expect(body.width).toBeCloseTo(viewport.width)
  expect(body.height).toBeCloseTo(viewport.height)
})

test('explorer', async ({ page }) => {
  await expect(page.locator('.explorer')).toBeAttached()
  const explorer = await getOffset(page, '.explorer')
  const viewport = await getViewport(page)
  expect(explorer.width).toBeCloseTo(viewport.width)
  expect(explorer.height).toBeCloseTo(viewport.height)
})

test('leftbar', async ({ page }) => {
  await expect(page.locator('.leftbar')).toBeAttached()
  const style = await page.locator('.leftbar').evaluate((el) => window.getComputedStyle(el))
  expect(style.boxSizing).toBe('border-box')

  const leftbar = await getOffset(page, '.leftbar')
  const viewport = await getViewport(page)
  expect(leftbar.left).toBeCloseTo(0)
  expect(leftbar.height).toBeCloseTo(viewport.height)
  expect(leftbar.width).toBeCloseTo(300)
})

test('editor', async ({ page }) => {
  await expect(page.locator('textarea.editor')).toBeAttached()
  const editor = await getOffset(page, '.editor')
  const leftbar = await getOffset(page, '.leftbar')
  const viewport = await getViewport(page)
  expect(editor.left).toBeCloseTo(leftbar.width)
  expect(editor.height).toBeCloseTo(viewport.height)
  expect(leftbar.width + editor.width).toBeCloseTo(viewport.width)
})
