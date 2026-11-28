import React from 'react';
import {render, screen, act, fireEvent} from '@testing-library/react';
import {MemoryRouter} from 'react-router-dom';
import fetchMock from 'fetch-mock';
import ResourceEditor from './ResourceEditor';

afterEach(() => { fetchMock.restore(); });

test('one real PUT uses the resource supplied to the mounted editor', async () => {
  fetchMock.put('/api/comments/23', {status: 200});
  render(<MemoryRouter><ResourceEditor id="23" commentId="23" /></MemoryRouter>);
  fireEvent.change(screen.getByPlaceholderText(/edit your comment/i), {target:{value:'A different comment'}});
  await act(async () => { fireEvent.click(screen.getByRole('button', {name:/edit/i})); });
  expect(fetchMock.calls('/api/comments/23')).toHaveLength(1);
  expect(fetchMock.calls('/api/comments/1')).toHaveLength(0);
});
