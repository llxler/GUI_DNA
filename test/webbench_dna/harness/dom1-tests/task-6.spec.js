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
const { getViewport, getOffset, getComputedStyle, isExisted } = require('@web-bench/test-util')
const path = require('path')

test.beforeEach(async ({ page }) => {
  await page.goto('/index.html')

  const addFile = page.locator('.tools button:text("file")')
  const addDir = page.locator('.tools button:text("dir")')
  await addFile.click()
  await addDir.click()
  // add to sub dir
  await addFile.click()
  await addDir.click() // selected
})

test('drag dir to entries panel', async ({ page }) => {
  const dir = page.locator('.entries > .dir:nth-child(3)')
  await expect(dir).not.toBeAttached()

  // drag and move
  await page.locator('.entries > .dir .dir').hover()
  const entries = await getOffset(page, '.entries')
  await page.mouse.down()
  await page.mouse.move(entries.width * 0.5, entries.height * 0.8)
  await page.mouse.up()

  await expect(dir).toBeAttached()
  await expect(dir).toHaveClass(/selected/)
})

test('drag file to entries panel', async ({ page }) => {
  const file = page.locator('.entries > .file:nth-child(3)')
  await expect(file).not.toBeAttached()

  // drag and move
  await page.locator('.entries > .dir .file').hover()
  const entries = await getOffset(page, '.entries')
  await page.mouse.down()
  await page.mouse.move(entries.width * 0.5, entries.height * 0.8)
  await page.mouse.up()

  await expect(file).toBeAttached()
  await expect(file).toHaveClass(/selected/)
})

test('drag file to insert after a file', async ({ page }) => {
  const text = (await page.locator('.entries > .dir .file').getAttribute('data-content')) ?? ''
  const file = page.locator('.entries > .file:nth-child(2)')
  await expect(file).not.toBeAttached()

  // drag and move
  await page.locator('.entries > .dir .file').hover()
  const file1 = await getOffset(page, '.entries > .file:nth-child(1)')
  await page.mouse.down()
  await page.mouse.move(file1.centerX, file1.centerY)
  await page.mouse.up()

  await expect(file).toHaveAttribute('data-content', text)
  await expect(file).toHaveClass(/selected/)
})

test('drag file to append to a dir', async ({ page }) => {
  const text = (await page.locator('.entries > .file').getAttribute('data-content')) ?? ''
  const file = page.locator('.entries > .dir .file:nth-child(3)')
  await expect(file).not.toBeAttached()

  // drag and move
  await page.locator('.entries > .file').hover()
  const dir = await getOffset(page, '.entries > .dir:nth-child(2)')
  await page.mouse.down()
  await page.mouse.move(dir.centerX - 1, dir.top)
  await page.mouse.up()

  await expect(file).toBeAttached()
  await expect(file).toHaveAttribute('data-content', text)
  await expect(file).toHaveClass(/selected/)
})

test('drag file to insert after a dir', async ({ page }) => {
  const text = (await page.locator('.entries > .file').getAttribute('data-content')) ?? ''
  const file = page.locator('.entries > .file:nth-child(2)')
  await expect(file).not.toBeAttached()

  // drag and move
  await page.locator('.entries > .file').hover()
  const dir = await getOffset(page, '.entries > .dir:nth-child(2)')
  await page.mouse.down()
  await page.mouse.move(dir.centerX + 1, dir.top)
  await page.mouse.up()

  await expect(file).toBeAttached()
  await expect(file).toHaveAttribute('data-content', text)
  await expect(file).toHaveClass(/selected/)
})
