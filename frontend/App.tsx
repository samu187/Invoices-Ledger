// 1. Imports
import { useState } from 'react';
import { AppShell, Burger, Group, NavLink, Paper, Stack, Text } from '@mantine/core';
import Accounts from './views/Accounts';
import Invoices from './views/Invoices';
import Vat from './views/Vat';
import Payments from './views/Payments';
import Suppliers from './views/Suppliers';
import Dashboard from './views/Dashboard';
import Assistant from './components/Assistant';

export default function App() {
  // 2. State
  const [view, setView] = useState('Dashboard');
  const [invoiceId, setInvoiceId] = useState<number | null>(null);
  const [journalId, setJournalId] = useState<number | null>(null);
  const [paymentId, setPaymentId] = useState<number | null>(null);
  const [accountCode, setAccountCode] = useState<string | null>(null);
  const [vatMonth, setVatMonth] = useState(() => {
    const today = new Date();
    return `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}`;
  });
  const [menuOpened, setMenuOpened] = useState(false);
  const [assistantOpened, setAssistantOpened] = useState(false);
  const [assistantRevision, setAssistantRevision] = useState(0);

  // 3. Helpers
  function selectView(name: string) {
    setInvoiceId(null);
    setJournalId(null);
    setPaymentId(null);
    setAccountCode(null);
    setView(name);
    setMenuOpened(false);
  }

  function openInvoice(id: number) {
    setInvoiceId(id);
    setView('Invoices');
  }

  function openPayment(id: number) {
    setPaymentId(id);
    setView('Payments');
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
          {['Dashboard', 'Accounts', 'Invoices', 'VAT', 'Payments', 'Suppliers'].map((name) => (
            <NavLink key={name} component="button" className="sidebar-link" label={name} active={view === name} aria-current={view === name ? 'page' : undefined} onClick={() => selectView(name)} />
          ))}
        </Stack>
        <Stack gap={2} mt="auto" pt="xl">
          <Assistant opened={assistantOpened} onOpenedChange={setAssistantOpened} onRecordCreated={() => setAssistantRevision((revision) => revision + 1)} />
        </Stack>
      </AppShell.Navbar>
      <AppShell.Main>
        <Paper key={assistantRevision} withBorder p={{ base: 'md', sm: 'xl' }} radius="md">
          {view === 'Dashboard' ? <Dashboard month={vatMonth} onNavigate={selectView} onOpenAssistant={() => setAssistantOpened(true)} /> : view === 'Accounts' ? <Accounts initialAccountCode={accountCode} initialJournalId={journalId} onOpenInvoice={openInvoice} onOpenPayment={openPayment} /> : view === 'Invoices' ? <Invoices initialInvoiceId={invoiceId} onOpenJournal={openJournal} onOpenPayment={openPayment} /> : view === 'VAT' ? <Vat month={vatMonth} onMonthChange={setVatMonth} onOpenJournal={(id) => openJournal(id, '1100')} /> : view === 'Payments' ? <Payments key={paymentId ?? 'list'} initialPaymentId={paymentId} onOpenInvoice={openInvoice} onOpenJournal={openJournal} /> : <Suppliers />}
        </Paper>
      </AppShell.Main>
    </AppShell>
  );
}
