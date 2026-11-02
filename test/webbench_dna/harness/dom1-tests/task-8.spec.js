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

test('menu item entries/add file', async ({ page }) => {
  await page.locator('.entries').click({ button: 'right' })
  await expect(page.locator('.menu .menu-item-add-file')).toBeVisible()
  await page.locator('.menu .menu-item-add-file').click()
  await expect(page.locator('.menu')).toBeHidden()

  await expect(page.locator('.entries > .file:nth-child(3)')).toBeVisible()
})

test('menu item entries/add dir', async ({ page }) => {
  await page.locator('.entries').click({ button: 'right' })
  await expect(page.locator('.menu .menu-item-add-dir')).toBeVisible()
  await page.locator('.menu .menu-item-add-dir').click()
  await expect(page.locator('.menu')).toBeHidden()

  await expect(page.locator('.entries > .dir:nth-child(3)')).toBeVisible()
})

test('menu item no entries/delete', async ({ page }) => {
  await page.locator('.entries').click({ button: 'right' })
  await expect(page.locator('.menu .menu-item-delete')).toBeHidden()
})