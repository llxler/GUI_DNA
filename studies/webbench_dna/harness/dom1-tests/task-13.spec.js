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
const { getEntryName } = require('./util/index')
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

test('edit file', async ({ page }) => {
  await page.locator('.entries > .file').click()
  const oldContent = await page.locator('.entries > .file').getAttribute('data-content')
  await expect(page.locator('.editor')).toHaveValue(oldContent)
  const newContent = Math.random() + ''
  await page.locator('.editor').clear()
  await page.locator('.editor').focus()
  await page.keyboard.type(newContent)
  await expect(page.locator('.editor')).toHaveValue(newContent)
  await expect(page.locator('.entries > .file')).toHaveAttribute('data-content', newContent)
})

test('edit files', async ({ page }) => {
  await page.locator('.entries > .file').click()
  const oldContent = await page.locator('.entries > .file').getAttribute('data-content')
  await expect(page.locator('.editor')).toHaveValue(oldContent)
  const newContent = Math.random() + ''
  await page.locator('.editor').clear()
  await page.locator('.editor').focus()
  await page.keyboard.type(newContent)
  await expect(page.locator('.editor')).toHaveValue(newContent)
  await expect(page.locator('.entries > .file')).toHaveAttribute('data-content', newContent)

  await page.locator('.entries > .dir .file').click()
  await expect(page.locator('.editor')).not.toHaveValue(newContent)
  await page.locator('.entries > .file').click()
  await expect(page.locator('.editor')).toHaveValue(newContent)
})
