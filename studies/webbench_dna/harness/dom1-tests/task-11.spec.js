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
})

test('import file', async ({ page }) => {
  const data = {
    entries: [{ type: 'file', name: 'file-0.txt', content: 'file content from file-0.txt' }],
  }
  page.on('dialog', async (dialog) => {
    if (dialog.type() === 'prompt') {
      await dialog.accept(JSON.stringify(data))
    }
  })

  await page.locator('.tools button:text("imp")').click()
  const file = page.locator('.entries > .file')
  await expect(file).toBeVisible()
  await expect(file).toHaveText(data.entries[0].name)
  await expect(file).toHaveAttribute('data-content', data.entries[0].content)
})

test('import dir', async ({ page }) => {
  const data = {
    entries: [{ type: 'dir', name: 'dir-0' }],
  }
  page.on('dialog', async (dialog) => {
    if (dialog.type() === 'prompt') {
      await dialog.accept(JSON.stringify(data))
    }
  })

  await page.locator('.tools button:text("imp")').click()
  const dir = page.locator('.entries > .dir')
  await expect(dir).toBeVisible()
  await expect(dir).toHaveText(data.entries[0].name)
})

test('import dirs & files', async ({ page }) => {
  const data = {
    entries: [
      { type: 'file', name: 'file-0.txt', content: 'file content from file-0.txt' },
      {
        type: 'dir',
        name: 'dir-0',
        children: [
          { type: 'file', name: 'file-2.txt', content: 'file content from file-2.txt' },
          { type: 'dir', name: 'dir-2', children: [] },
        ],
      },
    ],
  }
  page.on('dialog', async (dialog) => {
    if (dialog.type() === 'prompt') {
      await dialog.accept(JSON.stringify(data))
    }
  })

  await page.locator('.tools button:text("imp")').click()
  const file = page.locator('.entries > .file')
  await expect(file).toBeVisible()
  await expect(file).toHaveText(data.entries[0].name)
  await expect(file).toHaveAttribute('data-content', data.entries[0].content)

  const dir = page.locator('.entries > .dir')
  await expect(dir).toBeVisible()
  await expect(await getEntryName(dir)).toBe(data.entries[1].name)
  // children
  await expect(dir.locator('.file')).toHaveText(data.entries[1].children[0].name)
  await expect(dir.locator('.file')).toHaveAttribute(
    'data-content',
    data.entries[1].children[0].content
  )
  await expect(await getEntryName(dir.locator('.dir'))).toBe(data.entries[1].children[1].name)
})

test('import complicated dirs & files', async ({ page }) => {
  const data = {
    entries: [
      { type: 'file', name: 'file-0.txt', content: 'file content from file-0.txt' },
      {
        type: 'dir',
        name: 'dir-0',
        children: [
          { type: 'file', name: 'file-2.txt', content: 'file content from file-2.txt' },
          { type: 'dir', name: 'dir-2', children: [] },
        ],
      },
      { type: 'file', name: 'file-4.txt', content: 'file content from file-4.txt' },
      {
        type: 'dir',
        name: 'dir-4',
        children: [{ type: 'file', name: 'file-6.txt', content: 'file content from file-6.txt' }],
      },
    ],
  }

  page.on('dialog', async (dialog) => {
    if (dialog.type() === 'prompt') {
      await dialog.accept(JSON.stringify(data))
    }
  })

  await page.locator('.tools button:text("imp")').click()

  const file1 = page.locator('.entries > .file:nth-child(1)')
  await expect(file1).toBeVisible()
  await expect(file1).toHaveText(data.entries[0].name)
  await expect(file1).toHaveAttribute('data-content', data.entries[0].content)

  const dir2 = page.locator('.entries > .dir:nth-child(2)')
  await expect(dir2).toBeVisible()
  await expect(await getEntryName(dir2)).toBe(data.entries[1].name)
  // children
  await expect(dir2.locator('.file')).toHaveText(data.entries[1].children[0].name)
  await expect(dir2.locator('.file')).toHaveAttribute(
    'data-content',
    data.entries[1].children[0].content
  )
  await expect(await getEntryName(dir2.locator('.dir'))).toBe(data.entries[1].children[1].name)

  const file3 = page.locator('.entries > .file:nth-child(3)')
  await expect(file3).toBeVisible()
  await expect(file3).toHaveText(data.entries[2].name)
  await expect(file3).toHaveAttribute('data-content', data.entries[2].content)

  const dir4 = page.locator('.entries > .dir:nth-child(4)')
  await expect(dir4).toBeVisible()
  await expect(await getEntryName(dir4)).toBe(data.entries[3].name)
  // children
  await expect(dir4.locator('.file')).toHaveText(data.entries[3].children[0].name)
  await expect(dir4.locator('.file')).toHaveAttribute(
    'data-content',
    data.entries[3].children[0].content
  )
})
