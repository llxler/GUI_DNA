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

const os = require('os')

/**
 * @param {import('@playwright/test').Locator} locator
 */
export async function getEntryName(locator) {
  return locator.evaluate((el) => {
    const firstTextNode = Array.from(el.childNodes).find((node) => node.nodeType === Node.TEXT_NODE)
    return firstTextNode?.nodeValue ?? ''
  })
}
export function getCmdKey() {
  const isMac = os.platform() === 'darwin'
  return isMac ? 'Meta' : 'Control'
}

export function getCmdKeyText() {
  const isMac = os.platform() === 'darwin'
  return isMac ? 'Cmd' : 'Ctrl'
}
