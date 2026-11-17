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
  await addDir.click()
})

test('del is enabled initially ', async ({ page }) => {
  const del = page.locator('.tools button:text("del")')
  const disabled = await del.evaluate((/** @type {HTMLButtonElement} */ el) => el.disabled)
  await expect(disabled).toBeFalsy()
})

test('del is disabled after 2 clicks', async ({ page }) => {
  const del = page.locator('.tools button:text("del")')
  await del.click()
  await del.click()
  await del.click()
  await del.click()
  const disabled = await del.evaluate((/** @type {HTMLButtonElement} */ el) => el.disabled)
  await expect(disabled).toBeTruthy()
})

test('del opened file', async ({ page }) => {
  const del = page.locator('.tools button:text("del")')
  await page.locator('.entries > .file:nth-child(1)').click() // select
  await del.click()
  await expect(page.locator('.editor')).toHaveValue('')
})

test('click del to select next entry - basic', async ({ page }) => {
  const del = page.locator('.tools button:text("del")')

  await del.click()
  await del.click()
  await expect(page.locator('.entries > .dir')).toHaveClass(/selected/)
  await del.click()
  await expect(page.locator('.entries > .file')).toHaveClass(/selected/)

  await del.click()
  await expect(page.locator('.entries > .entry')).toHaveCount(0)
})

test('click del to select next entry - advanced', async ({ page }) => {
  const entries = page.locator('.entries')
  const addDir = page.locator('.tools button:text("dir")')
  const addFile = page.locator('.tools button:text("file")')
  const del = page.locator('.tools button:text("del")')

  await entries.click()
  await addFile.click()
  await addFile.click()
  await entries.locator('> .file:nth-child(3)').click() // select
  await del.click()
  // nextEntry === nextSibling
  await expect(entries.locator('> .file:nth-child(3)')).toHaveClass(/selected/)
  await expect(entries.locator('> .file:nth-child(4)')).not.toBeAttached()

  await del.click()
  // nextEntry === previousSibling
  await expect(entries.locator('> .dir:nth-child(2)')).toHaveClass(/selected/)

  await addDir.click()
  await addDir.click() // dir-1 / newdir / newdir
  await del.click()
  await del.click()
  await del.click()
  await del.click()
  // nextEntry === parent
  await expect(entries.locator('> .dir:nth-child(2)')).toHaveClass(/selected/)
  await del.click()
  // nextEntry === parent
  await expect(entries.locator('> .file:nth-child(1)')).toHaveClass(/selected/)

  await del.click()
  await expect(entries.locator('> .entry')).toHaveCount(0)
})
