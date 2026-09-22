// 1. Imports
import { useState } from 'react';
import { AppShell, Burger, Group, NavLink, Paper, Stack, Text, Title } from '@mantine/core';
import Accounts from './views/Accounts';

export default function App() {
  // 2. State
  const [view, setView] = useState('Accounts');
  const [menuOpened, setMenuOpened] = useState(false);

  // 3. Helpers
  function selectView(name: string) {
    setView(name);
    setMenuOpened(false);
  }

  // 4. View
  return (
    <AppShell header={{ height: 64 }} navbar={{ width: 260, breakpoint: 'sm', collapsed: { mobile: !menuOpened } }} padding={{ base: 'sm', sm: 'xl' }}>
      <AppShell.Header>
        <Group h="100%" px="xl" justify="space-between">
          <Group gap="sm">
            <Burger opened={menuOpened} onClick={() => setMenuOpened(!menuOpened)} hiddenFrom="sm" size="sm" aria-label="Toggle navigation" />
            <Text className="brand-mark" aria-hidden="true">IL</Text>
            <Text fw={600} size="lg" c="dark.8">Invoice Ledger</Text>
          </Group>
          <Text size="sm" c="dimmed">Sample Company Demo Ltd · GBP</Text>
        </Group>
      </AppShell.Header>
      <AppShell.Navbar p="lg" className="sidebar">
        <Text size="xs" fw={600} tt="uppercase" c="dimmed" mb="lg" pl="sm" style={{ letterSpacing: '0.1em' }}>Workspace</Text>
        <Stack gap={6}>
          {['Invoices', 'Payments', 'Suppliers', 'Accounts'].map((name) => (
            <NavLink key={name} component="button" className="sidebar-link" label={name} active={view === name} aria-current={view === name ? 'page' : undefined} onClick={() => selectView(name)} />
          ))}
        </Stack>
        <Stack gap={2} mt="auto" px="sm" pt="xl">
          <Text size="xs" fw={500} c="dimmed">Demo workspace</Text>
          <Text size="xs" c="dimmed">Base currency · GBP</Text>
        </Stack>
      </AppShell.Navbar>
      <AppShell.Main>
        <Paper withBorder p={{ base: 'md', sm: 'xl' }} radius="md">
          {view === 'Accounts' ? <Accounts /> : (
            <Stack>
              <Title order={1} size="h2">{view}</Title>
              <Text c="dimmed">This view is coming next.</Text>
            </Stack>
          )}
        </Paper>
      </AppShell.Main>
    </AppShell>
  );
}
