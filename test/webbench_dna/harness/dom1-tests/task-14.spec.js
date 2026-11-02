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

  const addFile = page.locator('.tools button:text("file")')
  const addDir = page.locator('.tools button:text("dir")')
  await addFile.click()
  await addDir.click()
  // add to sub dir
  await addFile.click()
  await addDir.click() // selected

  await page.locator('.entries > .file').click()
})

test('menu item text', async ({ page }) => {
  const cmdKey = getCmdKey()
  await page.keyboard.down(cmdKey)
  await page.keyboard.press('KeyC')
  await page.keyboard.up(cmdKey)

  const cmdKeyText = getCmdKeyText()
  const dir = page.locator('.entries > .dir:nth-child(2)')
  await dir.click({ button: 'right', position: { x: 0, y: 0 } })
  await expect(page.locator('.menu .menu-item-copy')).toContainText(
    new RegExp(`${cmdKeyText}(\\s*)\\+(\\s*)C`, 'i')
  )
  await expect(page.locator('.menu .menu-item-paste')).toContainText(
    new RegExp(`${cmdKeyText}(\\s*)\\+(\\s*)V`, 'i')
  )
  await expect(page.locator('.menu .menu-item-add-file')).toContainText(
    new RegExp(`${cmdKeyText}(\\s*)\\+(\\s*)J`, 'i')
  )
  await expect(page.locator('.menu .menu-item-add-dir')).toContainText(
    new RegExp(`${cmdKeyText}(\\s*)\\+(\\s*)K`, 'i')
  )
})

test('Cmd/Ctrl + V', async ({ page }) => {
  const cmdKey = getCmdKey()

  await expect(page.locator('.entries > .file:nth-child(2)')).toBeHidden()

  await page.keyboard.down(cmdKey)
  await page.keyboard.press('KeyV')
  await page.keyboard.up(cmdKey)

  await expect(page.locator('.entries > .file:nth-child(2)')).toBeHidden()
})

test('Cmd/Ctrl + C & Cmd/Ctrl + V', async ({ page }) => {
  const cmdKey = getCmdKey()

  await expect(page.locator('.entries > .file:nth-child(2)')).toBeHidden()

  await page.keyboard.down(cmdKey)
  await page.keyboard.press('KeyC')
  await page.keyboard.up(cmdKey)

  await page.keyboard.down(cmdKey)
  await page.keyboard.press('KeyV')
  await page.keyboard.up(cmdKey)

  await expect(page.locator('.entries > .file:nth-child(2)')).toBeVisible()
})

test('Cmd/Ctrl + J', async ({ page }) => {
  const cmdKey = getCmdKey()

  await expect(page.locator('.entries > .file:nth-child(2)')).toBeHidden()

  await page.keyboard.down(cmdKey)
  await page.keyboard.press('KeyJ')
  await page.keyboard.up(cmdKey)

  await expect(page.locator('.entries > .file:nth-child(2)')).toBeVisible()
})

test('Cmd/Ctrl + K', async ({ page }) => {
  const cmdKey = getCmdKey()

  await expect(page.locator('.entries > .dir:nth-child(3)')).toBeHidden()

  await page.keyboard.down(cmdKey)
  await page.keyboard.press('KeyK')
  await page.keyboard.up(cmdKey)

  await expect(page.locator('.entries > .dir:nth-child(3)')).toBeVisible()
})
