import { createRoot } from 'react-dom/client';
import { Workbench } from './Workbench';
import '../../hme-plate/src/fonts.css';
import './styles.css';

createRoot(document.getElementById('root')!).render(<Workbench />);
