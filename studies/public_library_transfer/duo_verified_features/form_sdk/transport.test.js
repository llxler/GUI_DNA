import React from 'react';
import {render, screen, act, fireEvent} from '@testing-library/react';
import fetchMock from 'fetch-mock';
import BookForm from './ResourceEditor';

afterEach(()=>fetchMock.restore());

test.each([[201,'Saved Violet'],[409,'Could not save']])('the SDK form sends edits and handles status %i',async(status,expected)=>{
  fetchMock.post('/calibration/books/23',{status,body:{title:'Violet'}});
  render(<BookForm shelf="23"/>);
  fireEvent.change(screen.getByLabelText('Title'),{target:{value:'Blue skies'}});
  await act(async()=>{fireEvent.click(screen.getByRole('button',{name:'Store book'}));});
  expect(fetchMock.calls('/calibration/books/23')).toHaveLength(1);
  expect(JSON.parse(fetchMock.lastOptions().body)).toEqual({title:'Blue skies'});
  expect(screen.getByText(expected)).toBeTruthy();
});
