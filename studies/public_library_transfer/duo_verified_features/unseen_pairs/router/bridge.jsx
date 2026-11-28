import { useLocation as useDuoLocation, useNavigate as useDuoNavigate } from 'react-router-dom';

function useHistory() {
  const navigate = useDuoNavigate();
  const location = useDuoLocation();
  return {
    location,
    push: (to, state) => navigate(to, { state }),
    replace: (to, state) => navigate(to, { replace: true, state }),
    go: steps => navigate(steps),
    goBack: () => navigate(-1),
    goForward: () => navigate(1),
  };
}
