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
const { getCmdKey, getCmdKeyText, getEntryName } = require('./util/index')
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

test('filter 1st level file', async ({ page }) => {
  const keyword = await getEntryName(page.locator('.entries > .file'))
  page.on('dialog', async (dialog) => {
    if (dialog.type() === 'prompt') {
      await dialog.accept(keyword)
    }
  })

  const filter = page.locator('.tools button:text("filter")')
  await filter.click()
  await expect(page.locator('.entries > .file')).toBeVisible()
  await expect(page.locator('.entries > .dir')).toBeHidden()
})

test('filter 1st level dir', async ({ page }) => {
  const keyword = await getEntryName(page.locator('.entries > .dir'))
  page.on('dialog', async (dialog) => {
    if (dialog.type() === 'prompt') {
      await dialog.accept(keyword)
    }
  })

  const filter = page.locator('.tools button:text("filter")')
  await filter.click()
  await expect(page.locator('.entries > .file')).toBeHidden()
  await expect(page.locator('.entries > .dir')).toBeVisible()
})

test('filter 2nd level file', async ({ page }) => {
  const keyword = await getEntryName(page.locator('.entries > .dir .file'))
  page.on('dialog', async (dialog) => {
    if (dialog.type() === 'prompt') {
      await dialog.accept(keyword)
    }
  })

  const filter = page.locator('.tools button:text("filter")')
  await filter.click()
  await expect(page.locator('.entries > .file')).toBeHidden()
  await expect(page.locator('.entries > .dir')).toBeVisible()
  await expect(page.locator('.entries > .dir .file')).toBeVisible()
  await expect(page.locator('.entries > .dir .dir')).toBeHidden()
})

test('filter 2nd level dir', async ({ page }) => {
  const keyword = await getEntryName(page.locator('.entries > .dir .dir'))
  page.on('dialog', async (dialog) => {
    if (dialog.type() === 'prompt') {
      await dialog.accept(keyword)
    }
  })

  const filter = page.locator('.tools button:text("filter")')
  await filter.click()
  await expect(page.locator('.entries > .file')).toBeHidden()
  await expect(page.locator('.entries > .dir')).toBeVisible()
  await expect(page.locator('.entries > .dir .file')).toBeHidden()
  await expect(page.locator('.entries > .dir .dir')).toBeVisible()
})

test('filter with empty keyword', async ({ page }) => {
  let keyword = await getEntryName(page.locator('.entries > .dir .dir'))
  page.on('dialog', async (dialog) => {
    if (dialog.type() === 'prompt') {
      await dialog.accept(keyword)
    }
  })

  const filter = page.locator('.tools button:text("filter")')
  await filter.click()
  await expect(page.locator('.entries > .file')).toBeHidden()
  await expect(page.locator('.entries > .dir')).toBeVisible()
  await expect(page.locator('.entries > .dir .file')).toBeHidden()
  await expect(page.locator('.entries > .dir .dir')).toBeVisible()

  keyword = ''
  await filter.click()
  await expect(page.locator('.entries > .file')).toBeVisible()
  await expect(page.locator('.entries > .dir')).toBeVisible()
  await expect(page.locator('.entries > .dir .file')).toBeVisible()
  await expect(page.locator('.entries > .dir .dir')).toBeVisible()
})
