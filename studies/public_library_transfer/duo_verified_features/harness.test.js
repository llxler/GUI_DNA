import fetchMock from 'fetch-mock';

afterEach(() => { fetchMock.restore(); });

test.each([200, 500])('one documented request, response status %i', async status => {
  const base = '/api/generatePostPerformanceReport';
  const full = base+'?postId=1';
  fetchMock.get(full,{status,body:{}});
  const response = await fetch(full);
  expect(response.status).toBe(status);
  expect(fetchMock.calls()).toHaveLength(1);
  expect(fetchMock.calls(full)).toHaveLength(1);
  expect(fetchMock.calls(base)).toHaveLength(0);
});
