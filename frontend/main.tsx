import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { createTheme, MantineProvider, Table } from '@mantine/core';
import '@mantine/core/styles.css';
import '@mantine/dates/styles.css';
import './theme.css';
import App from './App';

const theme = createTheme({
  primaryColor: 'indigo',
  defaultRadius: 'sm',
  fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
  headings: { fontWeight: '600' },
  components: {
    Table: Table.extend({ defaultProps: { verticalSpacing: 6, horizontalSpacing: 'md', fz: 'sm' } }),
  },
});

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <MantineProvider theme={theme} forceColorScheme="light">
      <App />
    </MantineProvider>
  </StrictMode>,
);
