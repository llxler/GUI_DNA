import React from 'react';
import {render, screen, fireEvent} from '@testing-library/react';
import {MemoryRouter} from 'react-router-dom';
import Editor from './ResourceEditor';

test('the adapted component pushes and replaces real entries and returns to the previous location', () => {
  render(<MemoryRouter initialEntries={['/shelf']}><Editor /></MemoryRouter>);
  const location = () => screen.getByRole('status').textContent;
  expect(location()).toBe('/shelf');
  fireEvent.click(screen.getByText('Open'));
  expect(location()).toBe('/shelf/23');
  fireEvent.click(screen.getByText('Rename'));
  expect(location()).toBe('/shelf/42');
  fireEvent.click(screen.getByText('Back'));
  expect(location()).toBe('/shelf');
  fireEvent.click(screen.getByText('Forward'));
  expect(location()).toBe('/shelf/42');
});
