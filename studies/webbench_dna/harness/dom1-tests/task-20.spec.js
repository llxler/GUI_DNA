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

test('menu item file/cut', async ({ page }) => {
  const cut = page.locator('.menu .menu-item-cut')
  const paste = page.locator('.menu .menu-item-paste')

  // file/cut
  const file = page.locator('.entries > .file')
  await file.click({ button: 'right' })
  await expect(cut).toBeVisible()
  await expect(paste).toBeHidden()
  await cut.click()

  // dir/paste
  await page.locator('.entries > .dir').click({ button: 'right', position: { x: 0, y: 0 } })
  await expect(paste).toBeVisible()
  await paste.click()
  await expect(file).toBeHidden()

  // newFile
  const newFile = page.locator('.entries > .dir .file:nth-child(3)')
  await expect(newFile).toBeVisible()
  await newFile.click()
  const text = (await newFile.getAttribute('data-content')) ?? ''
  await expect(page.locator('.editor')).toHaveValue(text)
})

test('menu item dir/cut & paste', async ({ page }) => {
  const cut = page.locator('.menu .menu-item-cut')
  const paste = page.locator('.menu .menu-item-paste')

  // dir/cut
  const dir = page.locator('.entries > .dir:nth-child(2)')
  await dir.click({ button: 'right', position: { x: 0, y: 0 } })
  await expect(cut).toBeVisible()
  await cut.click()

  // entries/paste
  await page.locator('.entries').click({ button: 'right' })
  await expect(paste).toBeVisible()
  await paste.click()
  await expect(page.locator('.entries > .dir:nth-child(3)')).toBeHidden()

  // newDir
  const newDir = page.locator('.entries > .dir:nth-child(2)')
  await expect(newDir).toBeVisible()
  await expect(newDir).toHaveClass(/open/) // default closed
  await expect(newDir.getAttribute('id')).not.toBe(dir.getAttribute('id'))
  await expect(newDir).toHaveClass(/open/) // default closed

  // newDir/children
  const newDirFile = page.locator('.entries > .dir:nth-child(2) .file')
  await newDirFile.click()
  const text = (await newDirFile.getAttribute('data-content')) ?? ''
  await expect(page.locator('.editor')).toHaveValue(text)

  const newDirDir = page.locator('.entries > .dir:nth-child(2) .dir')
  await newDirDir.click({ position: { x: 0, y: 0 } })
  await expect(newDirDir).toHaveClass(/selected/)
  await expect(newDirDir).not.toHaveClass(/open/)
})

test('menu item pasted dir open/close', async ({ page }) => {
  const cut = page.locator('.menu .menu-item-cut')
  const paste = page.locator('.menu .menu-item-paste')

  // dir/cut
  const dir = page.locator('.entries > .dir:nth-child(2)')
  await dir.click({ position: { x: 0, y: 0 } }) // close
  await expect(dir).not.toHaveClass(/open/)
  await dir.click({ button: 'right', position: { x: 0, y: 0 } })
  await cut.click()

  // entries/paste
  await page.locator('.entries').click({ button: 'right' })
  await paste.click()
  await expect(page.locator('.entries > .dir:nth-child(3)')).toBeHidden()

  // newDir
  const newDir = page.locator('.entries > .dir:nth-child(2)')
  await expect(newDir).toBeVisible()
  await expect(newDir).not.toHaveClass(/open/) // default closed
})

test('menu item entries/paste', async ({ page }) => {
  const cut = page.locator('.menu .menu-item-cut')
  const paste = page.locator('.menu .menu-item-paste')

  await page.locator('.entries').click({ button: 'right' })
  await expect(paste).toBeHidden()
  await expect(cut).toBeHidden()

  // cut file
  await page.locator('.entries > .file').click({ button: 'right' })
  await cut.click()

  // entries paste visble
  await page.locator('.entries').click({ button: 'right' })
  await expect(paste).toBeVisible()
  await expect(cut).toBeHidden()

  // paste
  await paste.click()
  await expect(page.locator('.entries > .file:nth-child(1)')).toBeHidden()
  await expect(page.locator('.entries > .file:nth-child(2)')).toBeVisible()
})
