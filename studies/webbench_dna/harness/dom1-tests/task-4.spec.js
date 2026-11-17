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
const { getViewport, getOffset, isExisted } = require('@web-bench/test-util')
const path = require('path')

test.beforeEach(async ({ page }) => {
  await page.goto('/index.html')

  const addFile = page.locator('.tools button:text("file")')
  const addDir = page.locator('.tools button:text("dir")')
  await addFile.click()
  await addDir.click()
  // sub dir
  await addFile.click()
  await addDir.click()
})

test('> 1 selected dir', async ({ page }) => {
  await expect(page.locator('.entries > .dir .dir')).toHaveClass(/selected/)
})

test('select/unselect file', async ({ page }) => {
  const entries = page.locator('.entries')
  const file = entries.locator('> .file:nth-child(1)')

  await expect(file).not.toHaveClass(/selected/)
  await entries.locator('> .file:nth-child(1)').click()
  await expect(file).toHaveClass(/selected/)
  await entries.click()
  await expect(file).not.toHaveClass(/selected/)
})

test('select/unselect dir', async ({ page }) => {
  const entries = page.locator('.entries')
  const file = page.locator('.entries > .file:nth-child(1)')
  const dir = page.locator('.entries > .dir:nth-child(2)')

  await file.click()
  await expect(file).toHaveClass(/selected/)
  await expect(dir).not.toHaveClass(/selected/)

  await dir.click({ position: { x: 0, y: 0 } })
  await expect(dir).toHaveClass(/selected/)

  await entries.click()
  await expect(dir).not.toHaveClass(/selected/)
})

test('add entry when SelectedEntry is dir', async ({ page }) => {
  const entries = page.locator('.entries')
  const dir = entries.locator('> .dir:nth-child(2)')
  await expect(dir.locator('> .dir-content > .file:nth-child(1)')).toBeVisible()
  await expect(dir.locator('> .dir-content > .dir:nth-child(2)')).toBeVisible()
})

test('add file when SelectedEntry is file', async ({ page }) => {
  const entries = page.locator('.entries')
  const addFile = page.locator('.tools button:text("file")')

  await entries.locator('> .file:nth-child(1)').click() // select
  await addFile.click()
  await expect(entries.locator('> .file:nth-child(2)')).toBeVisible()
  await expect(entries.locator('> .file:nth-child(2)')).toHaveClass(/selected/)
  await expect(entries.locator('> .file:nth-child(3)')).not.toBeAttached()

  await entries.click()
  await addFile.click()
  await expect(entries.locator('> .file:nth-child(4)')).toBeVisible()
  await expect(entries.locator('> .file:nth-child(4)')).toHaveClass(/selected/)
})

test('add dir when SelectedEntry is file', async ({ page }) => {
  const entries = page.locator('.entries')
  const addDir = page.locator('.tools button:text("dir")')

  await entries.locator('> .file:nth-child(1)').click() // select
  await addDir.click()
  await expect(entries.locator('> .dir:nth-child(2)')).toHaveClass(/selected/)

  await entries.click()
  await addDir.click()
  await expect(entries.locator('> .dir:nth-child(4)')).toHaveClass(/selected/)

  await addDir.click()
  await expect(entries.locator('> .dir:nth-child(4)')).toHaveClass(/open/)
  await expect(entries.locator('> .dir:nth-child(4) > .dir-content > .dir')).toBeVisible()
  await addDir.click()
  await expect(entries.locator('> .dir:nth-child(4) > .dir-content > .dir')).toHaveClass(/open/)
  await expect(
    entries.locator('> .dir:nth-child(4) > .dir-content > .dir > .dir-content > .dir')
  ).toBeVisible()
})

test('add entry when SelectedEntry is dir and closed', async ({ page }) => {
  const dir = page.locator('.entries > .dir:nth-child(2)')
  const addFile = page.locator('.tools button:text("file")')

  await expect(dir).not.toHaveClass(/selected/)
  await expect(dir).toHaveClass(/open/)
  // select & close
  await dir.click({ position: { x: 0, y: 0 } })
  await expect(dir).toHaveClass(/selected/)
  await expect(dir).not.toHaveClass(/open/)

  await addFile.click()
  await expect(dir).toHaveClass(/open/)
  await expect(dir.locator('> .dir-content > .file:last-child')).toBeVisible()
  await expect(dir.locator('> .dir-content > .file:last-child')).toHaveClass(/selected/)
})
