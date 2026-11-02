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

test('menu item file/copy', async ({ page }) => {
  const copy = page.locator('.menu .menu-item-copy')
  const paste = page.locator('.menu .menu-item-paste')

  // file/copy
  const file = page.locator('.entries > .file')
  await file.click({ button: 'right' })
  await expect(copy).toBeVisible()
  await expect(paste).toBeHidden()
  await copy.click()

  // dir/paste
  await page.locator('.entries > .dir').click({ button: 'right', position: { x: 0, y: 0 } })
  await expect(paste).toBeVisible()
  await paste.click()

  // newFile
  const newFile = page.locator('.entries > .dir .file:nth-child(3)')
  await expect(newFile).toBeVisible()
  await expect(await newFile.getAttribute('id')).not.toBe(await file.getAttribute('id'))
  await newFile.click()
  const text = (await newFile.getAttribute('data-content')) ?? ''
  await expect(page.locator('.editor')).toHaveValue(text)
})

test('menu item dir/copy & paste', async ({ page }) => {
  const copy = page.locator('.menu .menu-item-copy')
  const paste = page.locator('.menu .menu-item-paste')

  // dir/copy
  const dir = page.locator('.entries > .dir:nth-child(2)')
  await dir.click({ button: 'right', position: { x: 0, y: 0 } })
  await expect(copy).toBeVisible()
  await copy.click()

  // entries/paste
  await page.locator('.entries').click({ button: 'right' })
  await expect(paste).toBeVisible()
  await paste.click()

  // newDir
  const newDir = page.locator('.entries > .dir:nth-child(3)')
  await expect(newDir).toBeVisible()
  await expect(newDir).toHaveClass(/open/) // default closed
  await expect(newDir.getAttribute('id')).not.toBe(dir.getAttribute('id'))
  await expect(newDir).toHaveClass(/open/) // default closed

  // newDir/children
  const newDirFile = page.locator('.entries > .dir:nth-child(3) .file')
  await expect(await newDirFile.getAttribute('id')).not.toBe(
    await page.locator('.entries > .dir:nth-child(2) .file').getAttribute('id')
  )
  await newDirFile.click()
  const text = (await newDirFile.getAttribute('data-content')) ?? ''
  await expect(page.locator('.editor')).toHaveValue(text)

  const newDirDir = page.locator('.entries > .dir:nth-child(3) .dir')
  await expect(await newDirDir.getAttribute('id')).not.toBe(
    await page.locator('.entries > .dir:nth-child(2) .dir').getAttribute('id')
  )
  await newDirDir.click({ position: { x: 0, y: 0 } })
  await expect(newDirDir).toHaveClass(/selected/)
  await expect(newDirDir).not.toHaveClass(/open/)
})

test('menu item pasted dir open/close', async ({ page }) => {
  const copy = page.locator('.menu .menu-item-copy')
  const paste = page.locator('.menu .menu-item-paste')

  // dir/copy
  const dir = page.locator('.entries > .dir:nth-child(2)')
  await dir.click({ position: { x: 0, y: 0 } }) // close
  await expect(dir).not.toHaveClass(/open/)
  await dir.click({ button: 'right', position: { x: 0, y: 0 } })
  await copy.click()

  // entries/paste
  await page.locator('.entries').click({ button: 'right' })
  await paste.click()

  // newDir
  const newDir = page.locator('.entries > .dir:nth-child(3)')
  await expect(newDir).toBeVisible()
  await expect(newDir).not.toHaveClass(/open/) // default closed
})

test('menu item entries/paste', async ({ page }) => {
  const copy = page.locator('.menu .menu-item-copy')
  const paste = page.locator('.menu .menu-item-paste')

  await page.locator('.entries').click({ button: 'right' })
  await expect(paste).toBeHidden()
  await expect(copy).toBeHidden()

  // copy file
  await page.locator('.entries > .file').click({ button: 'right' })
  await copy.click()

  // entries paste visble
  await page.locator('.entries').click({ button: 'right' })
  await expect(paste).toBeVisible()
  await expect(copy).toBeHidden()

  // paste
  await paste.click()
  await expect(page.locator('.entries > .file:nth-child(3)')).toBeVisible()
})
