// 1. Imports
import { useState } from 'react';
import { AppShell, Burger, Group, NavLink, Paper, Stack, Text, Title } from '@mantine/core';
import Accounts from './views/Accounts';
import Invoices from './views/Invoices';
import Vat from './views/Vat';
import Payments from './views/Payments';
import Suppliers from './views/Suppliers';
import AssistantPreview from './components/AssistantPreview';

export default function App() {
  // 2. State
  const [view, setView] = useState('Accounts');
  const [invoiceId, setInvoiceId] = useState<number | null>(null);
  const [journalId, setJournalId] = useState<number | null>(null);
  const [accountCode, setAccountCode] = useState<string | null>(null);
  const [vatMonth, setVatMonth] = useState(() => {
    const today = new Date();
    return `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}`;
  });
  const [menuOpened, setMenuOpened] = useState(false);

  // 3. Helpers
  function selectView(name: string) {
    setInvoiceId(null);
    setJournalId(null);
    setAccountCode(null);
    setView(name);
    setMenuOpened(false);
  }

  function openInvoice(id: number) {
    setInvoiceId(id);
    setView('Invoices');
  }

  function openJournal(id: number, code: string | null = null) {
    setAccountCode(code);
    setJournalId(id);
    setView('Accounts');
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
          {['Accounts', 'Invoices', 'VAT', 'Payments', 'Suppliers'].map((name) => (
            <NavLink key={name} component="button" className="sidebar-link" label={name} active={view === name} aria-current={view === name ? 'page' : undefined} onClick={() => selectView(name)} />
          ))}
        </Stack>
        <Stack gap={2} mt="auto" pt="xl">
          <AssistantPreview />
        </Stack>
      </AppShell.Navbar>
      <AppShell.Main>
        <Paper withBorder p={{ base: 'md', sm: 'xl' }} radius="md">
          {view === 'Accounts' ? <Accounts initialAccountCode={accountCode} initialJournalId={journalId} onOpenInvoice={openInvoice} /> : view === 'Invoices' ? <Invoices initialInvoiceId={invoiceId} onOpenJournal={openJournal} /> : view === 'VAT' ? <Vat month={vatMonth} onMonthChange={setVatMonth} onOpenJournal={(id) => openJournal(id, '1100')} /> : view === 'Payments' ? <Payments onOpenInvoice={openInvoice} /> : view === 'Suppliers' ? <Suppliers /> : (
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
