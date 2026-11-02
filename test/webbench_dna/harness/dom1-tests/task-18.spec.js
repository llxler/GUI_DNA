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

// @ts-nocheck
const { test, expect } = require('@playwright/test')
const { getCmdKey, getCmdKeyText } = require('./util/index')
const { getViewport, getOffset, getComputedStyle, isExisted } = require('@web-bench/test-util')
const path = require('path')

test.beforeEach(async ({ page }) => {
  await page.goto('/index.html')
})

test('resizer <<', async ({ page }) => {
  await page.locator('.leftbar').hover()
  await page.locator('.resizer').hover()
  const initialOffset = await getOffset(page, '.leftbar')

  // drag
  await page.mouse.down()
  await page.mouse.move(initialOffset.width / 2, 0)
  await page.mouse.move(initialOffset.width / 4, 0)
  await page.mouse.move(initialOffset.width / 8, 0)
  await page.mouse.up()
  const finalOffset = await getOffset(page, '.leftbar')
  expect(initialOffset.width).toBeGreaterThan(finalOffset.width)
})

test('resizer >>', async ({ page }) => {
  await page.locator('.leftbar').hover()
  await page.locator('.resizer').hover()
  const initialOffset = await getOffset(page, '.leftbar')

  // drag
  await page.mouse.down()
  await page.mouse.move(initialOffset.width * 1.1, 0)
  await page.mouse.move(initialOffset.width * 1.5, 0)
  await page.mouse.move(initialOffset.width * 2.0, 0)
  await page.mouse.up()
  const finalOffset = await getOffset(page, '.leftbar')
  expect(initialOffset.width).toBeLessThan(finalOffset.width)
})